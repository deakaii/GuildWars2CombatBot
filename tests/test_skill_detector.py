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

import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class TestSkillDetectorOnRealHud(unittest.TestCase):
    """Accuracy check against a real GW2 HUD screenshot (config/templates/hud_reference.png)."""

    REF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "templates", "hud_reference.png")
    # Hand-measured slot left edges in hud_reference.png (1024x284), y top ~174, size ~77
    EXPECTED_X = {
        "weapon_1": 69, "weapon_2": 149, "weapon_3": 229, "weapon_4": 310, "weapon_5": 390,
        "heal": 616, "utility_1": 696, "utility_2": 776, "utility_3": 857, "elite": 937,
    }

    def _check(self, frame, x_off, y_off, scale):
        geom = ActionSkillDetector.detect_skill_bar(frame)
        self.assertIsNotNone(geom)
        tol = max(4, 4 * scale)
        self.assertAlmostEqual(geom.slot_size, 77 * scale, delta=tol)
        for key, ex in self.EXPECTED_X.items():
            x, y, _, _ = geom.slots[key]
            self.assertAlmostEqual(x, x_off + ex * scale, delta=tol, msg=f"{key} x")
            self.assertAlmostEqual(y, y_off + 174 * scale, delta=tol, msg=f"{key} y")

    def test_cropped_hud(self):
        frame = cv2.imread(self.REF)
        self.assertIsNotNone(frame)
        self._check(frame, 0, 0, 1.0)

    def test_full_screen_ultrawide_at_multiple_ui_scales(self):
        hud = cv2.imread(self.REF)
        for scale in (0.6, 1.0, 1.4):
            hs = cv2.resize(hud, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            frame = np.full((1440, 3440, 3), 40, np.uint8)
            # Red distractor in the lower screen (an enemy/effect) must not be picked as the orb
            cv2.circle(frame, (1100, 1000), 30, (20, 20, 200), -1)
            h, w = hs.shape[:2]
            x0, y0 = (3440 - w) // 2, 1440 - h
            frame[y0:y0 + h, x0:x0 + w] = hs
            with self.subTest(scale=scale):
                self._check(frame, x0, y0, scale)


    def test_press_calibration_locates_darkened_slot(self):
        # Simulate pressing each Mechanist F-skill in hud_reference.png: the icon darkens
        # (partly at +0.5s, fully at +2s, with white timer digits) while the world moves.
        from core.mech_press_calibrator import locate_cooldown_square, search_band
        before = cv2.imread(self.REF)
        geom = ActionSkillDetector.detect_skill_bar(before)
        band = search_band(geom)
        for x, y, s in ((75, 64, 44), (124, 64, 44), (171, 64, 44)):
            first, confirm = before.copy(), before.copy()
            first[y:y + s, x:x + s] = (first[y:y + s, x:x + s] * 0.6).astype(np.uint8)
            confirm[y:y + s, x:x + s] = (confirm[y:y + s, x:x + s] * 0.35).astype(np.uint8)
            cv2.putText(confirm, "18", (x + 8, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            confirm[100:150, 300:360] = np.roll(confirm[100:150, 300:360], 9, axis=1)
            box = locate_cooldown_square(before, first, confirm, band, geom.slot_size)
            self.assertIsNotNone(box, f"slot at x={x}")
            bx, by, bw, bh = box
            self.assertAlmostEqual(bx, x, delta=4)
            self.assertAlmostEqual(by, y, delta=4)
            self.assertAlmostEqual(max(bw, bh), s, delta=5)

    def test_press_calibration_ignores_no_change(self):
        from core.mech_press_calibrator import locate_cooldown_square, search_band
        frame = cv2.imread(self.REF)
        geom = ActionSkillDetector.detect_skill_bar(frame)
        self.assertIsNone(locate_cooldown_square(frame, frame, frame, search_band(geom), geom.slot_size))

    def test_weapon_swap_aligned_with_skill_row(self):
        # Swap icon in hud_reference.png: gray square at x ~7-62, y ~177-232 (top level with skills)
        x, y, w, h = ActionSkillDetector.detect_skill_bar(cv2.imread(self.REF)).slots["weapon_swap"]
        self.assertAlmostEqual(x, 7, delta=4)
        self.assertAlmostEqual(y, 177, delta=4)
        self.assertAlmostEqual(w, 56, delta=4)

    def test_no_mechanic_slots_without_spec(self):
        geom = ActionSkillDetector.detect_skill_bar(cv2.imread(self.REF))
        self.assertFalse(any(k.startswith("mech_") for k in geom.slots))

    def test_settings_never_receive_mech_slots(self):
        # calibrated_slots in settings.yaml override every spec's mechanic layout,
        # so auto-calibration must strip mech_* entries, including stale ones.
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
            yaml.safe_dump({"calibrated_slots": {"mech_f1": [0.1, 0.1, 0.05, 0.2]}}, tmp)
            tmp_path = tmp.name
        try:
            ok, msg, _ = ActionSkillDetector.auto_calibrate_and_save(frame=cv2.imread(self.REF), settings_path=tmp_path)
            self.assertTrue(ok, msg)
            with open(tmp_path) as fh:
                saved = yaml.safe_load(fh)
            self.assertFalse(any(k.startswith("mech_") for k in saved["calibrated_slots"]))
            self.assertIn("weapon_1", saved["calibrated_slots"])
        finally:
            os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
