"""
HUD Sub-Zone Coordinator.
Divides the calibrated HUD frame into targeted sub-regions so detectors
search only the relevant zone (e.g. mechanic zone, weapon bar, utility bar)
with sub-millisecond speed and zero false positives.
"""

from typing import Dict, Tuple
import numpy as np


class HudZones:
    """
    Sub-zones defined as relative percentages (0.0 - 1.0) of the calibrated HUD frame.
    Works identically across all screen resolutions!
    """

    # Sub-zone definitions relative to the calibrated HUD bounding box:
    ZONES: Dict[str, Tuple[float, float, float, float]] = {
        # x_start, y_start, width, height (percentages of HUD frame)
        "mechanic": (0.05, 0.00, 0.40, 0.55),     # Top-Left: Mech commands / charges / pips / F-skills
        "weapon_bar": (0.01, 0.55, 0.44, 0.45),   # Bottom-Left: Weapon Swap (~), Skills 1, 2, 3, 4, 5
        "health_globe": (0.43, 0.25, 0.16, 0.75), # Center: Health orb and endurance bar
        "buff_bar": (0.58, 0.25, 0.40, 0.30),     # Top-Right: Active boons / buff icons
        "utility_bar": (0.58, 0.55, 0.40, 0.45),  # Bottom-Right: Heal (Q), Utilities (E, R, T), Elite
    }

    @classmethod
    def get_zone(cls, hud_frame: np.ndarray, zone_name: str) -> np.ndarray:
        """
        Extracts a cropped numpy array for the requested sub-zone from the HUD frame.
        """
        if hud_frame is None or hud_frame.size == 0:
            return np.empty((0, 0, 3), dtype=np.uint8)

        if zone_name not in cls.ZONES:
            raise KeyError(f"Unknown HUD zone: '{zone_name}'. Available: {list(cls.ZONES.keys())}")

        h, w = hud_frame.shape[:2]
        zx, zy, zw, zh = cls.ZONES[zone_name]

        x1 = max(0, int(zx * w))
        y1 = max(0, int(zy * h))
        x2 = min(w, int((zx + zw) * w))
        y2 = min(h, int((zy + zh) * h))

        return hud_frame[y1:y2, x1:x2]

    @classmethod
    def get_zone_offset(cls, hud_frame: np.ndarray, zone_name: str) -> Tuple[int, int]:
        """Returns the (x_offset, y_offset) of the sub-zone within the HUD frame."""
        h, w = hud_frame.shape[:2]
        zx, zy, _, _ = cls.ZONES[zone_name]
        return int(zx * w), int(zy * h)
