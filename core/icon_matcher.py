"""
Skill icon matching: does a skill-bar slot currently show a given skill (by GW2 API id)?

Used for slots whose skill changes in place, e.g. a Deadeye's skill 1 turning into the
stealth attack (Malicious Death's Judgment) while stealthed. Icons are the API's 128 px PNGs
cached in config/templates/skills/{id}.png (downloaded on first use). Matching follows the
F-skill rule: trim the 16 px border, scale to the slot, compare the top 60% (the keybind
label covers the bottom) by normalized correlation.

Measured on a live 3440x1440 recording: the stealth attack scored 0.44-0.65 while shown and
<= 0.03 otherwise, so 0.35 separates them.
"""

import json
import os
import urllib.request
from typing import Dict

import cv2
import numpy as np

SKILL_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "templates", "skills")
SHOWS_THRESHOLD = 0.35


def icon_path(skill_id: int) -> str:
    return os.path.join(SKILL_ICONS_DIR, f"{int(skill_id)}.png")


def ensure_icon(skill_id: int) -> str:
    """Returns the cached icon path, downloading it from the GW2 API if needed."""
    path = icon_path(skill_id)
    if os.path.exists(path):
        return path
    os.makedirs(SKILL_ICONS_DIR, exist_ok=True)
    headers = {"User-Agent": "GuildWars2CombatBot"}
    with urllib.request.urlopen(urllib.request.Request(
            f"https://api.guildwars2.com/v2/skills/{int(skill_id)}", headers=headers), timeout=30) as resp:
        url = json.load(resp)["icon"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp, open(path, "wb") as f:
        f.write(resp.read())
    return path


class IconMatcher:
    def __init__(self):
        self._icons: Dict[int, np.ndarray] = {}

    def _icon(self, skill_id: int) -> np.ndarray:
        if skill_id not in self._icons:
            img = cv2.imread(ensure_icon(skill_id))
            if img is None:
                raise ValueError(f"Could not read icon for skill {skill_id}")
            self._icons[skill_id] = img[16:112, 16:112]
        return self._icons[skill_id]

    def score(self, crop: np.ndarray, skill_id: int) -> float:
        if crop is None or crop.size == 0:
            return -1.0
        h, w = crop.shape[:2]
        icon = cv2.resize(self._icon(skill_id), (w, h), interpolation=cv2.INTER_AREA)
        top = max(2, int(h * 0.6))
        a = cv2.cvtColor(crop[:top], cv2.COLOR_BGR2GRAY).astype(np.float32)
        b = cv2.cvtColor(icon[:top], cv2.COLOR_BGR2GRAY).astype(np.float32)
        return float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])

    def shows(self, crop: np.ndarray, skill_id: int, threshold: float = SHOWS_THRESHOLD) -> bool:
        return self.score(crop, skill_id) >= threshold
