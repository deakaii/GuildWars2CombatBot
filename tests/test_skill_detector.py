"""
Unit tests for ActionSkillDetector (core/skill_detector.py).
Verifies:
1. Health orb location and mathematical square derivation.
2. Exact square dimensions (width == height) for all skill slots.
3. Left (1-5) and Right (6-0) symmetry around the health orb.
4. Auto-calibration persistence to settings.yaml (calibrated_slots).
"""

import os
import unittest
import tempfile
import yaml
import numpy as np
import cv2

from core.skill_detector import ActionSkillDetector, SkillBarGeometry


class TestActionSkillDetector(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Check for real user game screenshot if available
        sample_path = r"C:\Users\Power Tower\.gemini\antigravity-ide\brain\1a0ab474-694c-4361-9117-8dc653223e77\.user_uploaded\media_1791524498436.png"
        if os.path.exists(sample_path):
            cls.test_image = cv2.imread(sample_path)
        else:
            # Generate synthetic test frame with central red health orb
            cls.test_image = np.zeros((300, 1000, 3), dtype=np.uint8)
            # Red circle at center (500, 180) radius 65
            cv2.circle(cls.test_image, (500, 180), 65, (30, 30, 210), -1)

    def test_detect_skill_bar_geometry(self):
        geom = ActionSkillDetector.detect_skill_bar(self.test_image)
        self.assertIsNotNone(geom, "SkillBarGeometry should be successfully detected")
        self.assertIsInstance(geom, SkillBarGeometry)

        # 1. Verify health orb
        ocx, ocy = geom.orb_center
        self.assertGreater(ocx, 400)
        self.assertLess(ocx, 600)
        self.assertGreater(geom.orb_radius, 30)

        # 2. Verify all 10 slots + weapon swap exist
        expected_slots = [
            "weapon_1", "weapon_2", "weapon_3", "weapon_4", "weapon_5",
            "weapon_swap",
            "heal", "utility_1", "utility_2", "utility_3", "elite"
        ]
        for s_id in expected_slots:
            self.assertIn(s_id, geom.slots, f"Slot {s_id} must be generated")
            x, y, w, h = geom.slots[s_id]
            if s_id != "weapon_swap":
                # Must be an exact square
                self.assertEqual(w, h, f"Slot {s_id} must be an exact square (w={w}, h={h})")
                self.assertEqual(w, geom.slot_size, f"Slot {s_id} width must match slot_size")

        # 3. Verify monotonic left-to-right positioning
        # Left side: swap < 1 < 2 < 3 < 4 < 5
        self.assertLess(geom.slots["weapon_swap"][0], geom.slots["weapon_1"][0])
        self.assertLess(geom.slots["weapon_1"][0], geom.slots["weapon_2"][0])
        self.assertLess(geom.slots["weapon_2"][0], geom.slots["weapon_3"][0])
        self.assertLess(geom.slots["weapon_3"][0], geom.slots["weapon_4"][0])
        self.assertLess(geom.slots["weapon_4"][0], geom.slots["weapon_5"][0])

        # All left skills must be to the left of the health orb center
        for num in [1, 2, 3, 4, 5]:
            x, y, w, h = geom.slots[f"weapon_{num}"]
            self.assertLess(x + w, ocx, f"Weapon skill {num} must be entirely left of orb center")

        # Right side: heal (6) < util_1 (7) < util_2 (8) < util_3 (9) < elite (0)
        self.assertLess(geom.slots["heal"][0], geom.slots["utility_1"][0])
        self.assertLess(geom.slots["utility_1"][0], geom.slots["utility_2"][0])
        self.assertLess(geom.slots["utility_2"][0], geom.slots["utility_3"][0])
        self.assertLess(geom.slots["utility_3"][0], geom.slots["elite"][0])

        # All right skills must be to the right of the health orb center
        for k in ["heal", "utility_1", "utility_2", "utility_3", "elite"]:
            x, y, w, h = geom.slots[k]
            self.assertGreater(x, ocx, f"Utility skill {k} must be entirely right of orb center")

        # 4. Verify shared horizontal baseline for all 10 skills
        baseline_y = geom.slots["weapon_1"][1]
        for s_id in ["weapon_2", "weapon_3", "weapon_4", "weapon_5", "heal", "utility_1", "utility_2", "utility_3", "elite"]:
            self.assertEqual(geom.slots[s_id][1], baseline_y, f"Slot {s_id} must share baseline y={baseline_y}")

    def test_auto_calibrate_and_save_persistence(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
            tmp_path = tmp.name

        try:
            success, msg, data = ActionSkillDetector.auto_calibrate_and_save(
                frame=self.test_image,
                settings_path=tmp_path
            )
            self.assertTrue(success, f"Auto-calibration failed: {msg}")
            self.assertIn("calibrated_slots", data)
            self.assertIn("region", data)

            with open(tmp_path, "r") as f:
                saved = yaml.safe_load(f)

            self.assertIn("calibrated_slots", saved)
            self.assertIn("region", saved)
            self.assertIn("weapon_1", saved["calibrated_slots"])
            self.assertIn("weapon_5", saved["calibrated_slots"])
            self.assertIn("heal", saved["calibrated_slots"])
            self.assertIn("elite", saved["calibrated_slots"])

            # Verify normalized values are between 0.0 and 1.0
            for k, coords in saved["calibrated_slots"].items():
                nx, ny, nw, nh = coords
                self.assertGreaterEqual(nx, 0.0)
                self.assertLessEqual(nx + nw, 1.05)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_draw_annotated_preview(self):
        geom = ActionSkillDetector.detect_skill_bar(self.test_image)
        self.assertIsNotNone(geom)
        annotated = ActionSkillDetector.draw_annotated_preview(self.test_image, geom)
        self.assertEqual(annotated.shape, self.test_image.shape)


if __name__ == "__main__":
    unittest.main()
