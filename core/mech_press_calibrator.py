"""
Press-to-Locate Calibration for profession mechanic (F1-F5) slots.

Mechanic bars differ per profession/spec (count, icon size, spacing, offset), and
icon artwork fools still-image detection. Instead, this presses each mechanic skill
once and watches which square goes dark as its cooldown overlay appears:

    capture BEFORE  ->  press skill  ->  +0.5s capture  ->  +1.5s more capture

A slot is located where the area darkened in the final capture (and had already
changed at +0.5s), restricted to the band above the weapon row. Slots that don't
go on cooldown (no target, out of range, very short cooldown) are reported and
keep their existing spec positions.

NOTE: this sends real skill inputs to Guild Wars 2 and puts those skills on cooldown.
"""

import os
import time
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import cv2

# Profession skill keybind actions in config/keybinds.yaml, translated by KeybindMapper
PROFESSION_ACTIONS = ["profession_1", "profession_2", "profession_3", "profession_4", "profession_5"]

FIRST_DELAY = 0.5     # seconds after the press: change has started
CONFIRM_DELAY = 1.5   # further seconds: cooldown overlay is still there
DARKEN_THRESHOLD = 22  # grey levels an icon must darken by to count as "on cooldown"


def search_band(geom) -> Tuple[int, int, int, int]:
    """(x0, y0, x1, y1) of the area above the weapon row where mechanic icons live."""
    S = geom.slot_size
    x0 = int(geom.slots["weapon_swap"][0] - 0.3 * S)
    x1 = int(geom.orb_center[0] - geom.orb_radius * 0.6)
    y0 = int(geom.y_top - 2.2 * S)
    y1 = int(geom.y_top - 2)
    return max(0, x0), max(0, y0), x1, y1


def locate_cooldown_square(
    before: np.ndarray,
    after_first: np.ndarray,
    after_confirm: np.ndarray,
    band: Tuple[int, int, int, int],
    slot_size: int,
) -> Optional[Tuple[int, int, int, int]]:
    """
    Finds the square that went dark between `before` and `after_confirm` (and had
    changed by `after_first`). Returns (x, y, w, h) in frame coordinates, or None.
    """
    x0, y0, x1, y1 = band
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None

    def gray(img):
        g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        return cv2.GaussianBlur(g, (3, 3), 0)

    b, a1, a2 = gray(before), gray(after_first), gray(after_confirm)
    darkened = (b - a2) > DARKEN_THRESHOLD
    changed_early = np.abs(b - a1) > DARKEN_THRESHOLD * 0.5

    mask = darkened.astype(np.uint8)
    k = max(3, int(slot_size * 0.08) | 1)
    # Close the holes left by the white cooldown-timer digits, drop speckle from world motion
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    best, best_score = None, 0.0
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        side = max(w, h)
        if side < 0.35 * slot_size or side > 1.15 * slot_size:
            continue
        if not 0.6 <= w / float(h) <= 1.6:
            continue
        fill = area / float(w * h)
        if fill < 0.45:
            continue
        early = changed_early[y:y + h, x:x + w][labels[y:y + h, x:x + w] == i].mean()
        if early < 0.25:
            continue
        score = area * fill
        if score > best_score:
            best_score, best = score, (x0 + int(x), y0 + int(y), int(w), int(h))
    return best


