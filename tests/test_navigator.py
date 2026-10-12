"""Navigator against a tiny 2-D world sim: W moves along the heading, A/D turn, X toggles the mount."""

import math
import os
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gw2_map_data import Target
from core.mumble_link import NavState
from core.nav_progress import NavProgress
from core.navigator import Navigator

DT = 0.05


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeInput:
    def __init__(self):
        self.held = set()
        self.taps = []
        self.release_calls = 0

    def is_game_focused(self):
        return True

    def key_down(self, k):
        self.held.add(k)
        return True

    def key_up(self, k):
        self.held.discard(k)

    def release_all(self):
        self.release_calls += 1
        self.held.clear()

    def tap(self, k):
        self.taps.append(k)
        return True


class World:
    """Advances physics by DT on every read(), using whatever keys are held."""

    def __init__(self, clock, inp, pos=(0.0, 0.0), heading=0.0, wall_x=None, turn="turn", wall_y=None):
        self.clock, self.inp = clock, inp
        self.pos, self.heading = list(pos), heading
        self.mounted = False
        self.in_combat = False
        self.map_open = False
        self.wall_x = wall_x                    # impassable vertical line...
        self.wall_y = wall_y                    # ...or only the segment wall_y[0] <= y <= wall_y[1] (a fence)
        self.turn_rate = math.radians(200)      # rad/s
        self.turn = turn                        # "turn" | "reversed" | "strafe" (what A/D do in game)
        self._taps_seen = 0

    def read(self):
        self.clock.t += DT
        for k in self.inp.taps[self._taps_seen:]:
            if k == "mount" and not self.in_combat:
                self.mounted = not self.mounted
        self._taps_seen = len(self.inp.taps)
        held = self.inp.held
        speed = 25.0 if self.mounted else 12.0
        side = ("turn_right" in held) - ("turn_left" in held)
        if self.turn != "strafe":
            self.heading += side * self.turn_rate * DT * (-1 if self.turn == "reversed" else 1)
        step = speed * DT * (("move_forward" in held) - 0.5 * ("move_back" in held))
        nx = self.pos[0] + step * math.cos(self.heading)
        ny = self.pos[1] + step * math.sin(self.heading)
        if self.turn == "strafe":
            nx += speed * DT * side * math.cos(self.heading + math.pi / 2)
            ny += speed * DT * side * math.sin(self.heading + math.pi / 2)
        crosses = self.wall_x is not None and (self.pos[0] < self.wall_x) != (nx < self.wall_x)
        if crosses and self.wall_y is not None and not (self.wall_y[0] <= ny <= self.wall_y[1]):
            crosses = False
        if not crosses:
            self.pos = [nx, ny]
        return NavState(tick=int(self.clock.t / DT), map_id=15, pos=tuple(self.pos), heading_rad=self.heading,
                        in_combat=self.in_combat, mounted=self.mounted, map_open=self.map_open,
                        textbox_focused=False, game_focused=True, character="Tester")


class FakeCombat:
    def __init__(self):
        self.begun = self.ended = 0

    def begin(self):
        self.begun += 1

    def end(self):
        self.ended += 1


TARGETS = [
    Target("poi:1", "waypoint", "Near WP", (60.0, 40.0)),
    Target("poi:2", "landmark", "Mid POI", (-80.0, 90.0)),
    Target("poi:3", "landmark", "Far POI", (300.0, -200.0)),
    Target("poi:4", "vista", "Vista", (10.0, 10.0)),          # not an enabled kind
]


