"""
Profile Manager for Multi-Character Support.
Manages up to 8 character profiles, handles auto-detection via the top-left mechanic zone,
and enables hotkey profile swapping.
"""

from typing import Dict, List, Optional
import numpy as np

from profiles.base_profile import BaseCharacterProfile
from core.hud_zones import HudZones
from core.detector import VisualDetector


class ProfileManager:
    """
    Registry and switchboard for all character profiles.
    """

    def __init__(self, detector: VisualDetector):
        self.detector = detector
        self.profiles: Dict[str, BaseCharacterProfile] = {}
        self.profile_list: List[BaseCharacterProfile] = []
        self.active_profile: Optional[BaseCharacterProfile] = None

    def register_profile(self, profile: BaseCharacterProfile) -> None:
        """Registers a character profile and initializes its behaviors."""
        profile.setup_behaviors(self.detector)
        self.profiles[profile.name.lower()] = profile
        self.profile_list.append(profile)
        print(f"[ProfileManager] Registered '{profile.name}' with {len(profile.behaviors)} behaviors.")

        if self.active_profile is None:
            self.active_profile = profile

    def set_active_profile(self, identifier: str) -> bool:
        """Sets active profile by name or 1-based index (e.g. '1', 'mech')."""
        key = identifier.lower().strip()
        if key in self.profiles:
            self.active_profile = self.profiles[key]
            print(f"\n[PROFILE ACTIVATED] Switched to '{self.active_profile.name}'")
            return True

        # Check index
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(self.profile_list):
                self.active_profile = self.profile_list[idx]
                print(f"\n[PROFILE ACTIVATED] Switched to '{self.active_profile.name}' (#{idx + 1})")
                return True

        return False

    def auto_detect_profile(self, hud_frame: np.ndarray) -> Optional[BaseCharacterProfile]:
        """
        Inspects the top-left mechanic zone of the HUD to identify which of the 8
        characters is currently active on screen.
        """
        if hud_frame is None or hud_frame.size == 0:
            return None

        mech_zone = HudZones.get_zone(hud_frame, "mechanic")

        for profile in self.profile_list:
            if profile.is_active_character(mech_zone, self.detector):
                if self.active_profile != profile:
                    print(f"\n[AUTO-DETECT] Identified character on screen: '{profile.name}'!")
                    self.active_profile = profile
                return profile

        return self.active_profile
