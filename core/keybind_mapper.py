"""
Keybind Mapper & Translation Layer.
Translates default game keybinds or semantic action names into the user's
customized keybinds (including Mouse 3/4/5 and Shift combos).
"""

import os
import yaml
from typing import Dict, Any, Optional


class KeybindMapper:
    """
    Translates standard game actions or default keys to the user's customized bindings.
    """

    def __init__(self, config_path: str = "config/keybinds.yaml"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, config_path)
        
        self.mappings: Dict[str, Dict[str, Any]] = {}
        self.default_to_user: Dict[str, str] = {}
        
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                data = yaml.safe_load(f) or {}
                self.mappings = data.get("keybind_mapping", {})
        
        # Build lookup tables
        for action_name, info in self.mappings.items():
            d_key = str(info.get("default", "")).lower()
            u_key = str(info.get("user", "")).lower()
            if d_key and u_key:
                self.default_to_user[d_key] = u_key

    def translate(self, action_or_key: str) -> str:
        """
        Translates a default key (e.g. '6', '7', 'f1', '0')
        OR a semantic action name (e.g. 'heal', 'utility_1', 'profession_1')
        into the user's configured keybind (e.g. 'q', 'e', 'mouse5', 'mouse3').
        """
        k = str(action_or_key).lower().strip()

        # 1. Direct semantic match (e.g. 'heal' -> 'q', 'elite' -> 'mouse3')
        if k in self.mappings:
            return self.mappings[k].get("user", k)

        # 2. Weapon swap synonyms (~ / ` / swap / weapon_swap)
        if k in ["~", "`", "swap", "weapon_swap"]:
            return self.mappings.get("weapon_swap", {}).get("user", "`")

        # 3. Default key match (e.g. '6' -> 'q', 'f1' -> 'mouse5', '0' -> 'mouse3')
        if k in self.default_to_user:
            return self.default_to_user[k]

        # 4. Otherwise return key as-is
        return k

    def get_description(self, action_or_key: str) -> str:
        """Returns human-readable description if available."""
        k = str(action_or_key).lower().strip()
        if k in self.mappings:
            return self.mappings[k].get("description", self.mappings[k].get("user", k))
        return self.translate(k)
