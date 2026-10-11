"""Fight recording: F9 (engage) starts a recording of the engine's frames, F10 stops it."""

import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import PrioritizationEngine
from core.fight_recorder import FightRecorder


class FakeMonitor:
    last_latency_ms = 0.0

    def grab_frame(self):
        return np.full((40, 80, 3), 128, np.uint8)

    def close(self):
        pass


class FakeInput:
    def __init__(self):
        self.active = False

    def is_game_focused(self):
        return True

    def is_active(self):
        return self.active

    def close(self):
        pass


class TestFightRecorder(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def fights(self):
        return sorted(d for d in os.listdir(self.root) if d.startswith("fight_"))

    def test_frames_are_saved_with_wall_clock_names(self):
        rec = FightRecorder(root=self.root)
        folder = rec.start()
        for i in range(3):
            rec.add(np.zeros((40, 80, 3), np.uint8), t=1_760_000_000.0 + i * 0.05)
        self.assertEqual(rec.stop(), folder)
        names = sorted(os.listdir(folder))
        self.assertEqual(len(names), 3)
        self.assertTrue(all(n.endswith(".jpg") and len(n) == len("HHMMSS.mmm.jpg") for n in names), names)

    def test_only_the_newest_fights_are_kept(self):
        for i in range(4):
            os.makedirs(os.path.join(self.root, f"fight_20260101_00000{i}"))
        rec = FightRecorder(root=self.root, keep=2)
        rec.start()
        rec.stop()
        self.assertEqual(len(self.fights()), 2)
        self.assertNotIn("fight_20260101_000000", self.fights())

    def test_disabled_unless_configured(self):
        self.assertIsNone(FightRecorder.from_config({}))
        self.assertIsNotNone(FightRecorder.from_config({"recording": {"enabled": True, "dir": self.root}}))

    def test_engage_starts_and_disengage_stops_recording(self):
        inp = FakeInput()
        engine = PrioritizationEngine({"recording": {"enabled": True, "dir": self.root}}, FakeMonitor(), None, inp)
        engine.run_tick()
        self.assertEqual(self.fights(), [], "nothing recorded in standby")
        inp.active = True                     # F9
        for _ in range(3):
            engine.run_tick()
        self.assertTrue(engine.recorder.recording)
        inp.active = False                    # F10
        engine.run_tick()
        self.assertFalse(engine.recorder.recording)
        [fight] = self.fights()
        self.assertEqual(len(os.listdir(os.path.join(self.root, fight))), 3)


if __name__ == "__main__":
    unittest.main()