class TestNavigator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.progress = NavProgress(os.path.join(self.tmp, "progress.json"))
        self.clock = Clock()
        self.inp = FakeInput()
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def make(self, world, targets=TARGETS, combat=None, **cfg):
        config = {"mount_min_distance": 10_000}
        config.update(cfg)
        return Navigator(world, self.inp, self.progress, config, targets_for_map=lambda m: targets,
                         combat=combat, log=self.logs.append, clock=self.clock, rng=random.Random(1))

    def run_until(self, nav, pred, max_ticks=20_000):
        for _ in range(max_ticks):
            state = nav.step()
            if pred(state):
                return state
        self.fail(f"condition not reached; state={nav.state} logs={self.logs[-5:]}")

    def test_visits_targets_nearest_first(self):
        world = World(self.clock, self.inp, heading=math.pi)   # facing away from everything
        nav = self.make(world)
        visited = []
        orig = self.progress.mark
        self.progress.mark = lambda c, m, tid, st: (visited.append((tid, st)), orig(c, m, tid, st))
        self.run_until(nav, lambda s: s == "DONE")
        self.assertEqual(visited, [("poi:1", "done"), ("poi:2", "done"), ("poi:3", "done")])
        self.assertEqual(self.progress.done("Tester", 15), {"poi:1", "poi:2", "poi:3"})
        self.assertEqual(self.inp.held, set())

    def test_resumes_from_progress(self):
        self.progress.mark("Tester", 15, "poi:1", "done")
        nav = self.make(World(self.clock, self.inp))
        nav.step()
        self.assertEqual(nav.target.id, "poi:2")

    def test_mounts_for_long_legs(self):
        world = World(self.clock, self.inp)
        nav = self.make(world, targets=[TARGETS[2]], mount_min_distance=120)
        self.run_until(nav, lambda s: s == "MOVING")
        self.assertEqual(self.inp.taps, ["mount"])
        self.assertTrue(world.mounted)
        self.run_until(nav, lambda s: s == "DONE")

    def test_wall_gets_skipped(self):
        world = World(self.clock, self.inp, wall_x=30.0)
        nav = self.make(world, targets=[Target("poi:9", "landmark", "Behind wall", (100.0, 0.0))])
        self.run_until(nav, lambda s: s == "DONE")
        self.assertIn("poi:9", self.progress.excluded("Tester", 15))
        self.assertNotIn("poi:9", self.progress.done("Tester", 15))
        self.assertIn("jump", self.inp.taps)
        self.assertTrue(any("skipping it" in m for m in self.logs))
        self.assertEqual(self.inp.held, set())

    def test_gets_around_a_fence(self):
        for mounted_leg in (False, True):
            with self.subTest(mounted=mounted_leg):
                self.tearDown()
                self.setUp()
                world = World(self.clock, self.inp, wall_x=60.0, wall_y=(-25.0, 25.0))
                target = Target("poi:7", "landmark", "Past fence", (300.0 if mounted_leg else 140.0, 0.0))
                nav = self.make(world, targets=[target], mount_min_distance=120 if mounted_leg else 10_000)
                self.run_until(nav, lambda s: s == "DONE")
                self.assertEqual(self.progress.done("Tester", 15), {"poi:7"}, self.logs)

    def test_blocked_target_is_deferred_before_skipping(self):
        world = World(self.clock, self.inp, wall_x=30.0)
        blocked = Target("poi:9", "landmark", "Behind wall", (100.0, 0.0))
        open_ = Target("poi:8", "landmark", "Open", (-150.0, 0.0))
        nav = self.make(world, targets=[blocked, open_])
        order = []
        orig = self.progress.mark
        self.progress.mark = lambda c, m, tid, st: (order.append((tid, st)), orig(c, m, tid, st))
        self.run_until(nav, lambda s: s == "DONE")
        self.assertEqual(order, [("poi:8", "done"), ("poi:9", "skipped")])
        self.assertTrue(any("come back to it" in m for m in self.logs))

    def test_mounted_unstuck_leaps_and_faces_sideways(self):
        world = World(self.clock, self.inp, wall_x=30.0)
        nav = self.make(world, targets=[Target("poi:9", "landmark", "Behind wall", (300.0, 0.0))],
                        mount_min_distance=120)
        jump_held = False
        for _ in range(2000):
            nav.step()
            jump_held |= "jump" in self.inp.held
            if "going around" in " ".join(self.logs):
                break
        self.assertTrue(jump_held, "raptor leap holds jump instead of tapping it")
        self.assertNotIn("move_back", self.inp.held)
        for _ in range(60):                      # face step: turn ~75 deg off the target, then ride
            nav.step()
            if self.inp.held == {"move_forward"}:
                break
        off = math.degrees(abs(nav.err))
        self.assertTrue(55 <= off <= 95, off)

    def test_combat_hands_over_and_resumes(self):
        world = World(self.clock, self.inp)
        combat = FakeCombat()
        nav = self.make(world, targets=[TARGETS[2]], combat=combat)
        self.run_until(nav, lambda s: s == "MOVING")
        world.in_combat = True
        self.assertEqual(nav.step(), "COMBAT")
        self.assertEqual(combat.begun, 1)
        self.assertEqual(self.inp.held, set(), "movement keys released for the rotation")
        for _ in range(20):
            self.assertEqual(nav.step(), "COMBAT")
        world.in_combat = False
        self.assertIn(nav.step(), ("MOVING", "TURNING"))
        self.assertEqual(combat.ended, 1)

    def test_pauses_when_map_open(self):
        world = World(self.clock, self.inp)
        nav = self.make(world)
        self.run_until(nav, lambda s: s == "MOVING")
        world.map_open = True
        self.assertEqual(nav.step(), "PAUSED")
        self.assertEqual(self.inp.held, set())

    def test_skip_request(self):
        nav = self.make(World(self.clock, self.inp))
        nav.step()
        nav.request("skip")
        nav.step()
        self.assertIn("poi:1", self.progress.excluded("Tester", 15))
        self.assertEqual(nav.target.id, "poi:2")

    def test_target_behind_does_not_flip_flop(self):
        world = World(self.clock, self.inp, heading=math.pi)          # target dead astern
        nav = self.make(world, targets=[Target("poi:5", "landmark", "Behind", (100.0, 0.0))])
        turn_keys = []
        for _ in range(20):
            nav.step()
            turn_keys.append(nav._turn_key)
        self.assertEqual(len({k for k in turn_keys if k}), 1, turn_keys)
        self.run_until(nav, lambda s: s == "DONE")

    def test_strafe_binds_stop_navigation(self):
        world = World(self.clock, self.inp, heading=math.pi, turn="strafe")
        nav = self.make(world, targets=[Target("poi:5", "landmark", "Behind", (100.0, 0.0))])
        self.assertEqual(self.run_until(nav, lambda s: s == "TURN_FAIL", max_ticks=200), "TURN_FAIL")
        self.assertIn("STRAFE", self.logs[-1])
        self.assertEqual(self.inp.held, set())

    def test_reversed_turning_stops_navigation(self):
        world = World(self.clock, self.inp, heading=math.pi / 2, turn="reversed")
        nav = self.make(world, targets=[Target("poi:5", "landmark", "East", (100.0, 0.0))])
        self.run_until(nav, lambda s: s == "TURN_FAIL", max_ticks=200)
        self.assertIn("invert_turn", self.logs[-1])

    def test_invert_turn_fixes_reversed_turning(self):
        world = World(self.clock, self.inp, heading=math.pi / 2, turn="reversed")
        nav = self.make(world, targets=[Target("poi:5", "landmark", "East", (100.0, 0.0))], invert_turn=True)
        self.run_until(nav, lambda s: s == "DONE")

    def test_trace_logs_state_changes(self):
        lines = []
        nav = Navigator(World(self.clock, self.inp), self.inp, self.progress, {"mount_min_distance": 10_000},
                        targets_for_map=lambda m: TARGETS, log=self.logs.append, clock=self.clock,
                        trace=lines.append)
        self.run_until(nav, lambda s: s == "MOVING")
        self.assertTrue(any("->MOVING" in l and "dist=" in l and "keys=" in l for l in lines))

    def test_run_releases_keys_on_stop(self):
        nav = self.make(World(self.clock, self.inp))
        ticks = iter(range(30))
        result = nav.run(should_stop=lambda: next(ticks, None) is None, sleep=lambda s: None)
        self.assertEqual(result, "STOPPED")
        self.assertEqual(self.inp.held, set())


if __name__ == "__main__":
    unittest.main()
