"""
Screen-Driven Rotation: off-cooldown priority, or opener + loop.

A rotation is one small YAML file per spec: config/rotations/{profession}_{spec}.yaml

Priority mode (e.g. Mechanist):

    priority: [2, 3, 4, 5, 7, 0]   # skill-bar numbers; the first READY one is pressed
    double_tap:   {5: 0.25}        # ground-targeted skills: press twice, N seconds apart
    no_interrupt: {2: 0.75}        # cancelled if anything is cast over it: hold N seconds

Sequence mode (e.g. Deadeye) adds an opener and a loop of blocks:

    opener: [5, f1, f2, {skill: f2, wait: {malice: 5}}, 1]   # once per fight, in order
    loop:                                                     # pick a block, run it, repeat
      - name: Mercy reset
        when: [f1, 8]              # chosen when these skills are all ready (first match wins)
        steps: [3, f1, 3, ...]
    instant: [f1, f2, 8]           # pressed even mid-cast; the sequence moves on once pressed
    costs:   {3: {initiative: 4}}  # waits until affordable; counts as cast once the amount drops

A step is a skill, {skill, wait: {resource: min}, after: {skill: seconds}}, or {auto: N}
(press nothing for N auto-attacks). Resources are the spec file's resource / extra_resources.

Readiness comes only from the on-screen cooldown detector (no timers), so cooldown
reduction effects are handled automatically. A skill "went off" once its slot shows a
cooldown or a resource it costs drops.

Pacing follows the game's skill queue: while one skill is casting, ONE more press may
queue behind it; further presses wait until the casting skill went off. Nothing is ever
pressed while a no_interrupt skill is casting (instant skills excepted). A skill that
never goes off (out of range, no target) is skipped briefly instead of spammed.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import yaml

from behaviors.base import BaseBehavior
from core.cooldown_detector import UniversalCooldownDetector
from core.detector import VisualDetector
from core.input_controller import InputController
from core.resource_detector import UniversalResourceDetector
from profiles.base_profile import BaseCharacterProfile

ROTATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "rotations")

# Skill-bar number -> cooldown detector slot
SKILL_SLOTS = {
    "1": "weapon_1", "2": "weapon_2", "3": "weapon_3", "4": "weapon_4", "5": "weapon_5",
    "6": "heal", "7": "utility_1", "8": "utility_2", "9": "utility_3", "0": "elite",
    "swap": "weapon_swap",
    "f1": "mech_f1", "f2": "mech_f2", "f3": "mech_f3", "f4": "mech_f4", "f5": "mech_f5",
}

MAX_WAIT_FOR_COOLDOWN = 1.2   # seconds a press may stay "outstanding" without going off
FAILED_SKILL_BACKOFF = 1.5    # seconds to skip a skill that was pressed but never went off
MAX_QUEUED = 2                # the casting skill + one queued behind it (the game's queue depth)
STEP_TIMEOUT = 6.0            # a sequence step stuck this long is pressed anyway (if ready) or skipped
NEW_FIGHT_GAP = 2.0           # seconds without engine ticks (F10 / tabbed out) before the opener restarts
WAIT_NOTE_AFTER = 1.0         # a step waiting this long logs (once) what it's waiting for


@dataclass
class Step:
    skill: Optional[str] = None                             # None = auto-attack pause
    autos: int = 0
    wait: Dict[str, float] = field(default_factory=dict)    # resource -> minimum amount
    after: Dict[str, float] = field(default_factory=dict)   # skill -> seconds since it last went off

    def describe(self) -> str:
        return self.skill if self.skill else f"auto x{self.autos}"


@dataclass
class Block:
    name: str
    when: List[str]
    steps: List[Step]


@dataclass
class SimpleRotation:
    name: str
    priority: List[str] = field(default_factory=list)
    double_tap: Dict[str, float] = field(default_factory=dict)
    no_interrupt: Dict[str, float] = field(default_factory=dict)
    instant: Set[str] = field(default_factory=set)
    costs: Dict[str, Dict[str, float]] = field(default_factory=dict)
    opener: List[Step] = field(default_factory=list)
    loop: List[Block] = field(default_factory=list)
    auto_attack_seconds: float = 0.8

    @property
    def sequenced(self) -> bool:
        return bool(self.opener or self.loop)

    def resource_names(self) -> Set[str]:
        names = {r for c in self.costs.values() for r in c}
        for step in self.opener + [s for b in self.loop for s in b.steps]:
            names.update(step.wait)
        return names

    def summary(self) -> str:
        if not self.sequenced:
            return f"priority {' > '.join(self.priority)}"
        return f"opener ({len(self.opener)} steps), loop blocks: {', '.join(b.name for b in self.loop)}"


def rotation_path(profession: str, spec: str) -> str:
    p = profession.lower().strip().replace(" ", "_")
    s = spec.lower().strip().replace(" ", "_")
    return os.path.join(ROTATIONS_DIR, f"{p}_{s}.yaml")


def parse_simple_rotation(data: Dict[str, Any], default_name: str = "Rotation") -> SimpleRotation:
    """Validates a rotation dict. Raises ValueError with a readable message on mistakes."""
    def skill(v) -> str:
        k = str(v).strip().lower()
        if k not in SKILL_SLOTS:
            raise ValueError(f"'{v}' is not a skill-bar number (use 1-9, 0, f1-f5, or swap)")
        return k

    def skill_list(v, where: str) -> List[str]:
        if not isinstance(v, list):
            raise ValueError(f"'{where}' must be a list of skill-bar numbers, e.g. [2, 3, f1]")
        return [skill(s) for s in v]

    def seconds_map(key: str) -> Dict[str, float]:
        raw = data.get(key) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"'{key}' must map skill numbers to seconds, e.g. {{5: 0.25}}")
        return {skill(k): float(v) for k, v in raw.items()}

    def amounts(raw, where: str) -> Dict[str, float]:
        if not isinstance(raw, dict):
            raise ValueError(f"'{where}' must map resource names to amounts, e.g. {{malice: 5}}")
        return {str(k).strip().lower(): float(v) for k, v in raw.items()}

    def step(raw, where: str) -> Step:
        if not isinstance(raw, dict):
            return Step(skill=skill(raw))
        unknown = set(raw) - {"skill", "wait", "after", "auto"}
        if unknown:
            raise ValueError(f"{where}: unknown step key(s) {sorted(unknown)} (use skill, wait, after, auto)")
        if "auto" in raw:
            if "skill" in raw:
                raise ValueError(f"{where}: a step is either a skill or an auto-attack pause, not both")
            return Step(autos=int(raw["auto"]))
        if "skill" not in raw:
            raise ValueError(f"{where}: step needs a 'skill' (or 'auto')")
        after = raw.get("after") or {}
        if not isinstance(after, dict):
            raise ValueError(f"{where}: 'after' must map skill numbers to seconds, e.g. {{1: 3}}")
        return Step(
            skill=skill(raw["skill"]),
            wait=amounts(raw.get("wait") or {}, f"{where} wait"),
            after={skill(k): float(v) for k, v in after.items()},
        )

    def steps(raw, where: str) -> List[Step]:
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"'{where}' must be a non-empty list of steps")
        return [step(s, f"{where} step {i + 1}") for i, s in enumerate(raw)]

    opener = steps(data["opener"], "opener") if data.get("opener") else []

    loop: List[Block] = []
    raw_loop = data.get("loop")
    if raw_loop:
        if isinstance(raw_loop, list) and all(isinstance(b, dict) and "steps" in b for b in raw_loop):
            for i, b in enumerate(raw_loop):
                name = str(b.get("name") or f"Block {i + 1}")
                loop.append(Block(name, skill_list(b.get("when") or [], f"{name} when"), steps(b["steps"], name)))
        else:
            loop.append(Block("Loop", [], steps(raw_loop, "loop")))

    raw_priority = data.get("priority") or []
    if not opener and not loop and (not isinstance(raw_priority, list) or not raw_priority):
        raise ValueError("'priority' must be a list of skill-bar numbers, e.g. [2, 3, 4, 5, 7, 0] "
                         "(or give an 'opener' / 'loop')")
    priority = skill_list(raw_priority, "priority")

    raw_costs = data.get("costs") or {}
    if not isinstance(raw_costs, dict):
        raise ValueError("'costs' must map skill numbers to resources, e.g. {3: {initiative: 4}}")

    return SimpleRotation(
        name=str(data.get("name") or default_name),
        priority=priority,
        double_tap=seconds_map("double_tap"),
        no_interrupt=seconds_map("no_interrupt"),
        instant=set(skill_list(data.get("instant") or [], "instant")),
        costs={skill(k): amounts(v, f"costs {k}") for k, v in raw_costs.items()},
        opener=opener,
        loop=loop,
        auto_attack_seconds=float(data.get("auto_attack_seconds", 0.8)),
    )


def load_simple_rotation(profession: str, spec: str) -> Optional[SimpleRotation]:
    """Loads config/rotations/{profession}_{spec}.yaml, or None if there isn't one."""
    path = rotation_path(profession, spec)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return parse_simple_rotation(data, default_name=f"{profession} {spec}".title())


