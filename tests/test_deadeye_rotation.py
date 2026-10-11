"""
Tests for sequence rotations (opener + loop blocks) in profiles/simple_rotation.py, using the
Thief/Deadeye rotation file against a small simulated game: initiative, malice, cooldowns,
Mercy recharging Deadeye's Mark and Shadow Flare flipping to Shadow Swap.
"""

import os
import sys
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resource_detector import UniversalResourceDetector
from profiles.simple_rotation import (
    SKILL_SLOTS, SimpleRotationBehavior, check_resources, load_simple_rotation, parse_simple_rotation,
)

TICK = 0.05
FRAME = np.zeros((10, 10, 3), np.uint8)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Game:
    """Plays the cooldown detector, the resource detector and the input controller at once."""

    def __init__(self, clock, initiative=15.0, malice=0, malice_per_burst=3):
        self.clock = clock
        self.initiative = initiative
        self.malice = malice
        self.malice_per_burst = malice_per_burst
        self.cd_until = {}
        self.shadow_swap_up = False
        self.stealthed = False
        self.presses = []

    def get_slot_status(self, frame, slot_id):
        r = self.clock.t >= self.cd_until.get(slot_id, 0.0)
        return SimpleNamespace(is_ready=r, raw_is_ready=r)

    def get_resource_state(self, frame, name):
        value = int(self.initiative) if name == "initiative" else self.malice
        return SimpleNamespace(current_value=float(value))

    def cooldown(self, skill, seconds):
        self.cd_until[SKILL_SLOTS[skill]] = self.clock.t + seconds

    def press_key(self, key, double_tap=False, double_tap_gap=None):
        self.presses.append((round(self.clock.t, 2), key))
        if key == "3" and self.initiative >= 4:          # Three Round Burst
            self.initiative -= 4
            self.malice = min(5, self.malice + self.malice_per_burst)
        elif key == "1":                                  # stealth attack spends malice
            if self.stealthed:
                self.malice, self.stealthed = 0, False
        elif key == "f2":                                 # Steal Time stealths at 3+ malice
            self.stealthed = self.malice >= 3
        elif key == "f1":                                 # Deadeye's Mark
            self.cooldown("f1", 25)
        elif key == "6":                                  # Mercy: loses malice, recharges the Mark
            self.malice = 0
            self.cooldown("6", 1)
            self.cd_until.pop(SKILL_SLOTS["f1"], None)
        elif key == "7":                                  # Shadow Flare, then Shadow Swap
            if self.shadow_swap_up:
                self.cooldown("7", 20)
            self.shadow_swap_up = not self.shadow_swap_up
        elif key == "0":                                  # Shadow Meld
            self.cooldown("0", 60)
            self.stealthed = True
        return True

    def advance(self, dt):
        self.initiative = min(15.0, self.initiative + dt)  # ~1 initiative a second


