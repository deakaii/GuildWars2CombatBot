"""
Open-world navigator: walks/rides to map-completion targets in a straight line,
steering with the turn keys and correcting every tick from MumbleLink.

One step() per tick (~20 Hz). Priority order inside a step:
  no link / paused (map open, chat, alt-tab) -> map change -> combat -> unstuck maneuver
  -> arrival -> target timeout -> mount -> steer + stuck detection.

Distances are continent units (1 unit = 24 in, about 0.61 m).
"""

import math
import random
import time
from collections import deque
from typing import Callable, Dict, List, Optional, Set

from core.gw2_map_data import Target, get_map_targets
from core.mumble_link import NavState

METERS_PER_UNIT = 0.6096

DEFAULTS = {
    "tick_interval": 0.05,
    "unlock_radius": 12.0,
    "arrive_dwell_s": 0.6,
    "mount_min_distance": 120.0,
    "heading_tolerance_deg": 12.0,
    "arc_limit_deg": 60.0,
    "invert_turn": False,
    "stuck_window_s": 3.0,
    "stuck_min_progress": 3.0,
    "max_stuck_attempts": 7,
    "target_timeout_s": 240.0,
    "combat_mode": "fight",
    "combat_timeout_s": 30.0,
    "enabled_kinds": ["waypoint", "landmark"],
}

