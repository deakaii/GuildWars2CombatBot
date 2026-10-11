import os
import unittest
import yaml
from core.spec_manager import (
    get_resolution_tag,
    sanitize_filename,
    load_spec_config,
    save_spec_config,
    get_spec_file_path,
    SPECS_DIR
)
from core.cooldown_detector import UniversalCooldownDetector


class TestSpecResolutionCalibration(unittest.TestCase):

    def test_resolution_tag_format(self):
        tag = get_resolution_tag()
        self.assertTrue(len(tag) > 0)
        self.assertIn("x", tag)
        w, h = tag.split("x")
        self.assertTrue(int(w) > 0)
        self.assertTrue(int(h) > 0)

    def test_sanitize_filename_with_and_without_resolution(self):
        fn_base = sanitize_filename("Engineer", "Mechanist")
        self.assertEqual(fn_base, "engineer_mechanist.yaml")

        fn_res = sanitize_filename("Engineer", "Mechanist", "3440x1440")
        self.assertEqual(fn_res, "engineer_mechanist_3440x1440.yaml")

    def test_resolution_specific_save_and_priority_load(self):
        res_tag = "9999x9999"
        test_data = {
            "profession": "Engineer",
            "elite_spec": "Mechanist",
            "display_name": "Engineer - Mechanist Test",
            "mechanic_bar": {
                "f_slots_count": 3,
                "slots": {
                    "mech_f1": [0.01, 0.02, 0.03, 0.04],
                    "mech_f2": [0.05, 0.06, 0.07, 0.08],
                    "mech_f3": [0.09, 0.10, 0.11, 0.12]
                },
                "labels": {"mech_f1": "M1", "mech_f2": "M2", "mech_f3": "M3"}
            },
            "resource": {"type": "none"}
        }

        # Save test resolution file
        saved_path = save_spec_config("engineer", "mechanist", test_data, resolution_tag=res_tag)
        self.assertTrue(os.path.exists(saved_path))
        self.assertIn("engineer_mechanist_9999x9999.yaml", saved_path)

        try:
            # Load with explicit resolution tag
            loaded = load_spec_config("engineer", "mechanist", resolution_tag=res_tag)
            self.assertEqual(loaded.get("display_name"), "Engineer - Mechanist Test")
            slots = loaded.get("mechanic_bar", {}).get("slots", {})
            self.assertEqual(slots.get("mech_f1"), [0.01, 0.02, 0.03, 0.04])
            self.assertEqual(len(slots), 3)
        finally:
            if os.path.exists(saved_path):
                os.remove(saved_path)

    def test_mechanist_has_exactly_three_mech_slots(self):
        cd = UniversalCooldownDetector()
        cd.set_composite("engineer", "mechanist")
        mech_keys = [k for k in cd.slots.keys() if k.startswith("mech_")]
        self.assertEqual(sorted(mech_keys), ["mech_f1", "mech_f2", "mech_f3"])
        self.assertNotIn("mech_f4", cd.slots)
        self.assertNotIn("mech_f5", cd.slots)

    def test_virtuoso_has_five_mech_slots(self):
        cd = UniversalCooldownDetector()
        cd.set_composite("mesmer", "virtuoso")
        mech_keys = [k for k in cd.slots.keys() if k.startswith("mech_")]
        self.assertEqual(sorted(mech_keys), ["mech_f1", "mech_f2", "mech_f3", "mech_f4", "mech_f5"])


if __name__ == "__main__":
    unittest.main()
