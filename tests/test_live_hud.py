"""
Unit tests for Live HUD tool.
Verifies:
1. live_hud imports without errors (including numpy and cv2).
2. Can render overlays and construct HUD canvas without NameError or missing dependencies.
"""

import unittest
import numpy as np
import cv2
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cooldown_detector import UniversalCooldownDetector
from core.resource_detector import UniversalResourceDetector


class TestLiveHUD(unittest.TestCase):

    def test_imports_and_canvas_assembly(self):
        # Ensure tools.live_hud imports cleanly
        import tools.live_hud as live_hud
        self.assertTrue(hasattr(live_hud, "run_live_hud"))

        # Test canvas creation as done in live_hud
        w, h = 640, 360
        header_h = 24
        footer_h = 24
        mock_frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Replicate live_hud canvas creation
        canvas = np.zeros((header_h + h + footer_h, w, 3), dtype=np.uint8)
        canvas[0:header_h, :] = (25, 25, 25)
        canvas[header_h : header_h + h, 0:w] = mock_frame
        canvas[header_h + h :, :] = (30, 30, 30)

        self.assertEqual(canvas.shape, (header_h + h + footer_h, w, 3))

    def test_square_slot_geometry(self):
        # Action bar skill slots must be exact squares (box_w == box_h)
        cd_det = UniversalCooldownDetector(profession="Mesmer", spec="Virtuoso")
        hud_shape = (246, 1026)  # 1440p standard HUD frame

        square_slots = [
            "weapon_1", "weapon_2", "weapon_3", "weapon_4", "weapon_5",
            "heal", "utility_1", "utility_2", "utility_3", "elite",
            "mech_f1", "mech_f2", "mech_f3", "mech_f4", "mech_f5"
        ]
        for s_id in square_slots:
            rect = cd_det.get_slot_rect(hud_shape, s_id)
            self.assertIsNotNone(rect, f"Slot {s_id} should have a valid rect")
            x, y, w, h = rect
            self.assertEqual(w, h, f"Slot {s_id} must be an exact square (w={w}, h={h})")
            self.assertGreater(w, 20, f"Slot {s_id} must have reasonable width")

    def test_slot_aliases(self):
        cd_det = UniversalCooldownDetector(profession="Mesmer", spec="Virtuoso")
        self.assertEqual(cd_det.resolve_slot_id("1"), "weapon_1")
        self.assertEqual(cd_det.resolve_slot_id("5"), "weapon_5")
        self.assertEqual(cd_det.resolve_slot_id("6"), "heal")
        self.assertEqual(cd_det.resolve_slot_id("7"), "utility_1")
        self.assertEqual(cd_det.resolve_slot_id("8"), "utility_2")
        self.assertEqual(cd_det.resolve_slot_id("9"), "utility_3")
        self.assertEqual(cd_det.resolve_slot_id("0"), "elite")
        self.assertEqual(cd_det.resolve_slot_id("skill_1"), "weapon_1")
        self.assertEqual(cd_det.resolve_slot_id("skill_6"), "heal")

    def test_calibrated_slots_persistence_in_autodetect(self):
        import tempfile, yaml
        from core.hud_detector import AutoHUDDetector

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
            test_cfg = {
                "calibrated_slots": {
                    "weapon_1": [0.060, 0.580, 0.075, 0.310],
                    "heal": [0.570, 0.580, 0.075, 0.310]
                }
            }
            yaml.safe_dump(test_cfg, tmp)
            tmp_path = tmp.name

        try:
            # Create a synthetic frame with mock orb
            synthetic_frame = np.zeros((1440, 3440, 3), dtype=np.uint8)
            # Center red orb
            cv2.circle(synthetic_frame, (1720, 1300), 50, (30, 30, 200), -1)

            AutoHUDDetector.auto_calibrate_and_save(settings_path=tmp_path, frame=synthetic_frame)

            with open(tmp_path, "r") as f:
                saved = yaml.safe_load(f)

            self.assertIn("calibrated_slots", saved, "Auto-detect must NEVER delete user calibrated_slots")
            self.assertIn("weapon_1", saved["calibrated_slots"])
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


    def test_window_utils_foreground_query(self):
        from core.window_utils import get_foreground_window_info, is_gw2_process_running
        info = get_foreground_window_info()
        self.assertIsInstance(info, dict)
        self.assertIn("hwnd", info)
        self.assertIn("title", info)
        self.assertIn("exe", info)
        self.assertIn("is_gw2", info)

        # Process check should return boolean without crashing
        running = is_gw2_process_running()
        self.assertIsInstance(running, bool)

    def test_window_utils_focus_logic(self):
        from core.window_utils import is_gw2_focused
        from unittest.mock import patch

        # When foreground is Guild Wars 2
        with patch("core.window_utils.get_foreground_window_info", return_value={
            "hwnd": 12345, "title": "Guild Wars 2", "class": "ArenaNet_Dx_Window_Class", "exe": "Gw2-64.exe", "is_gw2": True
        }):
            self.assertTrue(is_gw2_focused())

        # When foreground is Chrome / Discord / IDE / HUD
        with patch("core.window_utils.get_foreground_window_info", return_value={
            "hwnd": 99999, "title": "Discord - #general", "class": "Chrome_WidgetWin_1", "exe": "Discord.exe", "is_gw2": False
        }):
            self.assertFalse(is_gw2_focused())

    def test_hud_standby_canvas_generation(self):
        # Verify standby canvas renders correctly without errors
        h_roi, w_roi = 240, 800
        header_h, footer_h = 24, 24
        display = np.full((h_roi, w_roi, 3), (20, 20, 26), dtype=np.uint8)

        card_w, card_h = 600, 150
        card_x = (w_roi - card_w) // 2
        card_y = (h_roi - card_h) // 2

        cv2.rectangle(display, (card_x, card_y), (card_x + card_w, card_y + card_h), (0, 180, 240), 2)
        cv2.putText(display, "PAUSED -- WAITING FOR GUILD WARS 2 FOCUS", (card_x + 18, card_y + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 215, 255), 2)

        canvas = np.zeros((header_h + h_roi + footer_h, w_roi, 3), dtype=np.uint8)
        canvas[0:header_h, :] = (20, 20, 24)
        canvas[header_h : header_h + h_roi, 0:w_roi] = display
        canvas[header_h + h_roi :, :] = (24, 24, 28)

        self.assertEqual(canvas.shape, (header_h + h_roi + footer_h, w_roi, 3))

    def test_engine_blocks_tick_when_not_focused(self):
        from unittest.mock import MagicMock
        from core.engine import PrioritizationEngine

        mock_monitor = MagicMock()
        mock_detector = MagicMock()
        mock_input = MagicMock()
        mock_input.is_game_focused.return_value = False
        mock_input.is_active.return_value = True

        cfg = {"control": {"require_game_focus": True}}
        engine = PrioritizationEngine(
            config=cfg,
            monitor=mock_monitor,
            detector=mock_detector,
            input_controller=mock_input
        )

        triggered = engine.run_tick()
        self.assertIsNone(triggered, "Engine tick must return None and do nothing when game is not focused")
        mock_monitor.grab_frame.assert_not_called()