MOVE_KEYS = ("move_forward", "move_back", "turn_left", "turn_right")


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def distance(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def heading_error(state: NavState, coord) -> float:
    """Signed angle from facing to target, radians. Positive = target is clockwise (to the right)."""
    bearing = math.atan2(coord[1] - state.pos[1], coord[0] - state.pos[0])
    return wrap_angle(bearing - state.heading_rad)


def fmt_dist(units: float) -> str:
    return f"{units:.0f}u (~{units * METERS_PER_UNIT:.0f} m)"


class Navigator:
    """
    link:     object with read() -> NavState | None (core.mumble_link.MumbleLinkReader)
    inp:      key_down/key_up/release_all/tap/is_game_focused (core.input_controller.InputController)
    progress: core.nav_progress.NavProgress
    combat:   optional object with begin()/end(); begin hands the keyboard to the combat engine
    """

    def __init__(self, link, inp, progress, config: Optional[Dict] = None,
                 targets_for_map: Callable[[int], List[Target]] = get_map_targets,
                 combat=None, log: Callable[[str], None] = print,
                 clock: Callable[[], float] = time.monotonic, rng: Optional[random.Random] = None,
                 trace: Optional[Callable[[str], None]] = None):
        self.link = link
        self.inp = inp
        self.progress = progress
        self.cfg = dict(DEFAULTS)
        self.cfg.update(config or {})
        self.targets_for_map = targets_for_map
        self.combat = combat
        self.log = log
        self.trace = trace          # detailed per-state/per-second lines for the session log file
        self._last_trace = -1e9
        self.clock = clock
        self.rng = rng or random.Random()

        self.state = "IDLE"
        self.map_id: Optional[int] = None
        self.character = ""
        self.targets: List[Target] = []
        self.target: Optional[Target] = None
        self.last: Optional[NavState] = None
        self.dist: Optional[float] = None
        self.err: Optional[float] = None

        self._held: Set[str] = set()
        self._requests: List[str] = []
        self._deferred: Set[str] = set()     # gave up once this session; retried after everything else
        self._reset_target_state()
        self._combat_since: Optional[float] = None
        self._combat_ignore_until = 0.0
        self._mount_pending_until: Optional[float] = None
        self._mount_block_until = 0.0
        self._done_logged = False

    # ------------------------------------------------------------------ public

    def request(self, action: str) -> None:
        """Thread-safe-enough hook for the GUI: "skip" or "done" the current target."""
        self._requests.append(action)

    def remaining(self) -> List[Target]:
        excluded = self.progress.excluded(self.character, self.map_id) if self.map_id is not None else set()
        kinds = set(self.cfg["enabled_kinds"])
        return [t for t in self.targets if t.kind in kinds and t.id not in excluded]

    def run(self, should_stop: Callable[[], bool], sleep: Callable[[float], None] = time.sleep) -> str:
        try:
            while not should_stop():
                t0 = self.clock()
                state = self.step()
                if state in ("DONE", "NO_DATA", "TURN_FAIL"):
                    return state
                sleep(max(0.01, self.cfg["tick_interval"] - (self.clock() - t0)))
            return "STOPPED"
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._release()
        if self._combat_since is not None and self.combat:
            self.combat.end()
        self._combat_since = None

    # ------------------------------------------------------------------ tick

    def step(self) -> str:
        now = self.clock()
        s = self.link.read()
        self.last = s
        if s is None:
            self._release()
            self._maneuver = None
            return self._set("NO_LINK")
        self.character = s.character or "unknown"

        if s.map_open or s.textbox_focused or not s.game_focused or not self.inp.is_game_focused():
            self._release()
            self._maneuver = None
            self._samples.clear()
            return self._set("PAUSED")

        if s.map_id != self.map_id:
            if not self._load_map(s.map_id):
                self._release()
                return self._set("NO_DATA")

        self._handle_requests()

        if self.target is None:
            self.target = self._pick_target(s)
            if self.target is None:
                self._release()
                if not self._done_logged:
                    self.log(f"[NAV] Map {s.map_id}: nothing left to visit "
                             f"({', '.join(self.cfg['enabled_kinds'])}). Map done!")
                    self._done_logged = True
                return self._set("DONE")

        self.dist = distance(s.pos, self.target.coord)
        self.err = heading_error(s, self.target.coord)

        combat = self._handle_combat(s, now)
        if combat:
            return self._set(combat)

        if self._maneuver is not None:
            return self._set(self._run_maneuver(now))

        if self.dist <= self.cfg["unlock_radius"]:
            self._apply(set())
            if self._dwell_since is None:
                self._dwell_since = now
            if now - self._dwell_since >= self.cfg["arrive_dwell_s"]:
                self.log(f"[NAV] Reached {self.target.kind} '{self.target.name}'.")
                self._finish_target("done")
                return self._set("ARRIVED")
            return self._set("ARRIVING")
        self._dwell_since = None

        if now - self._target_started > self.cfg["target_timeout_s"]:
            return self._set(self._give_up(f"took over {self.cfg['target_timeout_s']:.0f}s "
                                           f"({fmt_dist(self.dist)} left)"))

        mounting = self._handle_mount(s, now)
        if mounting:
            return self._set(mounting)

        return self._set(self._steer(now))

    # ------------------------------------------------------------------ pieces

    def _set(self, state: str) -> str:
        if self.trace:
            now = self.clock()
            if state != self.state or now - self._last_trace >= 1.0:
                self._last_trace = now
                self.trace(self._trace_line(state))
        self.state = state
        return state

    def _trace_line(self, state: str) -> str:
        s = self.last
        if s is None:
            return f"[NAV-TRACE] {self.state}->{state} (no link)"
        parts = [f"[NAV-TRACE] {self.state}->{state}", f"pos={s.pos[0]:.0f},{s.pos[1]:.0f}",
                 f"face={(math.degrees(s.heading_rad) + 90) % 360:.0f}"]
        if self.target is not None and self.dist is not None:
            parts += [f"target={self.target.name!r}", f"dist={self.dist:.0f}", f"err={math.degrees(self.err):+.0f}"]
        parts += [f"mounted={int(s.mounted)}", f"combat={int(s.in_combat)}", f"keys={','.join(sorted(self._held)) or '-'}"]
        if s.map_open or s.textbox_focused or not s.game_focused:
            parts.append(f"map_open={int(s.map_open)} chat={int(s.textbox_focused)} focus={int(s.game_focused)}")
        return " ".join(parts)

    def _reset_target_state(self) -> None:
        self._target_started = self.clock()
        self._attempts = 0
        self._samples = deque()
        self._dwell_since: Optional[float] = None
        self._maneuver: Optional[List] = None
        self._step_idx = -1
        self._step_deadline = 0.0
        self._no_mount = False
        self._turn_key: Optional[str] = None
        self._turn_check = None      # [since, progress_deg, last_heading, start_pos, key] while turning
        self._unstuck_side: Optional[int] = None   # +1 right / -1 left, chosen once per target
        self._maneuver_name = ""

    def _load_map(self, map_id: int) -> bool:
        self.map_id = map_id
        self.target = None
        self._done_logged = False
        self._deferred.clear()
        try:
            self.targets = self.targets_for_map(map_id)
        except Exception as e:
            self.targets = []
            self.log(f"[NAV] Couldn't load map {map_id} from the GW2 API: {e}")
            return False
        n = len(self.remaining())
        self.log(f"[NAV] Map {map_id}: {len(self.targets)} targets, {n} left to visit "
                 f"({', '.join(self.cfg['enabled_kinds'])}).")
        return True

    def _pick_target(self, s: NavState) -> Optional[Target]:
        remaining = self.remaining()
        if not remaining:
            return None
        fresh = [t for t in remaining if t.id not in self._deferred] or remaining
        target = min(fresh, key=lambda t: distance(s.pos, t.coord))
        self._reset_target_state()
        self.log(f"[NAV] Next: {target.kind} '{target.name}', {fmt_dist(distance(s.pos, target.coord))} away "
                 f"({len(remaining)} left).")
        return target

    def _finish_target(self, status: str) -> None:
        if self.target is not None:
            self.progress.mark(self.character, self.map_id, self.target.id, status)
        self._release()
        self.target = None

    def _handle_requests(self) -> None:
        while self._requests:
            action = self._requests.pop(0)
            if self.target is None:
                continue
            if action == "skip":
                self.log(f"[NAV] Skipped '{self.target.name}' (by you).")
                self._finish_target("skipped")
            elif action == "done":
                self.log(f"[NAV] Marked '{self.target.name}' done (by you).")
                self._finish_target("done")

    def _handle_combat(self, s: NavState, now: float) -> Optional[str]:
        """Hands the keyboard to the combat engine while in combat on foot."""
        fighting = (s.in_combat and not s.mounted and self.combat is not None
                    and self.cfg["combat_mode"] == "fight" and now >= self._combat_ignore_until)
        if fighting:
            if self._combat_since is None:
                self._release()
                self._maneuver = None
                self._combat_since = now
                self.log("[NAV] In combat - handing over to the rotation.")
                self.combat.begin()
            if now - self._combat_since <= self.cfg["combat_timeout_s"]:
                return "COMBAT"
            self.log(f"[NAV] Still in combat after {self.cfg['combat_timeout_s']:.0f}s - moving on.")
            self._combat_ignore_until = now + 15.0
        if self._combat_since is not None:
            self.combat.end()
            self._target_started += now - self._combat_since   # fighting doesn't count against the target
            self._combat_since = None
            self._samples.clear()
            if not s.in_combat:
                self.log("[NAV] Combat over - resuming.")
        return None

    def _handle_mount(self, s: NavState, now: float) -> Optional[str]:
        if s.mounted:
            self._mount_pending_until = None
            return None
        want = (self.dist > self.cfg["mount_min_distance"] and not s.in_combat
                and not self._no_mount and now >= self._mount_block_until)
        if not want:
            self._mount_pending_until = None
            return None
        if self._mount_pending_until is None:
            self._release()
            ok = self.inp.tap("mount")
            if self.trace:
                self.trace(f"[NAV-TRACE] mount key tapped (sent={ok}) at dist={self.dist:.0f}")
            self._mount_pending_until = now + 2.5
            return "MOUNTING"
        if now < self._mount_pending_until:
            return "MOUNTING"
        self.log("[NAV] Mount didn't come up (check the 'mount' keybind) - walking for now.")
        self._mount_pending_until = None
        self._mount_block_until = now + 20.0
        return None

    def _steer(self, now: float) -> str:
        err = self.err
        tol = math.radians(self.cfg["heading_tolerance_deg"])
        close = self.dist < 3 * self.cfg["unlock_radius"]
        arc = math.radians(25.0 if close else self.cfg["arc_limit_deg"])

        keys = set()
        if abs(err) > tol:
            right = (err > 0) != bool(self.cfg["invert_turn"])
            key = "turn_right" if right else "turn_left"
            # Target (nearly) behind: err flips sign around 180 deg, so keep the direction already chosen
            if self._turn_key and abs(err) > math.radians(135):
                key = self._turn_key
            self._turn_key = key
            keys.add(key)
        else:
            self._turn_key = None
        if abs(err) < arc:
            keys.add("move_forward")
        self._apply(keys)

        if self._turn_does_nothing(now, keys):
            return "TURN_FAIL"

        if "move_forward" not in keys:
            self._samples.clear()
            return "TURNING"

        self._samples.append((now, self.dist))
        window = self.cfg["stuck_window_s"]
        while len(self._samples) > 1 and self._samples[1][0] <= now - window:
            self._samples.popleft()
        t0, d0 = self._samples[0]
        if now - t0 >= window and d0 - self.dist < self.cfg["stuck_min_progress"]:
            return self._on_stuck(now)
        return "MOVING"

    def _turn_does_nothing(self, now: float, keys: Set[str]) -> bool:
        """Safety check: 1.5 s of holding turn keys must turn the character the expected way.
        Catches A/D bound to strafe, reversed turning, or a stuck autorun before the bot runs off.
        Progress is summed per tick across left/right switches, so dithering can't hide a fault."""
        s = self.last
        key = self._turn_key
        if key is None or key not in keys or s is None:
            self._turn_check = None
            return False

        def sign(k):
            return (1 if k == "turn_right" else -1) * (-1 if self.cfg["invert_turn"] else 1)

        if self._turn_check is None:
            self._turn_check = [now, 0.0, s.heading_rad, s.pos, key]
            return False
        chk = self._turn_check
        # heading change since last tick, credited to the key that was held during it (+ = expected way)
        chk[1] += math.degrees(wrap_angle(s.heading_rad - chk[2])) * sign(chk[4])
        chk[2], chk[4] = s.heading_rad, key
        since, progress, _, p0, _ = chk
        if now - since < 1.5:
            return False
        if progress >= 20:
            self._turn_check = [now, 0.0, s.heading_rad, s.pos, key]
            return False
        turned = progress * sign(key)
        expected = sign(key)

        self._release()
        mapper = getattr(self.inp, "mapper", None)
        bound = mapper.translate(key).upper() if mapper else key
        moved = distance(p0, s.pos)
        mount = " while mounted" if s.mounted else ""
        if progress <= -20:
            why = ("Turning is reversed. Set navigation.invert_turn: true in config/settings.yaml "
                   "(or swap turn_left/turn_right in keybinds.yaml).")
        elif "move_forward" not in keys and moved > 10:
            why = (f"You moved {fmt_dist(moved)} without W held, so [{bound}] is most likely STRAFE in your game. "
                   f"In GW2 Options > Control Options, give 'Turn Left' / 'Turn Right' a key (e.g. a secondary "
                   f"bind) and put those keys as turn_left / turn_right 'user' in config/keybinds.yaml.")
        else:
            why = (f"[{bound}] doesn't seem to be bound to '{key.replace('_', ' ').title()}' in GW2. Check Options > "
                   f"Control Options and the turn_left / turn_right 'user' keys in config/keybinds.yaml.")
        self.log(f"[NAV] Stopped: holding {key} [{bound}] for 1.5s turned you {turned:+.0f} deg{mount} "
                 f"(expected {'right' if expected > 0 else 'left'}). {why}")
        return True

    def _give_up(self, why: str) -> str:
        """First time: come back to it after the other targets (likely from another side). Second: skip."""
        tid = self.target.id
        if tid not in self._deferred:
            self._deferred.add(tid)
            self.log(f"[NAV] '{self.target.name}': {why} - will come back to it after the others.")
            self._release()
            self.target = None
            return "DEFERRED"
        self.log(f"[NAV] '{self.target.name}': {why} again - skipping it (Retry skipped re-enables it).")
        self._finish_target("skipped")
        return "SKIPPED"

    def _on_stuck(self, now: float) -> str:
        self._samples.clear()
        self._attempts += 1
        if self._attempts >= self.cfg["max_stuck_attempts"]:
            return self._give_up(f"stuck {self._attempts - 1}x")
        mounted = bool(self.last and self.last.mounted)
        self._maneuver = self._build_maneuver(self._attempts, mounted)
        self._step_idx = -1
        self._step_deadline = now
        self.log(f"[NAV] Stuck (attempt {self._attempts}/{self.cfg['max_stuck_attempts'] - 1}) - "
                 f"{self._maneuver_name}.")
        return self._run_maneuver(now)

    @staticmethod
    def _hold(keys, seconds, tap=None) -> Dict:
        return {"kind": "hold", "keys": set(keys), "seconds": seconds, "tap": tap}

    @staticmethod
    def _face(offset_deg, timeout=2.5) -> Dict:
        """Turn (in place) until facing target bearing + offset (+ = clockwise/right of the target)."""
        return {"kind": "face", "offset": math.radians(offset_deg), "seconds": timeout}

    def _build_maneuver(self, attempt: int, mounted: bool) -> List[Dict]:
        """Escalating: leap/jump, then ride along the obstacle on alternating sides, further each time.
        The raptor barely reverses, so it never backs up while mounted."""
        if self._unstuck_side is None:
            self._unstuck_side = self.rng.choice([1, -1])
        side = self._unstuck_side
        back = [] if mounted else [self._hold({"move_back"}, 0.8)]
        if attempt == 1:
            self._maneuver_name = "leaping" if mounted else "jumping"
            if mounted:   # raptor leap: hold jump to charge, release to leap
                return [self._hold({"move_forward", "jump"}, 0.7), self._hold({"move_forward"}, 1.2)]
            return [self._hold({"move_forward"}, 0.9, tap="jump")]
        if attempt in (2, 3):
            sgn = side if attempt == 2 else -side
            self._maneuver_name = f"going around on the {'right' if sgn > 0 else 'left'}"
            return back + [self._face(75 * sgn), self._hold({"move_forward"}, 2.5 if attempt == 2 else 4.0)]
        if mounted and not self._no_mount:
            self._no_mount = True
            self._maneuver_name = "dismounting to try on foot"
            return [self._hold(set(), 0.4, tap="mount"), self._hold(set(), 1.0)]
        sgn = side if attempt % 2 == 0 else -side
        self._maneuver_name = f"wide detour on the {'right' if sgn > 0 else 'left'}"
        return back + [self._face(110 * sgn), self._hold({"move_forward"}, 6.0, tap="jump")]

    def _run_maneuver(self, now: float) -> str:
        if 0 <= self._step_idx < len(self._maneuver):
            step = self._maneuver[self._step_idx]
            if step["kind"] == "face" and now < self._step_deadline:
                if not self._face_tick(step["offset"]):
                    return "UNSTUCK"
            elif now < self._step_deadline:
                return "UNSTUCK"
        self._step_idx += 1
        if self._step_idx >= len(self._maneuver):
            self._maneuver = None
            self._apply(set())
            return "UNSTUCK"
        step = self._maneuver[self._step_idx]
        self._step_deadline = now + step["seconds"]
        if step["kind"] == "face":
            self._face_tick(step["offset"])
        else:
            self._apply(step["keys"])
            if step["tap"]:
                self.inp.tap(step["tap"])
        return "UNSTUCK"

    def _face_tick(self, offset: float) -> bool:
        """One tick of turning toward target bearing + offset. True once within 15 degrees."""
        err = wrap_angle(self.err + offset)
        if abs(err) < math.radians(15):
            self._apply(set())
            return True
        right = (err > 0) != bool(self.cfg["invert_turn"])
        self._apply({"turn_right" if right else "turn_left"})
        return False

    def _apply(self, keys: Set[str]) -> None:
        for k in self._held - keys:
            self.inp.key_up(k)
        self._held &= keys
        for k in keys - self._held:
            if self.inp.key_down(k):
                self._held.add(k)

    def _release(self) -> None:
        self.inp.release_all()
        self._held.clear()
