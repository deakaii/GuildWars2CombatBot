"""
Tests for the simple priority rotation (profiles/simple_rotation.py), using the
Engineer/Mechanist rotation file, a simulated clock, simulated slot readings and a
recording input controller (no game, no real key presses).
"""

import os
import sys
import unittest
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from profiles.simple_rotation import (
    SKILL_SLOTS, SimpleRotationBehavior, load_simple_rotation, parse_simple_rotation,
)

TICK = 0.05   # engine tick (settings.yaml timing.tick_interval)


class FakeDetector:
    """Slot readings the test controls: True = ready, False = on cooldown."""

    def __init__(self):
        self.ready = {slot: True for slot in SKILL_SLOTS.values()}

    def get_slot_status(self, frame, slot_id):
        r = self.ready[slot_id]
        return SimpleNamespace(is_ready=r, raw_is_ready=r)


class FakeInput:
    def __init__(self, clock):
        self.clock = clock
        self.presses = []   # (time, skill, double_tap_gap)

    def press_key(self, key, double_tap=False, double_tap_gap=None):
        self.presses.append((round(self.clock.t, 2), key, double_tap_gap if double_tap else None))
        return True


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


FRAME = np.zeros((10, 10, 3), np.uint8)


class TestSimpleRotation(unittest.TestCase):

    def setUp(self):
        self.rotation = load_simple_rotation("Engineer", "Mechanist")
        self.clock = Clock()
        self.det = FakeDetector()
        self.inp = FakeInput(self.clock)
        self.bot = SimpleRotationBehavior(self.rotation, self.det, clock=self.clock, log=lambda m: None)

    def tick(self):
        matched, _ = self.bot.evaluate_condition(FRAME, None)
        if matched:
            self.bot.execute_action(self.inp)
        self.clock.t = round(self.clock.t + TICK, 4)

    def pressed(self):
        return [k for _, k, _ in self.inp.presses]

    def set_cd(self, skill, on=True):
        self.det.ready[SKILL_SLOTS[skill]] = not on

    def test_rotation_file_loads(self):
        r = self.rotation
        self.assertEqual(r.priority, ["2", "3", "4", "5", "7", "0"])
        self.assertEqual(r.double_tap, {"5": 0.25})
        self.assertEqual(r.no_interrupt, {"2": 0.75})

    def test_nothing_is_cast_over_two(self):
        self.tick()                          # 2 first (highest priority, everything ready)
        self.set_cd("2")                     # 2 shows its cooldown immediately...
        for _ in range(14):                  # ...but nothing is pressed for its 0.75 s hold
            self.tick()
        self.assertEqual(self.pressed(), ["2"])
        for _ in range(2):
            self.tick()
        self.assertEqual(self.pressed()[:2], ["2", "3"], "3 goes as soon as the hold ends")

    def test_one_press_queues_behind_a_cast_but_not_two(self):
        self.set_cd("2")
        for _ in range(6):                   # 3 is casting (no cooldown shown yet)
            self.tick()
        self.assertEqual(self.pressed(), ["3", "4"], "one skill queues behind 3, no more")
        self.set_cd("3")                     # 3 finishes -> 4 is casting -> another may queue
        self.tick()
        self.assertEqual(self.pressed(), ["3", "4", "5"])
        self.assertEqual(self.inp.presses[2][2], 0.25, "5 is double-tapped 0.25 s apart")

    def test_ready_skill_is_pressed_on_the_next_tick(self):
        for s in ("2", "3", "4", "5", "7", "0"):
            self.set_cd(s)
        for _ in range(10):
            self.tick()
        self.assertEqual(self.pressed(), [])
        self.set_cd("4", on=False)           # 4 comes off cooldown
        t_ready = self.clock.t
        self.tick()
        self.assertEqual(self.inp.presses[0][:2], (t_ready, "4"))

    def test_cooldown_reduction_is_followed_not_a_timer(self):
        """A 20 s cooldown that ends at 17 s on screen is used at 17 s."""
        for s in ("3", "4", "5", "7", "0"):
            self.set_cd(s)
        self.tick()                          # presses 2
        self.set_cd("2")
        while self.clock.t < 17.0:
            self.tick()
        self.set_cd("2", on=False)           # screen shows 2 ready early (cooldown reduced)
        self.tick()
        self.assertEqual(self.pressed(), ["2", "2"])
        self.assertAlmostEqual(self.inp.presses[1][0], 17.0, delta=TICK)

    def test_skill_that_never_goes_off_is_skipped_briefly(self):
        for s in ("3", "4", "5", "7", "0"):
            self.set_cd(s)
        for _ in range(60):                  # 3 s; 2 never shows a cooldown (no target)
            self.tick()
        self.assertLessEqual(self.pressed().count("2"), 2, "backs off instead of spamming")

    def test_busy_cycle_presses_every_skill_promptly(self):
        """Every skill that goes off returns 6 s later; all six keep getting used with no idle gaps."""
        back_at = {}
        for _ in range(int(30 / TICK)):
            for s, t in list(back_at.items()):
                if self.clock.t >= t:
                    self.set_cd(s, on=False)
                    del back_at[s]
            n = len(self.inp.presses)
            self.tick()
            if len(self.inp.presses) > n:
                s = self.inp.presses[-1][1]
                self.set_cd(s)                    # goes off right away
                back_at[s] = self.clock.t + 6.0
        counts = {s: self.pressed().count(s) for s in self.rotation.priority}
        self.assertTrue(all(c >= 4 for c in counts.values()), counts)

    def test_mistakes_in_rotation_file_are_reported(self):
        with self.assertRaisesRegex(ValueError, "not a skill-bar number"):
            parse_simple_rotation({"priority": [2, 11]})
        with self.assertRaisesRegex(ValueError, "priority"):
            parse_simple_rotation({})
        with self.assertRaisesRegex(ValueError, "double_tap"):
            parse_simple_rotation({"priority": [2], "double_tap": [5]})


if __name__ == "__main__":
    unittest.main()