class TestDeadeyeRotation(unittest.TestCase):

    def make(self, rotation=None, **game):
        self.clock = Clock()
        self.game = Game(self.clock, **game)
        self.bot = SimpleRotationBehavior(rotation or load_simple_rotation("Thief", "Deadeye"),
                                          self.game, self.game, clock=self.clock, log=lambda m: None,
                                          icon_reader=lambda frame, skill, sid: self.game.stealthed)

    def tick(self, n=1):
        for _ in range(n):
            matched, _ = self.bot.evaluate_condition(FRAME, None)
            if matched:
                self.bot.execute_action(self.game)
            self.clock.t = round(self.clock.t + TICK, 4)
            self.game.advance(TICK)

    def pressed(self):
        return [k for _, k in self.game.presses]

    def press_time(self, i):
        return self.game.presses[i][0]

    def test_rotation_file_loads_and_resources_exist(self):
        r = load_simple_rotation("Thief", "Deadeye")
        self.assertTrue(r.sequenced)
        self.assertEqual([b.name for b in r.loop], ["Mercy reset", "Shadow Flare combo", "Shadow Meld intermission"])
        check_resources(r, UniversalResourceDetector(profession="Thief", spec="Deadeye"))

    def test_opener_follows_snow_crows_order(self):
        self.make()
        while len(self.game.presses) < 25 and self.clock.t < 60:
            self.tick()
        self.assertEqual(self.pressed(), [
            "5", "f1", "f2", "7", "3", "7", "3", "f2", "1",
            "3", "6", "f2", "3", "f1", "3", "f2", "1", "6",
            "3", "f2", "3", "f1", "3", "f2", "1",
        ])

    def test_steal_time_waits_for_five_malice(self):
        self.make(parse_simple_rotation({"opener": [{"skill": "f2", "wait": {"malice": 5}}, 1], "instant": ["f2"]}), malice=4)
        self.tick(40)
        self.assertEqual(self.pressed(), [])
        self.game.malice = 5
        self.tick(3)
        self.assertEqual(self.pressed(), ["f2", "1"])

    def test_burst_waits_for_initiative_and_counts_as_cast_when_it_drops(self):
        rot = parse_simple_rotation({"opener": [3, 3], "costs": {3: {"initiative": 4}}})
        self.make(rot, initiative=5)
        self.tick(10)
        self.assertEqual(self.pressed(), ["3"], "second burst waits: 1 initiative left")
        self.tick(70)
        self.assertEqual(self.pressed(), ["3", "3"])
        self.assertAlmostEqual(self.press_time(1), 3.0, delta=0.2, msg="pressed once 4 initiative is back")

    def test_stealth_waits_for_revealed_to_wear_off(self):
        rot = parse_simple_rotation({"opener": [1, {"skill": "f2", "after": {1: 3}}],
                                     "instant": ["f2"], "costs": {1: {"malice": 1}}})
        self.make(rot, malice=5)
        self.game.stealthed = True
        self.tick(100)
        self.assertEqual(self.pressed(), ["1", "f2"])
        self.assertGreaterEqual(self.press_time(1) - self.press_time(0), 3.0)

    def _at_loop(self):
        self.bot.steps, self.bot.step_i, self.bot.block = [], 0, None

    def test_mercy_reset_comes_first_when_mark_and_mercy_are_ready(self):
        self.make(malice=5)
        self._at_loop()
        self.tick()
        self.assertEqual(self.bot.block, "Mercy reset")
        self.assertEqual(self.pressed(), ["3"])

    def test_shadow_flare_combo_when_mark_is_on_cooldown(self):
        self.make()
        self.game.cooldown("f1", 20)
        self._at_loop()
        self.tick()
        self.assertEqual(self.bot.block, "Shadow Flare combo")
        self.assertEqual(self.pressed(), ["7"])

    def test_shadow_meld_intermission_starts_with_auto_attacks(self):
        self.make(malice=5)
        self.game.cooldown("f1", 20)
        self.game.cooldown("7", 20)
        self._at_loop()
        self.tick(100)                         # 5 autos x 0.8 s = 4 s of pressing nothing
        self.assertEqual(self.bot.block, "Shadow Meld intermission")
        self.assertEqual(self.pressed()[0], "0")
        self.assertGreaterEqual(self.press_time(0), 4.0)

    def test_nothing_ready_presses_nothing(self):
        self.make()
        for s in ("f1", "7", "0"):
            self.game.cooldown(s, 20)
        self._at_loop()
        self.tick(40)
        self.assertEqual(self.pressed(), [])

    def test_new_fight_restarts_the_opener(self):
        self.make()
        self.tick(30)
        self.clock.t += 5.0                    # F10 / tabbed out, then engaged again
        n = len(self.game.presses)
        self.tick()
        self.assertEqual(self.pressed()[n:], ["5"])

    def test_step_that_never_becomes_ready_is_skipped(self):
        self.make(parse_simple_rotation({"opener": ["f1", 3], "instant": ["f1"]}))
        self.game.cooldown("f1", 100)
        self.tick(int(5.5 / TICK))
        self.assertEqual(self.pressed(), [])
        self.tick(20)
        self.assertEqual(self.pressed(), ["3"])

    def test_fill_builds_malice_instead_of_idling(self):
        rot = parse_simple_rotation({
            "opener": [{"skill": "f2", "wait": {"malice": 5}, "fill": 3}, {"skill": 1, "only_if": {"malice": 3}}],
            "instant": ["f2"], "costs": {3: {"initiative": 4}, 1: {"malice": 1}},
        })
        self.make(rot, malice=1, malice_per_burst=2)
        self.tick(60)
        self.assertEqual(self.pressed(), ["3", "3", "f2", "1"])
        self.assertEqual(self.game.malice, 0, "stealth attack spent the malice")

    def test_stealth_attack_skipped_when_steal_time_could_not_stealth(self):
        rot = parse_simple_rotation({
            "opener": [{"skill": "f2", "wait": {"malice": 5}, "fill": 3}, {"skill": 1, "only_if": {"malice": 3}}, 3],
            "instant": ["f2"], "costs": {3: {"initiative": 4}},
        })
        self.make(rot, malice=2)
        self.game.cooldown("3", 6.4)              # nothing to fill with until Steal Time gives up
        self.tick(int(6.6 / TICK))
        self.assertEqual(self.pressed(), ["f2", "3"], "1 skipped at 2 malice, sequence moves on")

    def test_unconfirmed_step_presses_once_and_moves_on(self):
        rot = parse_simple_rotation({"opener": [{"skill": 1, "confirm": False}, 3], "costs": {1: {"malice": 1}}})
        self.make(rot, malice=0)
        self.tick(5)
        self.assertEqual(self.pressed(), ["1", "3"])

    def test_stealth_attack_waits_for_its_icon_and_counts_when_it_goes(self):
        rot = parse_simple_rotation({"opener": [1, 3], "icons": {1: 44087}})
        self.make(rot)
        self.tick(10)
        self.assertEqual(self.pressed(), [], "not stealthed: slot 1 doesn't show the stealth attack")
        self.game.stealthed = True              # e.g. Steal Time went off behind a cast
        self.tick(5)
        self.assertEqual(self.pressed(), ["1", "3"], "pressed once shown; cast once the icon left")

    def test_fill_presses_are_spaced_out(self):
        rot = parse_simple_rotation({"opener": [{"skill": "f2", "wait": {"malice": 5}, "fill": 3}],
                                     "instant": ["f2"], "costs": {3: {"initiative": 4}}})
        self.make(rot, malice=0, malice_per_burst=1)
        self.tick(int(1.6 / TICK))
        fills = [t for t, k in self.game.presses if k == "3"]
        self.assertEqual(len(fills), 3)
        self.assertTrue(all(b - a >= 0.75 for a, b in zip(fills, fills[1:])), fills)

    def test_real_stealth_attack_icon_on_recorded_frames(self):
        from core.icon_matcher import IconMatcher
        m, fix = IconMatcher(), os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cooldown")
        for name, shown in (("shown", True), ("before", False), ("after", False)):
            crop = cv2.imread(os.path.join(fix, f"deadeye_slot1_mdj_{name}.png"))
            self.assertEqual(m.shows(crop, 44087), shown, name)

    def test_mistakes_are_reported(self):
        with self.assertRaisesRegex(ValueError, "unknown step key"):
            parse_simple_rotation({"opener": [{"skill": 3, "wiat": {"malice": 5}}]})
        with self.assertRaisesRegex(ValueError, "not both"):
            parse_simple_rotation({"opener": [{"skill": 3, "auto": 2}]})
        with self.assertRaisesRegex(ValueError, "not a skill-bar number"):
            parse_simple_rotation({"opener": ["f6"]})
        rot = parse_simple_rotation({"opener": [{"skill": 3, "wait": {"heat": 50}}]})
        with self.assertRaisesRegex(ValueError, "heat"):
            check_resources(rot, UniversalResourceDetector(profession="Thief", spec="Deadeye"))


if __name__ == "__main__":
    unittest.main()