def check_resources(rotation: SimpleRotation, resources: UniversalResourceDetector) -> None:
    """Raises ValueError if the rotation names a resource the spec file doesn't define."""
    known = set(resources.extras)
    if resources.resource_type != "none":
        known.add(resources.resource_name)
    missing = rotation.resource_names() - known
    if missing:
        raise ValueError(f"unknown resource(s) {sorted(missing)}; this spec has {sorted(known) or 'none'}")


@dataclass
class _Press:
    skill: str
    pressed_at: float
    hold: float          # no_interrupt: minimum seconds before anything else may be pressed
    spent_from: Dict[str, float] = field(default_factory=dict)   # cost resources at press time
    went_off: bool = False


class SimpleRotationBehavior(BaseBehavior):
    """Presses the next skill (priority or sequence), following the game's one-deep skill queue."""

    def __init__(
        self,
        rotation: SimpleRotation,
        cooldown_detector: UniversalCooldownDetector,
        resources: Optional[UniversalResourceDetector] = None,
        clock: Callable[[], float] = time.time,
        log: Callable[[str], None] = print,
    ):
        super().__init__(name=f"{rotation.name}Rotation", priority=100, cooldown_seconds=0.0, cooldown_jitter_ratio=0.0)
        self.rotation = rotation
        self.cooldown_detector = cooldown_detector
        self.resources = resources
        self.clock = clock
        self.log = log
        self.outstanding: List[_Press] = []    # pressed, not yet seen going off
        self.backoff_until: Dict[str, float] = {}
        self.last_went_off: Dict[str, float] = {}
        self.next_skill: Optional[str] = None
        self._amounts: Dict[str, float] = {}   # resource readings for the current tick
        self._last_tick: Optional[float] = None
        self.reset()

    def reset(self) -> None:
        self.outstanding.clear()
        self.backoff_until.clear()
        self.last_went_off.clear()
        self.steps: List[Step] = list(self.rotation.opener)
        self.block: Optional[str] = "Opener" if self.rotation.opener else None
        self.step_i = 0
        self.step_started: Optional[float] = None
        self.step_press: Optional[_Press] = None
        self.wait_noted = False

    def is_on_cooldown(self, current_time: float) -> bool:
        return False   # pacing is handled by the skill-queue logic below, every engine tick

    # -- screen readings ---------------------------------------------------------------
    def _status(self, frame, skill: str):
        return self.cooldown_detector.get_slot_status(frame, SKILL_SLOTS[skill])

    def _is_ready(self, frame, skill: str) -> bool:
        st = self._status(frame, skill)
        return bool(st and st.is_ready)

    def _shows_cooldown(self, frame, skill: str) -> bool:
        st = self._status(frame, skill)
        return bool(st and not st.raw_is_ready)

    def _amount(self, frame, resource: str) -> float:
        if resource not in self._amounts:
            self._amounts[resource] = self.resources.get_resource_state(frame, resource).current_value
        return self._amounts[resource]

    def _has(self, frame, needs: Dict[str, float]) -> bool:
        return all(self._amount(frame, r) >= n for r, n in needs.items())

    def _spent(self, frame, p: _Press) -> bool:
        return any(self._amount(frame, r) < v for r, v in p.spent_from.items())

    # -- decision ----------------------------------------------------------------------
    def _update_outstanding(self, frame, now: float) -> None:
        still = []
        for p in self.outstanding:
            if not p.went_off and (self._shows_cooldown(frame, p.skill) or self._spent(frame, p)):
                p.went_off = True
                self.last_went_off[p.skill] = now
            elapsed = now - p.pressed_at
            if p.went_off and elapsed >= p.hold:
                continue                                   # done
            if elapsed >= max(MAX_WAIT_FOR_COOLDOWN, p.hold + 1.0):
                if not p.went_off:
                    self.backoff_until[p.skill] = now + FAILED_SKILL_BACKOFF
                    self.log(f"[Rotation] Skill {p.skill} didn't go off (out of range / no target?); skipping it briefly.")
                continue
            still.append(p)
        self.outstanding = still

    def _queue_full(self) -> bool:
        if any(p.skill in self.rotation.no_interrupt for p in self.outstanding):
            return True
        return len(self.outstanding) >= MAX_QUEUED

    def _can_press(self, frame, skill: str, now: float) -> bool:
        return now >= self.backoff_until.get(skill, 0.0) and self._is_ready(frame, skill)

    def evaluate_condition(self, frame, detector: VisualDetector) -> Tuple[bool, Any]:
        self.next_skill = None
        self._amounts = {}
        if frame is None or getattr(frame, "size", 0) == 0:
            return False, None
        now = self.clock()
        if self.rotation.sequenced and self._last_tick is not None and now - self._last_tick > NEW_FIGHT_GAP:
            self.log(f"[{self.rotation.name}] New fight: starting from the opener")
            self.reset()
        self._last_tick = now
        self._update_outstanding(frame, now)
        if self.rotation.sequenced:
            return self._evaluate_sequence(frame, now)
        return self._evaluate_priority(frame, now)

    def _evaluate_priority(self, frame, now: float) -> Tuple[bool, Any]:
        if self._queue_full():
            return False, None
        busy = {p.skill for p in self.outstanding}
        for skill in self.rotation.priority:
            if skill in busy or not self._can_press(frame, skill, now):
                continue
            if self._has(frame, self.rotation.costs.get(skill, {})):
                self.next_skill = skill
                return True, skill
        return False, None

    def _advance(self) -> None:
        self.step_i += 1
        self.step_started = None
        self.step_press = None
        self.wait_noted = False

    def _waiting(self, now: float, why: str) -> Tuple[bool, Any]:
        if not self.wait_noted and now - self.step_started >= WAIT_NOTE_AFTER:
            self.wait_noted = True
            step = self.steps[self.step_i]
            self.log(f"[{self.rotation.name}] {self.block} step {self.step_i + 1} ({step.describe()}): waiting, {why}")
        return False, None

    def _pick_block(self, frame, now: float) -> bool:
        for b in self.rotation.loop:
            if all(self._can_press(frame, s, now) for s in b.when):
                self.steps, self.step_i, self.block = b.steps, 0, b.name
                self.log(f"[{self.rotation.name}] {b.name}")
                return True
        return False

    def _evaluate_sequence(self, frame, now: float) -> Tuple[bool, Any]:
        for _ in range(len(self.steps) + 2):           # finished steps fall through to the next
            if self.step_i >= len(self.steps):
                self.block = None
                if not self._pick_block(frame, now):
                    return False, None                 # nothing ready: let auto-attacks run
            step = self.steps[self.step_i]
            if self.step_started is None:
                self.step_started = now

            if step.skill is None:                     # auto-attack pause
                if now - self.step_started < step.autos * self.rotation.auto_attack_seconds:
                    return False, None
                self._advance()
                continue

            p = self.step_press
            if p is not None and p.went_off:
                self._advance()
                continue
            if p is not None and p in self.outstanding:
                return self._waiting(now, "pressed but not seen going off (no cooldown, no resource drop)")

            skill = step.skill
            instant = skill in self.rotation.instant
            if not instant and self._queue_full():
                return self._waiting(now, "skill queue busy: " + ", ".join(p.skill for p in self.outstanding))
            timed_out = now - self.step_started >= STEP_TIMEOUT
            if not self._can_press(frame, skill, now):
                if timed_out:
                    self.log(f"[{self.rotation.name}] {self.block}: skill {skill} never became ready; skipping it")
                    self._advance()
                    continue
                backoff = now < self.backoff_until.get(skill, 0.0)
                return self._waiting(now, "backing off after a failed press" if backoff else "not ready on screen")
            waits = dict(self.rotation.costs.get(skill, {}))
            waits.update(step.wait)
            met = self._has(frame, waits) and all(
                now - self.last_went_off.get(s, float("-inf")) >= secs for s, secs in step.after.items()
            )
            if not met:
                if not timed_out:
                    have = ", ".join(f"{r} {self._amount(frame, r):g}/{n:g}" for r, n in waits.items())
                    left = {s: secs - (now - self.last_went_off.get(s, float("-inf"))) for s, secs in step.after.items()}
                    since = ", ".join(f"{t:.1f}s more after skill {s}" for s, t in left.items() if t > 0)
                    return self._waiting(now, "; ".join(x for x in (have, since) if x))
                self.log(f"[{self.rotation.name}] {self.block}: gave up waiting on skill {skill}'s conditions; pressing it")
            self.next_skill = skill
            return True, skill
        return False, None

    def execute_action(self, input_controller: InputController) -> bool:
        skill = self.next_skill
        self.next_skill = None
        if not skill:
            return False
        gap = self.rotation.double_tap.get(skill)
        if gap is not None:
            ok = input_controller.press_key(skill, double_tap=True, double_tap_gap=gap)
        else:
            ok = input_controller.press_key(skill)
        if not ok:
            return False
        now = self.clock()
        instant = skill in self.rotation.instant
        hold = self.rotation.no_interrupt.get(skill, 0.0)
        if instant:
            self.last_went_off[skill] = now
            if self.rotation.sequenced:
                self._advance()
        else:
            spent_from = {r: self._amounts[r] for r in self.rotation.costs.get(skill, {}) if r in self._amounts}
            press = _Press(skill, now, hold, spent_from)
            self.outstanding.append(press)
            if self.rotation.sequenced:
                self.step_press = press
        extra = f" (double-tap, {gap:.2f}s)" if gap is not None else ""
        extra += f" (no-interrupt {hold:.2f}s)" if hold else ""
        extra += " (queued)" if len(self.outstanding) > 1 else ""
        extra += " (instant)" if instant else ""
        where = f"[{self.block}] " if self.rotation.sequenced and self.block else ""
        self.log(f"[{self.rotation.name}] {where}Skill {skill}{extra}")
        return True


class SimpleRotationProfile(BaseCharacterProfile):
    """Profile wrapper so the engine/GUI can run a simple rotation file."""

    def __init__(self, rotation: SimpleRotation, profession: str = "", spec: str = ""):
        super().__init__(name=rotation.name, signature_template=None)
        resources = UniversalResourceDetector(profession=profession, spec=spec)
        check_resources(rotation, resources)
        self.rotation_behavior = SimpleRotationBehavior(
            rotation, UniversalCooldownDetector(profession=profession, spec=spec), resources
        )

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(self.rotation_behavior)

    def reset_rotation(self) -> None:
        self.rotation_behavior.reset()