def run_press_calibration(
    profession: str,
    spec: str,
    settings_path: Optional[str] = None,
    log=print,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Presses each of the spec's mechanic skills and saves the located squares to the
    resolution-specific spec file. Returns (success, message, {"found": {...}, "missing": [...]}).
    """
    from core.dpi_utils import enable_dpi_awareness
    from core.window_utils import find_gw2_window, bring_gw2_to_front, capture_window_client
    from core.skill_detector import ActionSkillDetector
    from core.spec_manager import load_spec_config
    from core.capture import ScreenMonitor
    from core.input_controller import InputController
    import yaml

    enable_dpi_awareness()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = settings_path or os.path.join(base_dir, "config", "settings.yaml")

    count = int(load_spec_config(profession, spec).get("mechanic_bar", {}).get("f_slots_count", 0) or 0)
    if count <= 0:
        return False, f"{profession}/{spec} has no mechanic slots (f_slots_count = 0).", {}
    count = min(count, len(PROFESSION_ACTIONS))

    hwnd = find_gw2_window()
    if not hwnd:
        return False, "Guild Wars 2 window not found.", {}
    if not bring_gw2_to_front(hwnd):
        return False, "Could not bring Guild Wars 2 to the front (it must be focused to receive key presses).", {}
    time.sleep(0.8)

    def capture():
        img = capture_window_client(hwnd)
        if img is None:
            raise RuntimeError("Could not capture the Guild Wars 2 window.")
        return img

    first = capture()
    geom = ActionSkillDetector.detect_skill_bar(first, first.shape[1], first.shape[0])
    if not geom:
        return False, "Could not find the skill bar (health orb) on screen.", {}
    band = search_band(geom)

    controller = InputController({}, {"require_game_focus": True})
    found: Dict[str, Tuple[int, int, int, int]] = {}
    missing: List[str] = []
    try:
        for idx in range(count):
            slot_id = f"mech_f{idx + 1}"
            action = PROFESSION_ACTIONS[idx]
            if controller.is_stopped():
                return False, "Emergency stop pressed; calibration aborted.", {}
            before = capture()
            log(f"[F-Calibrate] Pressing {action} ({controller.mapper.translate(action)}) for {slot_id}...")
            if not controller.press_key(action):
                missing.append(slot_id)
                log(f"[F-Calibrate] {slot_id}: key press not sent (game lost focus?).")
                continue
            time.sleep(FIRST_DELAY)
            after_first = capture()
            time.sleep(CONFIRM_DELAY)
            after_confirm = capture()
            box = locate_cooldown_square(before, after_first, after_confirm, band, geom.slot_size)
            if box:
                found[slot_id] = box
                log(f"[F-Calibrate] {slot_id}: found at {box}.")
            else:
                missing.append(slot_id)
                log(f"[F-Calibrate] {slot_id}: no cooldown appeared (needs a target, out of range, or no cooldown).")
    finally:
        controller.close()

    if not found:
        return False, "No mechanic skill went on cooldown. Target an enemy (e.g. a training golem) and retry.", \
            {"found": found, "missing": missing}

    # Icons in one bar share a row and size: use the median of what was found
    side = int(np.median([max(w, h) for _, _, w, h in found.values()]))
    row_y = int(np.median([y for _, y, _, _ in found.values()]))
    found = {k: (x + (w - side) // 2, row_y, side, side) for k, (x, y, w, h) in found.items()}

    # Normalize against the same capture region the HUD and engine use
    with open(settings_path, "r") as f:
        region = (yaml.safe_load(f) or {}).get("region", {})
    monitor = ScreenMonitor(region)
    rx, ry, rw, rh = monitor.get_roi_bounds()
    monitor.close()
    normalized = {
        k: (round((x - rx) / rw, 4), round((y - ry) / rh, 4), round(w / rw, 4), round(h / rh, 4))
        for k, (x, y, w, h) in found.items()
    }

    path = _merge_into_spec(profession, spec, normalized)
    msg = f"Located {len(found)}/{count} mechanic slots for {profession}/{spec}"
    msg += f"; saved to {os.path.basename(path)}." if path else "; could not save the spec file."
    if missing:
        msg += f" Not found (kept existing positions): {', '.join(missing)}."
    return bool(path), msg, {"found": found, "missing": missing}


def _merge_into_spec(profession: str, spec: str, normalized: Dict[str, Tuple[float, ...]]) -> Optional[str]:
    """Writes located slots into {profession}_{spec}_{WxH}.yaml, keeping slots that weren't found."""
    try:
        from core.spec_manager import load_spec_config, save_spec_config, get_resolution_tag
        res_tag = get_resolution_tag()
        data = load_spec_config(profession, spec, resolution_tag=res_tag)
        bar = dict(data.get("mechanic_bar", {}))
        slots = dict(bar.get("slots", {}))
        for k, v in normalized.items():
            slots[k] = [float(c) for c in v]
        bar["slots"] = dict(sorted(slots.items()))
        data["mechanic_bar"] = bar
        return save_spec_config(profession, spec, data, resolution_tag=res_tag)
    except Exception as e:
        print(f"[F-Calibrate] Warning: could not update spec YAML: {e}")
        return None