class TestReadyConfirmation(unittest.TestCase):
    """End-of-cooldown flicker (single READY frames) must not report READY early."""

    def test_flicker_suppressed_until_confirmed(self):
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        raw = [0, 1, 0, 1, 1, 0, 1, 0, 1] + [1] * 20   # 30 fps readings, last CD at frame 7
        reported = [det._confirm_ready("weapon_1", bool(r), now=i / 30.0) for i, r in enumerate(raw)]
        first_ready = reported.index(True)
        self.assertFalse(any(reported[:first_ready]))
        self.assertTrue(all(reported[first_ready:]))
        self.assertGreaterEqual((first_ready - 7) / 30.0, det.ready_confirm_seconds - 1e-9)

    def test_cooldown_applies_immediately_and_fresh_slot_is_ready(self):
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        self.assertTrue(det._confirm_ready("heal", True, now=0.0))
        self.assertFalse(det._confirm_ready("heal", False, now=0.1))


class TestLateCooldownOnRealFrames(unittest.TestCase):
    """Real Mechanist frames: late-cooldown timers on green/black art, and white artwork on a ready icon."""

    FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cooldown")

    def _img(self, name):
        img = cv2.imread(os.path.join(self.FIX, name))
        self.assertIsNotNone(img, name)
        return img

    def test_timer_seen_until_the_end_of_cooldown(self):
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        for name in ("f2_cd_3.1s.png", "f2_cd_1.5s.png", "f2_cd_0.8s.png", "f2_cd_0.2s.png"):
            st = det.evaluate_slot_crop(self._img(name), "mech_f2")
            self.assertTrue(st.digit_detected, f"{name}: timer digits must be detected")
            self.assertFalse(st.is_ready, f"{name} must read as cooldown")
        self.assertTrue(det.evaluate_slot_crop(self._img("f2_ready.png"), "mech_f2").is_ready)

    def test_colorful_icon_timer_seen_late_in_cooldown(self):
        # Weapon 2 (yellow art): timer at 2.6s / 1.2s was missed when gated on wash-out
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        for name in ("w2_cd_2.6s.png", "w2_cd_1.2s.png"):
            self.assertFalse(det.evaluate_slot_crop(self._img(name), "weapon_2").is_ready, name)

    def test_ready_icon_with_flame_and_black_art_is_ready(self):
        # Weapon 5 rocket: white-hot flame core (tinted, solid) and large black silhouette
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        for name in ("w5_ready_flame_a.png", "w5_ready_flame_b.png"):
            st = det.evaluate_slot_crop(self._img(name), "weapon_5")
            self.assertFalse(st.digit_detected, name)
            self.assertTrue(st.is_ready, name)

    def test_white_artwork_on_ready_icon_is_not_a_timer(self):
        det = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        for name in ("w1_ready_white_mask.png", "w1_ready_ref.png"):
            st = det.evaluate_slot_crop(self._img(name), "weapon_1")
            self.assertFalse(st.digit_detected, name)
            self.assertTrue(st.is_ready, name)


if __name__ == "__main__":
    unittest.main()
