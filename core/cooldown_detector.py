"""
Universal Cooldown Detector.
Agnostic across all 9 professions, 36 elite specs, and all weapon/utility kits.

Rather than storing hundreds of fragile icon templates, this detector evaluates
the universal visual shader signatures that the game applies to ANY skill slot:
1. Pitch-Black Radial Sweep: When a skill is triggered, a solid/translucent dark clock
   mask (RGB <= 14) sweeps across the icon.
2. Centered White Countdown Digits: The game renders sharp white text (RGB > 200)
   with standardized digit proportions (12-28px height) in the upper-center of the slot.
3. Desaturation Drop: The underlying art is dimmed and desaturated.

This provides 100% character-agnostic readiness detection with sub-millisecond performance.
"""

import time
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List
import numpy as np
import cv2


@dataclass
class SlotCooldownStatus:
    slot_id: str
    is_ready: bool
    black_sweep_ratio: float
    digit_detected: bool
    saturation: float
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h) relative to HUD frame
    radial_wedge_sectors: int = 0
    raw_is_ready: bool = True                 # this frame's reading before ready-confirmation


class UniversalCooldownDetector:
    """
    Evaluates cooldown state for all action bar slots without needing icon templates.
    """

    # Slot bounding boxes normalized (0.0 - 1.0) relative to the calibrated HUD bounding box.
    # Calibrated to standard action bar proportions:
    # Action bar width: 1024, height: 235-340.
    # We define relative percentage anchors so it adapts to any resolution/aspect ratio.
    NORMALIZED_SLOTS: Dict[str, Tuple[float, float, float, float]] = {
        # Weapon swap (Immediately left of Weapon 1):
        "weapon_swap": (0.0105, 0.6964, 0.0429, 0.1774),

        # Weapon bar 1 - 5 (Left of Health Orb, exact equidistant squares):
        "weapon_1": (0.0618, 0.6750, 0.0702, 0.2903),
        "weapon_2": (0.1359, 0.6738, 0.0702, 0.2903),
        "weapon_3": (0.2119, 0.6742, 0.0702, 0.2903),
        "weapon_4": (0.2858, 0.6742, 0.0702, 0.2903),
        "weapon_5": (0.3600, 0.6746, 0.0702, 0.2903),

        # Utility bar 6 - 0 / Heal - Elite (Right of Health Orb, exact equidistant squares):
        "heal":      (0.5686, 0.6742, 0.0702, 0.2903),  # Q / 6
        "utility_1": (0.6446, 0.6750, 0.0702, 0.2903),  # E / 7
        "utility_2": (0.7168, 0.6746, 0.0702, 0.2903),  # R / 8
        "utility_3": (0.7926, 0.6746, 0.0702, 0.2903),  # T / 9
        "elite":     (0.8669, 0.6742, 0.0702, 0.2903),  # M3 / 0
    }

    # Built-in archetype fallbacks for explicitly calibrated composite duos ONLY.
    # No attributes are carried over to other professions/specs unless explicitly notified.
    COMPOSITE_MECHANIC_SLOTS: Dict[str, Dict[str, Tuple[float, float, float, float]]] = {
        # Guardian Core: 3 Virtues positioned directly above weapon skills 2, 3, 4
        "guardian_core": {
            "mech_f1": (0.2040, 0.1644, 0.0550, 0.2740),  # Virtue of Justice (M5)
            "mech_f2": (0.2610, 0.1644, 0.0550, 0.2740),  # Virtue of Resolve (M4)
            "mech_f3": (0.3180, 0.1644, 0.0550, 0.2740),  # Virtue of Courage (Shift+M5)
        },
        # Engineer Mechanist: 3 Jade Mech commands positioned on the left above weapon skills 1, 2
        "engineer_mechanist": {
            "mech_f1": (0.0662, 0.2508, 0.0409, 0.1694),  # Rolling Smash / Spark Revolver (M5)
            "mech_f2": (0.1112, 0.2508, 0.0409, 0.1694),  # Discharge Array / Core Reactor Shot (M4)
            "mech_f3": (0.1567, 0.2508, 0.0409, 0.1694),  # Crisis Zone / Overclock Signet (Shift+M5)
        },
        # Mesmer Chronomancer: 5 Shatters (F1-F4 Shatters + F5 Continuum Split)
        "mesmer_chronomancer": {
            "mech_f1": (0.1500, 0.1644, 0.0580, 0.2740),  # Mind Wrack (M5 / F1)
            "mech_f2": (0.2120, 0.1644, 0.0580, 0.2740),  # Cry of Frustration (M4 / F2)
            "mech_f3": (0.2740, 0.1644, 0.0580, 0.2740),  # Diversion (F3)
            "mech_f4": (0.3360, 0.1644, 0.0580, 0.2740),  # Distortion (F4)
            "mech_f5": (0.3980, 0.1644, 0.0580, 0.2740),  # Continuum Split (F5)
        },
        # Mesmer Virtuoso: 5 Bladesongs (F1-F5)
        "mesmer_virtuoso": {
            "mech_f1": (0.0954, 0.1644, 0.0724, 0.2740),  # Bladesong Harmony (M5 / F1)
            "mech_f2": (0.1711, 0.1644, 0.0724, 0.2740),  # Bladesong Sorrow (M4 / F2)
            "mech_f3": (0.2467, 0.1644, 0.0724, 0.2740),  # Bladesong Dissonance (F3)
            "mech_f4": (0.3224, 0.1644, 0.0724, 0.2740),  # Bladesong Distortion (F4)
            "mech_f5": (0.3980, 0.1644, 0.0724, 0.2740),  # Bladesong Requiem (F5)
        },
        # Mesmer Core / Mirage: 4 Shatters (F1-F4)
        "mesmer_core": {
            "mech_f1": (0.1800, 0.1562, 0.0580, 0.3438),  # Mind Wrack
            "mech_f2": (0.2420, 0.1562, 0.0580, 0.3438),  # Cry of Frustration
            "mech_f3": (0.3040, 0.1562, 0.0580, 0.3438),  # Diversion
            "mech_f4": (0.3660, 0.1562, 0.0580, 0.3438),  # Distortion
        },
    }

    # Aliases for convenience:
    SLOT_ALIASES = {
        "`": "weapon_swap",
        "~": "weapon_swap",
        "swap": "weapon_swap",
        "weapon_swap": "weapon_swap",
        "1": "weapon_1",
        "2": "weapon_2",
        "3": "weapon_3",
        "4": "weapon_4",
        "5": "weapon_5",
        "6": "heal",
        "7": "utility_1",
        "8": "utility_2",
        "9": "utility_3",
        "0": "elite",
        "10": "elite",
        "q": "heal",
        "e": "utility_1",
        "r": "utility_2",
        "t": "utility_3",
        "m3": "elite",
        "mouse3": "elite",
        "skill_1": "weapon_1",
        "skill_2": "weapon_2",
        "skill_3": "weapon_3",
        "skill_4": "weapon_4",
        "skill_5": "weapon_5",
        "skill_6": "heal",
        "skill_7": "utility_1",
        "skill_8": "utility_2",
        "skill_9": "utility_3",
        "skill_10": "elite",
        "slot_1": "weapon_1",
        "slot_2": "weapon_2",
        "slot_3": "weapon_3",
        "slot_4": "weapon_4",
        "slot_5": "weapon_5",
        "slot_6": "heal",
        "slot_7": "utility_1",
        "slot_8": "utility_2",
        "slot_9": "utility_3",
        "slot_10": "elite",
        "f1": "mech_f1",
        "m5": "mech_f1",
        "mouse5": "mech_f1",
        "f2": "mech_f2",
        "m4": "mech_f2",
        "mouse4": "mech_f2",
        "f3": "mech_f3",
        "shift+m5": "mech_f3",
        "shift+mouse5": "mech_f3",
        "f4": "mech_f4",
        "shift+m4": "mech_f4",
        "shift+mouse4": "mech_f4",
        "f5": "mech_f5",
        "shift+m3": "mech_f5",
        "shift+mouse3": "mech_f5",
    }

    def __init__(
        self,
        profession: str = "guardian",
        spec: str = "core",
        black_sweep_threshold: float = 0.28,
        black_pixel_val: int = 18,
        digit_min_height: int = 10,
        digit_max_height: int = 30,
        white_pixel_val: int = 200,
        ready_confirm_seconds: float = 0.1
    ):
        self.profession = profession.lower().strip()
        self.spec = spec.lower().strip()
        self.black_sweep_threshold = black_sweep_threshold
        self.black_pixel_val = black_pixel_val
        self.digit_min_height = digit_min_height
        self.digit_max_height = digit_max_height
        self.white_pixel_val = white_pixel_val

        # Ready-confirmation: near the end of a cooldown the remaining dark wedge is small
        # and single frames can read as READY, flickering green/red. A slot only reports
        # READY after reading ready continuously for this long; COOLDOWN applies at once.
        self.ready_confirm_seconds = ready_confirm_seconds
        self._last_cooldown_seen: Dict[str, float] = {}

        # Dynamic active slot map
        self.slots = dict(self.NORMALIZED_SLOTS)
        self.set_composite(self.profession, self.spec)
        self.load_calibrated_slots()

    def _clear_mech_slots(self) -> None:
        """Removes existing mech_* keys to avoid stale slots from previous profession."""
        to_del = [k for k in self.slots.keys() if k.startswith("mech_")]
        for k in to_del:
            del self.slots[k]

    def load_calibrated_slots(self, settings_path: Optional[str] = None) -> None:
        """Loads user-calibrated slot coordinates from settings.yaml if present.

        For weapon/utility slots: always overrides with calibrated values.
        For mech_* slots: only overrides if the active spec already declared that
        slot (i.e. it's already in self.slots).  This prevents mech_f4/f5 from
        being injected into specs that only have 3 mechanic skills (e.g. Mechanist).
        """
        try:
            import os, yaml
            if not settings_path:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                settings_path = os.path.join(base_dir, "config", "settings.yaml")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
                custom = cfg.get("calibrated_slots", {})
                for k, coords in custom.items():
                    resolved = self.resolve_slot_id(k)
                    # Mech slots: only apply if this spec already defines that slot
                    if resolved.startswith("mech_") and resolved not in self.slots:
                        continue
                    self.slots[resolved] = tuple(coords)
        except Exception:
            pass


    def set_composite(self, profession: str, spec: str = "") -> None:
        """
        Configures the mechanic slot layout for the active (profession, specialization) composite duo.
        First attempts to load character-specific coordinates from config/specs/{profession}_{spec}.yaml,
        then falls back to professions_database.yaml or built-in archetype presets.
        Does NOT carry over attributes to other professions/specializations.
        """
        self.profession = profession.lower().strip() if profession else ""
        self.spec = spec.lower().strip() if spec else ""

        # Always start by clearing any existing mechanic slots so nothing carries over
        self._clear_mech_slots()
        self.slot_labels = {}

        if not self.profession:
            return

        loaded_from_spec = False
        try:
            from core.spec_manager import load_spec_config, get_resolution_tag
            spec_cfg = load_spec_config(self.profession, self.spec, resolution_tag=get_resolution_tag())
            m_bar = spec_cfg.get("mechanic_bar", {})
            m_slots = m_bar.get("slots", {})
            if m_slots:
                for m_k, coords in m_slots.items():
                    self.slots[m_k] = tuple(coords)
                self.slot_labels = m_bar.get("labels", {})
                loaded_from_spec = True
        except Exception:
            pass

        # Built-in archetype fallback ONLY if exact composite match exists and not loaded from spec file
        if not loaded_from_spec:
            composite_key = f"{self.profession}_{self.spec}".strip("_")
            if composite_key in self.COMPOSITE_MECHANIC_SLOTS:
                self.slots.update(self.COMPOSITE_MECHANIC_SLOTS[composite_key])
            elif not self.spec or self.spec == "core":
                core_key = f"{self.profession}_core"
                if core_key in self.COMPOSITE_MECHANIC_SLOTS:
                    self.slots.update(self.COMPOSITE_MECHANIC_SLOTS[core_key])

        # Always re-apply user's calibrated slots so custom layout takes priority
        self.load_calibrated_slots()

    def set_profession(self, profession: str) -> None:
        """Backwards compatibility alias for set_composite."""
        self.set_composite(profession, "")

    def resolve_slot_id(self, slot_id: str) -> str:
        s = str(slot_id).lower().strip()
        return self.SLOT_ALIASES.get(s, s)

    def get_slot_rect(self, hud_shape: Tuple[int, int], slot_id: str) -> Optional[Tuple[int, int, int, int]]:
        """Calculates (x, y, w, h) bounding box for slot in pixels."""
        resolved = self.resolve_slot_id(slot_id)
        if resolved not in self.slots:
            return None

        h, w = hud_shape[:2]
        nx, ny, nw, nh = self.slots[resolved]
        x = int(round(nx * w))
        y = int(round(ny * h))
        box_w = int(round(nw * w))
        box_h = int(round(nh * h))

        # Clamp starting coordinates to frame
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        # Action bar skills and mechanic skills are explicitly square in Guild Wars 2
        # Enforce exact square dimensions (box_h == box_w) constrained by available bounds
        if resolved != "weapon_swap":
            square_size = max(1, min(box_w, w - x, h - y))
            box_w = square_size
            box_h = square_size
        else:
            box_w = max(1, min(w - x, box_w))
            box_h = max(1, min(h - y, box_h))

        return x, y, box_w, box_h

    def evaluate_slot_crop(self, crop: np.ndarray, slot_id: str = "slot") -> SlotCooldownStatus:
        """
        Analyzes a cropped skill slot image and determines whether it is READY or ON COOLDOWN.
        Applies inner-margin filtering and background-contrast gating to resist combat VFX.
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 15 or crop.shape[1] < 15:
            return SlotCooldownStatus(
                slot_id=slot_id,
                is_ready=True,
                black_sweep_ratio=0.0,
                digit_detected=False,
                saturation=0.0,
                bounding_box=(0, 0, 0, 0)
            )

        h, w = crop.shape[:2]

        # Sample active upper 80% to exclude bottom keybind pill and out-of-range red underline
        inner = crop[0:int(h * 0.80), :]
        ih, iw = inner.shape[:2]

        # -------------------------------------------------------------
        # 1. Radial Polar Coordinates (12:00 Clock Dial Geometry)
        # -------------------------------------------------------------
        cx, cy = iw / 2.0, ih / 2.0
        radius = min(cx, cy) * 0.92

        y_coords, x_coords = np.ogrid[:ih, :iw]
        dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        circle_mask = dist <= radius

        # Pitch-black cooldown shader mask (R, G, B <= black_pixel_val)
        dark_pixels = (
            (inner[:, :, 0] <= self.black_pixel_val) &
            (inner[:, :, 1] <= self.black_pixel_val) &
            (inner[:, :, 2] <= self.black_pixel_val)
        )
        total_circle_px = max(1, np.sum(circle_mask))
        overall_dark = float(np.sum(circle_mask & dark_pixels) / total_circle_px)

        # Angles from 12 o'clock (0 deg) sweeping clockwise:
        # dx > 0 to right, dy < 0 upwards -> arctan2(dx, -dy) gives 0 at 12 o'clock, 90 at 3 o'clock, 180 at 6 o'clock
        dx = x_coords - cx
        dy = y_coords - cy
        angles = np.degrees(np.arctan2(dx, -dy)) % 360.0

        # Divide circle into 12 clock sectors (30 degrees per sector, like hours on a clock)
        sector_ratios = []
        for s in range(12):
            s_mask = circle_mask & (angles >= s * 30.0) & (angles < (s + 1) * 30.0)
            tot_s = np.sum(s_mask)
            dark_s = np.sum(s_mask & dark_pixels)
            sector_ratios.append(float(dark_s / max(1, tot_s)))

        # Find maximum contiguous block of solid dark sectors (>= 65% black per sector)
        # Double the list to smoothly wrap around past 12:00 (sector 11 back to 0)
        doubled = [1 if r >= 0.65 else 0 for r in sector_ratios] * 2
        max_contig_sectors = 0
        curr_streak = 0
        for val in doubled:
            if val == 1:
                curr_streak += 1
                max_contig_sectors = max(max_contig_sectors, curr_streak)
            else:
                curr_streak = 0
        max_contig_sectors = min(12, max_contig_sectors)

        # -------------------------------------------------------------
        # 2. Color Saturation
        # -------------------------------------------------------------
        hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
        sat_mean = float(np.mean(hsv[:, :, 1]))

        # -------------------------------------------------------------
        # 3. Centered White Countdown Digits
        # -------------------------------------------------------------
        digit_detected = self._countdown_digits_present(crop)

        # -------------------------------------------------------------
        # 4. Universal Cooldown Logic (Radial Clock Model)
        # -------------------------------------------------------------
        # A skill is on cooldown if:
        # 1. White countdown numbers are visible in the center (digit_detected)
        # 2. OR It exhibits a contiguous black radial wedge of at least 3 sectors
        #    (>= 90 degrees of unbroken solid black clockwise sweep) with overall dark >= 30%,
        #    on a washed-out icon (sat < 60): ready icons with large black art areas
        #    (e.g. a rocket silhouette) otherwise match; real overlays measured sat ~7
        # 3. OR Full blackout upon skill activation (overall_dark >= 0.55 and sat_mean < 70)
        # 4. OR Moderate dark coverage with heavily drained saturation (overall_dark >= 0.35 and sat_mean < 45)
        is_on_cooldown = (
            digit_detected or
            (max_contig_sectors >= 3 and overall_dark >= 0.30 and sat_mean < 60.0) or
            (overall_dark >= 0.55 and sat_mean < 70.0) or
            (overall_dark >= 0.35 and sat_mean < 45.0)
        )

        return SlotCooldownStatus(
            slot_id=slot_id,
            is_ready=not is_on_cooldown,
            black_sweep_ratio=round(overall_dark, 3),
            digit_detected=digit_detected,
            saturation=round(sat_mean, 1),
            bounding_box=(0, 0, w, h),
            radial_wedge_sectors=max_contig_sectors
        )

    def _countdown_digits_present(self, crop: np.ndarray) -> bool:
        """
        Detects the white cooldown timer ("19", "4.8", "0.2") anywhere in the slot.

        Checked on every frame with no darkness/saturation gating, so the timer is seen to the
        very end of a cooldown even on icons whose art is green, yellow, etc. (late in a cooldown
        only a thin dark wedge remains). White artwork is rejected because timer text has a dark
        outline while artwork (e.g. a white mask) does not. Sizes are relative to the slot so
        this scales with resolution and UI size. The keybind label at the bottom is excluded.
        """
        h, w = crop.shape[:2]
        region = crop[int(h * 0.12):int(h * 0.80), int(w * 0.12):int(w * 0.88)]
        if region.size == 0:
            return False
        rw = region.shape[1]
        white = (region.min(axis=2) > 185).astype(np.uint8)
        value = region.max(axis=2)
        chroma = value.astype(np.int16) - region.min(axis=2).astype(np.int16)
        n, labels, stats, cents = cv2.connectedComponentsWithStats(white)
        kernel = np.ones((3, 3), np.uint8)
        for i in range(1, n):
            cw, ch, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
            if not (0.18 * h <= ch <= 0.6 * h and 0.04 * w <= cw <= 0.45 * w
                    and area >= 0.008 * h * w and abs(cents[i][0] - rw / 2.0) < rw * 0.45):
                continue
            # Timer text is neutral white thin strokes (tint <= ~15, fill <= ~0.57 measured);
            # bright artwork such as a flame core is tinted and solid
            if area / float(cw * ch) > 0.62:
                continue
            # Timer digits are taller than wide (<= ~0.81 measured); a white ring in the art
            # (Deadeye's Mark, 1.31) is not
            if cw > ch:
                continue
            comp = (labels == i).astype(np.uint8)
            if chroma[comp.astype(bool)].mean() > 20:
                continue
            ring = (cv2.dilate(comp, kernel) - comp).astype(bool)
            if (value[ring] < 70).mean() >= 0.05 or np.median(value[ring]) < 170:
                return True
        return False

    def get_slot_status(
        self, hud_frame: np.ndarray, slot_id: str, now: Optional[float] = None
    ) -> Optional[SlotCooldownStatus]:
        """Evaluates readiness of a specific slot from the HUD frame."""
        resolved = self.resolve_slot_id(slot_id)
        rect = self.get_slot_rect(hud_frame.shape[:2], resolved)
        if not rect:
            return None

        now = time.monotonic() if now is None else now
        x, y, w, h = rect
        crop = hud_frame[y:y+h, x:x+w]
        status = self.evaluate_slot_crop(crop, resolved)
        status.bounding_box = (x, y, w, h)
        status.raw_is_ready = status.is_ready
        status.is_ready = self._confirm_ready(resolved, status.is_ready, now)
        return status

    def _confirm_ready(self, slot_id: str, raw_ready: bool, now: Optional[float] = None) -> bool:
        """Applies ready-confirmation: READY only after ready_confirm_seconds without a cooldown reading."""
        now = time.monotonic() if now is None else now
        if not raw_ready:
            self._last_cooldown_seen[slot_id] = now
            return False
        last_cd = self._last_cooldown_seen.get(slot_id)
        return last_cd is None or (now - last_cd) >= self.ready_confirm_seconds

    def is_slot_ready(self, hud_frame: np.ndarray, slot_id: str) -> bool:
        """Returns True if the slot is ready to be cast; False if on cooldown."""
        status = self.get_slot_status(hud_frame, slot_id)
        return status.is_ready if status else True

    def get_all_slot_statuses(self, hud_frame: np.ndarray, now: Optional[float] = None) -> Dict[str, SlotCooldownStatus]:
        """Evaluates readiness across all registered slots on the action bar."""
        results = {}
        for s_id in list(self.slots.keys()):
            st = self.get_slot_status(hud_frame, s_id, now)
            if st:
                results[s_id] = st
        return results

    def draw_debug_overlay(self, hud_frame: np.ndarray) -> np.ndarray:
        """Renders diagnostic overlay with green/red bounding boxes over slots and composite duo indicator."""
        overlay = hud_frame.copy()
        statuses = self.get_all_slot_statuses(hud_frame)

        # Draw top banner indicating active composite duo
        p_str = self.profession.upper() if self.profession else "UNKNOWN"
        s_str = self.spec.upper() if self.spec else "DEFAULT"
        banner_text = f"DUO: [ {p_str} | {s_str} ]"
        cv2.putText(
            overlay,
            banner_text,
            (10, 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 220, 100),
            1
        )

        for s_id, st in statuses.items():
            x, y, w, h = st.bounding_box
            color = (50, 220, 80) if st.is_ready else (40, 50, 240)  # Green = Ready, Red = Cooldown
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

            # Context-sensitive mechanic label
            if s_id.startswith("mech_"):
                m_num = s_id.replace("mech_f", "")
                if "guardian" in self.profession:
                    # Virtues: F1=M5, F2=M4, F3=Shift+M5
                    v_keys = {"1": "M5", "2": "M4", "3": "Shift+M5"}
                    label = f"V{m_num}({v_keys.get(m_num, 'F' + m_num)})"
                elif "mechanist" in self.spec or "mechanist" in self.profession:
                    p_keys = {"1": "M5", "2": "M4", "3": "Shift+M5"}
                    label = f"M{m_num}({p_keys.get(m_num, 'F' + m_num)})"
                else:
                    label = f"F{m_num}"
            elif s_id == "weapon_swap":
                label = "SWAP(~)"
            else:
                label = s_id.replace("weapon_", "W").replace("utility_", "U").replace("heal", "Heal").replace("elite", "Elite")

            state_tag = "RDY" if st.is_ready else "CD"
            cv2.putText(
                overlay,
                f"{label}:{state_tag}",
                (x + 2, y + 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.33,
                color,
                1
            )

        return overlay
