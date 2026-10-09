"""
Test Suite for Automated HUD Detection and Modular Spec Files.
Validates:
1. Automated HUD Detection on real full-screen GW2 captures.
2. Aspect-ratio invariant bottom-center scaling across Ultrawide, 16:9, and 1080p.
3. Modular spec loading from config/specs/ for Mesmer Virtuoso and all classes.
4. Cooldown and Resource detector alignment with spec configuration files.
"""

import os
import sys
import unittest
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hud_detector import AutoHUDDetector
from core.spec_manager import load_spec_config, list_available_specs, get_spec_file_path
from core.cooldown_detector import UniversalCooldownDetector
from core.resource_detector import UniversalResourceDetector
from core.dpi_utils import bottom_center_to_absolute


class TestHUDAutoDetectAndSpecs(unittest.TestCase):

    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.screenshot_path = os.path.join(
            r"C:\Users\Power Tower\.gemini\antigravity-ide\brain\1a0ab474-694c-4361-9117-8dc653223e77\.user_uploaded",
            "media_1791523064338.png"
        )

    def test_health_orb_and_hud_detection(self):
        if not os.path.exists(self.screenshot_path):
            self.skipTest("Reference screenshot not found on test system")

        img = cv2.imread(self.screenshot_path)
        self.assertIsNotNone(img, "Failed to load screenshot")

        res = AutoHUDDetector.detect_hud_from_image(img)
        self.assertTrue(res["success"], f"Detection failed: {res['message']}")
        
        # Verify health orb coordinates
        ox, oy, radius = res["orb"]
        self.assertAlmostEqual(ox, 512.1, delta=2.0)
        self.assertAlmostEqual(oy, 392.9, delta=2.0)

        # Verify expanded action bar bounds in 1024x428 (+44px W, +46px H on 1440p)
        x, y, w, h = res["abs_bounds"]
        self.assertAlmostEqual(x, 360, delta=4)
        self.assertAlmostEqual(y, 354, delta=4)
        self.assertAlmostEqual(w, 304, delta=4)
        self.assertAlmostEqual(h, 73, delta=4)

        # Verify bottom-center configuration
        bc = res["bottom_center"]
        self.assertEqual(bc["mode"], "bottom_center")
        self.assertAlmostEqual(bc["center_offset_ratio_x"], 0.0, delta=0.01)

    def test_ultrawide_to_standard_scaling(self):
        # Using expanded parameters:
        # width_ratio = 0.71250, height_ratio = 0.17222, bottom_offset_ratio_y = 0.00139
        bc = {
            "center_offset_ratio_x": 0.0,
            "bottom_offset_ratio_y": 0.00139,
            "width_ratio": 0.71250,
            "height_ratio": 0.17222,
        }

        # 3440x1440 (21:9 Ultrawide)
        ux, uy, uw, uh = bottom_center_to_absolute(
            bc["center_offset_ratio_x"], bc["bottom_offset_ratio_y"],
            bc["width_ratio"], bc["height_ratio"],
            3440, 1440
        )
        self.assertEqual(ux + uw // 2, 1720, "Should be horizontally centered at 1720 on 3440px wide")
        self.assertEqual(uw, 1026)
        self.assertEqual(uh, 248)

        # 2560x1440 (16:9 Standard)
        sx, sy, sw, sh = bottom_center_to_absolute(
            bc["center_offset_ratio_x"], bc["bottom_offset_ratio_y"],
            bc["width_ratio"], bc["height_ratio"],
            2560, 1440
        )
        self.assertEqual(sx + sw // 2, 1280, "Should be horizontally centered at 1280 on 2560px wide")
        self.assertEqual(sw, 1026, "Size in pixels should be identical between 1440p monitors")
        self.assertEqual(sh, 248)

        # 1920x1080 (1080p Standard)
        fx, fy, fw, fh = bottom_center_to_absolute(
            bc["center_offset_ratio_x"], bc["bottom_offset_ratio_y"],
            bc["width_ratio"], bc["height_ratio"],
            1920, 1080
        )
        self.assertEqual(fx + fw // 2, 960, "Should be horizontally centered at 960 on 1920px wide")
        self.assertAlmostEqual(fw, int(1026 * 1080 / 1440), delta=2)

    def test_mesmer_virtuoso_spec_file(self):
        spec_cfg = load_spec_config("Mesmer", "Virtuoso")
        self.assertEqual(spec_cfg["profession"], "Mesmer")
        self.assertEqual(spec_cfg["elite_spec"], "Virtuoso")

        m_bar = spec_cfg.get("mechanic_bar", {})
        self.assertEqual(m_bar.get("f_slots_count"), 5)
        slots = m_bar.get("slots", {})
        self.assertIn("mech_f1", slots)
        self.assertIn("mech_f5", slots)
        self.assertAlmostEqual(slots["mech_f1"][0], 0.0954, delta=0.005)
        self.assertAlmostEqual(slots["mech_f5"][0], 0.3980, delta=0.005)

        res = spec_cfg.get("resource", {})
        self.assertEqual(res.get("type"), "discrete_pips")
        self.assertEqual(res.get("name"), "blades")
        self.assertEqual(res.get("max_pips"), 5)
        self.assertAlmostEqual(res.get("bbox")[0], 0.1875, delta=0.005)

    def test_cooldown_detector_loads_virtuoso_spec(self):
        cd_det = UniversalCooldownDetector(profession="Mesmer", spec="Virtuoso")
        self.assertIn("mech_f1", cd_det.slots)
        self.assertIn("mech_f5", cd_det.slots)
        self.assertIn("weapon_swap", cd_det.slots)
        self.assertIn("weapon_1", cd_det.slots)
        self.assertIn("elite", cd_det.slots)

        f1 = cd_det.slots["mech_f1"]
        self.assertAlmostEqual(f1[0], 0.0954, delta=0.005)
        self.assertEqual(cd_det.slot_labels.get("mech_f1"), "F1:Harmony")

    def test_resource_detector_loads_virtuoso_spec(self):
        res_det = UniversalResourceDetector(profession="Mesmer", spec="Virtuoso")
        self.assertEqual(res_det.resource_type, "discrete_pips")
        self.assertEqual(res_det.resource_name, "blades")
        self.assertEqual(res_det.max_value, 5.0)
        self.assertIsNotNone(res_det.pip_detector)
        self.assertEqual(res_det.pip_detector.max_pips, 5)

    def test_all_spec_files_load_valid_yaml(self):
        specs = list_available_specs()
        self.assertGreaterEqual(len(specs), 30, f"Expected at least 30 specs, found {len(specs)}")
        for s in specs:
            cfg = load_spec_config(s["profession"], s["elite_spec"])
            self.assertIn("profession", cfg)
            self.assertIn("elite_spec", cfg)
            self.assertIn("mechanic_bar", cfg)
            self.assertIn("resource", cfg)


if __name__ == "__main__":
    unittest.main()
