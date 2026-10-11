"""
Core Automated Guild Wars 2 HUD Detector.
Zero-click detection of the action bar, health globe, and UI geometry.
Agnostic across resolutions (1080p, 1440p, 4K, 1600p) and aspect ratios (16:9, 16:10, 21:9 Ultrawide, 32:9).
"""

import os
from typing import Tuple, Dict, Any, Optional
import numpy as np
import cv2
import yaml

from core.dpi_utils import (
    enable_dpi_awareness,
    get_screen_resolution,
    absolute_to_bottom_center,
    bottom_center_to_absolute,
)


class AutoHUDDetector:
    """
    Detects the Guild Wars 2 bottom-center action bar and health orb.
    """

    # Proportions of the GW2 action bar relative to vertical screen height (screen_h)
    # Calibrated with comfortable margins (+44px W, +46px H on 1440p) so pips, key numbers,
    # and action bar borders have clear breathing room without clipping:
    HALF_WIDTH_RATIO = 0.3562    # Distance from orb center to outer edge of Weapon Swap / Elite
    TOP_OFFSET_RATIO = 0.0917    # Distance from orb center to clearance above mechanic bar / pips
    BOT_OFFSET_RATIO = 0.0806    # Distance from orb center to clearance below skill bar base

    @staticmethod
    def detect_health_orb(frame: np.ndarray) -> Optional[Tuple[float, float, float]]:
        """
        Detects the GW2 health globe in the given frame.
        Returns (center_x, center_y, radius) or None if not found.
        """
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]

        # In GW2, the health globe is in the bottom ~35% of the screen
        # and centered horizontally within ~15% of screen width.
        y_start = int(h * 0.65)
        roi = frame[y_start:h, :]

        # Color filter for GW2 health orb red:
        b = roi[:, :, 0].astype(int)
        g = roi[:, :, 1].astype(int)
        r = roi[:, :, 2].astype(int)

        red_mask = (r > 120) & (r - b > 40) & (r - g > 25)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask.astype(np.uint8))
        if num_labels <= 1:
            return None

        screen_cx = w / 2.0
        best_candidate = None
        best_score = -1.0

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            cw = stats[i, cv2.CC_STAT_WIDTH]
            ch = stats[i, cv2.CC_STAT_HEIGHT]
            cx_local, cy_local = centroids[i]
            cy = y_start + cy_local
            cx = cx_local

            # Health orb must be reasonably sized (>= 0.015 of screen height)
            min_dim = max(8, int(h * 0.015))
            if cw < min_dim or ch < min_dim:
                continue

            # Must be horizontally near screen center (< 15% deviation)
            dist_from_center_x = abs(cx - screen_cx)
            if dist_from_center_x > (w * 0.15):
                continue

            # Aspect ratio should be roughly circular/elliptical (0.65 - 1.6)
            aspect = cw / float(ch) if ch > 0 else 0
            if aspect < 0.65 or aspect > 1.6:
                continue

            # Score prioritizes area and central position
            center_penalty = dist_from_center_x / float(w)
            score = area * (1.0 - center_penalty * 3.0)

            if score > best_score:
                best_score = score
                radius = max(cw, ch) / 2.0
                best_candidate = (cx, cy, radius)

        return best_candidate

    @classmethod
    def calculate_hud_bounds(
        cls,
        orb_cx: float,
        orb_cy: float,
        screen_w: int,
        screen_h: int
    ) -> Tuple[int, int, int, int]:
        """
        Calculates the tight action bar bounding box from the health orb center.
        """
        half_w = int(round(cls.HALF_WIDTH_RATIO * screen_h))
        top_h = int(round(cls.TOP_OFFSET_RATIO * screen_h))
        bot_h = int(round(cls.BOT_OFFSET_RATIO * screen_h))

        x1 = max(0, int(round(orb_cx - half_w)))
        x2 = min(screen_w, int(round(orb_cx + half_w)))
        y1 = max(0, int(round(orb_cy - top_h)))
        y2 = min(screen_h, int(round(orb_cy + bot_h)))

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        return x1, y1, w, h

    @classmethod
    def detect_hud_from_image(cls, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyzes a frame and returns full HUD bounds and bottom_center config.
        """
        h, w = frame.shape[:2]
        orb = cls.detect_health_orb(frame)

        if not orb:
            # Fallback to standard GW2 bottom-center proportions if orb not visible
            # Assumes centered at screen width / 2
            orb_cx = w / 2.0
            orb_cy = h - (cls.BOT_OFFSET_RATIO * h) - (h * 0.015)
            abs_x, abs_y, abs_w, abs_h = cls.calculate_hud_bounds(orb_cx, orb_cy, w, h)
            bc = absolute_to_bottom_center(abs_x, abs_y, abs_w, abs_h, w, h)
            return {
                "success": False,
                "message": "Health orb not detected; generated standard bottom-center fallback.",
                "abs_bounds": (abs_x, abs_y, abs_w, abs_h),
                "bottom_center": bc
            }

        ox, oy, r = orb
        abs_x, abs_y, abs_w, abs_h = cls.calculate_hud_bounds(ox, oy, w, h)
        bc = absolute_to_bottom_center(abs_x, abs_y, abs_w, abs_h, w, h)

        return {
            "success": True,
            "message": f"Detected GW2 Health Orb at ({ox:.1f}, {oy:.1f}).",
            "orb": (ox, oy, r),
            "abs_bounds": (abs_x, abs_y, abs_w, abs_h),
            "bottom_center": bc
        }

    @classmethod
    def auto_calibrate_and_save(
        cls,
        frame: Optional[np.ndarray] = None,
        settings_path: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Captures screen (or takes frame), detects HUD and exact skill squares, and saves to settings.yaml.
        """
        enable_dpi_awareness()
        screen_w, screen_h = get_screen_resolution()

        if frame is None:
            import mss
            with mss.MSS() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                frame = cv2.cvtColor(np.array(raw, dtype=np.uint8), cv2.COLOR_BGRA2BGR)

        # Primary: Use high-precision ActionSkillDetector to lock orb and all 10 square slots
        from core.skill_detector import ActionSkillDetector
        success, msg, data = ActionSkillDetector.auto_calibrate_and_save(frame=frame, settings_path=settings_path)
        if success and "region" in data:
            return True, msg, data["region"]

        # Fallback: Detect health orb and calculate default aspect-ratio bounds
        res = cls.detect_hud_from_image(frame)
        bc = res["bottom_center"]

        if not settings_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(base_dir, "config", "settings.yaml")

        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                settings = yaml.safe_load(f) or {}

        settings["region"] = bc

        with open(settings_path, "w") as f:
            yaml.safe_dump(settings, f, default_flow_style=False, sort_keys=False)

        msg = f"{res['message']} Saved bottom-center HUD parameters to {settings_path}."
        return res["success"], msg, bc

