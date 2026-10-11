"""
Automated Guild Wars 2 Skill Bar & Square Slot Detector.
Anchors skills 1-5 (Weapon) and 6-0 (Heal/Utility/Elite) directly to the central
health orb using exact geometric proportions and 1D Sobel edge energy refinement.

Zero hardcoded crop assumptions: adapts automatically to any resolution
(1080p, 1440p, 4K, Ultrawide 21:9 / 32:9) and any game UI scale.
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import numpy as np
import cv2
import yaml

from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, absolute_to_bottom_center


@dataclass
class SkillBarGeometry:
    orb_center: Tuple[float, float]
    orb_radius: float
    slot_size: int
    y_top: int
    slots: Dict[str, Tuple[int, int, int, int]]                      # (x, y, w, h) in frame pixels
    normalized_slots: Dict[str, Tuple[float, float, float, float]]    # (nx, ny, nw, nh) relative to tight HUD ROI
    tight_roi_abs: Tuple[int, int, int, int]                         # (x, y, w, h) on captured screen
    bottom_center_roi: Dict[str, Any]                                # Aspect-ratio invariant bottom_center config


class ActionSkillDetector:
    """
    Detects the Guild Wars 2 health orb and extracts pixel-perfect square bounding boxes
    for skills 1-5 (left of orb), skills 6-0 (right of orb), weapon swap, and mechanic bar.
    """

    @staticmethod
    def detect_health_orb(frame: np.ndarray) -> Optional[Tuple[float, float, float, int, int, int, int]]:
        """
        Locates the central red health globe.
        Returns (center_x, center_y, radius, left, top, width, height) or None.
        """
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]

        # In full screen, the orb is in the bottom ~40% and middle ~30% of screen.
        # If frame is already cropped HUD, search the entire frame.
        if h > 500:
            y_start = int(h * 0.55)
            x_start = int(w * 0.25)
            x_end = int(w * 0.75)
            roi = frame[y_start:h, x_start:x_end]
            offset_x, offset_y = x_start, y_start
        else:
            roi = frame
            offset_x, offset_y = 0, 0

        rh, rw = roi.shape[:2]
        b = roi[:, :, 0].astype(int)
        g = roi[:, :, 1].astype(int)
        r = roi[:, :, 2].astype(int)

        # Distinctive Guild Wars 2 health globe red hue
        red_mask = (r > 110) & (r - b > 30) & (r - g > 18)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask.astype(np.uint8))
        if num_labels <= 1:
            return None

        best_orb = None
        best_score = -1.0
        center_x_local = rw / 2.0

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            cw = stats[i, cv2.CC_STAT_WIDTH]
            ch = stats[i, cv2.CC_STAT_HEIGHT]
            cx_local, cy_local = centroids[i]

            min_dim = max(14, int(min(rh, rw) * 0.08))
            if cw < min_dim or ch < min_dim:
                continue

            aspect = cw / float(ch) if ch > 0 else 0
            if aspect < 0.60 or aspect > 2.0:
                continue

            # Prioritize area and centrality relative to ROI
            center_penalty = abs(cx_local - center_x_local) / float(rw)
            score = area * (1.0 - center_penalty * 2.2)

            if score > best_score:
                best_score = score
                abs_cx = offset_x + cx_local
                abs_cy = offset_y + cy_local
                abs_left = offset_x + stats[i, cv2.CC_STAT_LEFT]
                abs_top = offset_y + stats[i, cv2.CC_STAT_TOP]
                radius = max(cw, ch) / 2.0
                best_orb = (abs_cx, abs_cy, radius, abs_left, abs_top, cw, ch)

        return best_orb

    @classmethod
    def detect_skill_bar(
        cls,
        frame: np.ndarray,
        screen_w: int = 0,
        screen_h: int = 0
    ) -> Optional[SkillBarGeometry]:
        """
        Analyzes game screenshot/frame, finds health orb, derives all 10 square slots,
        and returns complete mathematical SkillBarGeometry.
        """
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        if screen_w <= 0 or screen_h <= 0:
            screen_w, screen_h = w, h

        orb_info = cls.detect_health_orb(frame)
        if not orb_info:
            return None

        ocx, ocy, orb_r, oleft, otop, ocw, och = orb_info

        # -------------------------------------------------------------
        # 1. Base Geometry Estimation from Orb Dimensions
        # In GW2: Skill square size S is ~1.05 to 1.15 * orb_radius.
        # Baseline bottom is aligned with the bottom edge of the health orb.
        # -------------------------------------------------------------
        est_s = int(round(orb_r * 1.08))
        est_y_bot = int(round(ocy + orb_r * 0.95))
        est_y_top = est_y_bot - est_s

        # -------------------------------------------------------------
        # 2. 1D Sobel Edge Energy Refinement of Skill Row (Top and Bottom)
        # -------------------------------------------------------------
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        row_dy = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))

        y_search_top_min = max(0, est_y_top - 20)
        y_search_top_max = min(h - 1, est_y_top + 20)
        x_left_span = max(0, int(ocx - 4.5 * est_s))
        x_right_span = min(w - 1, int(ocx + 4.5 * est_s))

        # Scan strip to left of orb for sharp top border
        strip_l1 = max(0, int(ocx - 4.2 * est_s))
        strip_l2 = max(0, int(ocx - orb_r * 1.10))

        slice_top = row_dy[y_search_top_min:y_search_top_max, strip_l1:strip_l2]
        if slice_top.size > 0:
            best_y_top = y_search_top_min + int(np.argmax(np.mean(slice_top, axis=1)))
        else:
            best_y_top = est_y_top

        # Scan strip for bottom border
        y_search_bot_min = max(0, est_y_bot - 20)
        y_search_bot_max = min(h - 1, est_y_bot + 20)
        slice_bot = row_dy[y_search_bot_min:y_search_bot_max, strip_l1:strip_l2]
        if slice_bot.size > 0:
            best_y_bot = y_search_bot_min + int(np.argmax(np.mean(slice_bot, axis=1)))
        else:
            best_y_bot = est_y_bot

        calc_s = best_y_bot - best_y_top
        # Keep square size within valid physical GW2 UI bounds (35px - 120px)
        if 35 <= calc_s <= 120:
            S = calc_s
        else:
            S = est_s

        y_top = best_y_top

        # -------------------------------------------------------------
        # 3. Inter-Slot Spacing & Symmetrical Orb Clearance
        # -------------------------------------------------------------
        gap = max(2, int(round(S * 0.055)))
        stride = S + gap

        # Symmetrical distance from orb center to skill 5 right / skill 6 left
        d_orb_est = orb_r * 1.16

        # Refine inner edges using vertical Sobel projection
        col_dx = np.abs(cv2.Sobel(gray[y_top:y_top + S, :], cv2.CV_64F, 1, 0, ksize=3))
        col_energy = np.mean(col_dx, axis=0)

        # Search for skill 5 right edge (inner left edge of orb housing)
        s5_min = max(0, int(ocx - orb_r * 1.35))
        s5_max = max(0, int(ocx - orb_r * 0.95))
        if s5_max > s5_min and len(col_energy[s5_min:s5_max]) > 0:
            s5_right = s5_min + int(np.argmax(col_energy[s5_min:s5_max]))
        else:
            s5_right = int(round(ocx - d_orb_est))

        # Search for skill 6 left edge (inner right edge of orb housing)
        s6_min = min(w - 1, int(ocx + orb_r * 0.95))
        s6_max = min(w - 1, int(ocx + orb_r * 1.35))
        if s6_max > s6_min and len(col_energy[s6_min:s6_max]) > 0:
            s6_left = s6_min + int(np.argmax(col_energy[s6_min:s6_max]))
        else:
            s6_left = int(round(ocx + d_orb_est))

        # Enforce exact symmetry around orb center if detection deviates slightly
        d_left = ocx - s5_right
        d_right = s6_left - ocx
        symm_d = (d_left + d_right) / 2.0
        s5_right = int(round(ocx - symm_d))
        s6_left = int(round(ocx + symm_d))

        # -------------------------------------------------------------
        # 4. Generate Pixel-Perfect Bounding Boxes for All Slots
        # -------------------------------------------------------------
        slots: Dict[str, Tuple[int, int, int, int]] = {}

        # Left 5 Weapon Skills: 5, 4, 3, 2, 1 (exact squares S x S)
        for i, s_num in enumerate([5, 4, 3, 2, 1]):
            slot_x = s5_right - (i + 1) * S - i * gap
            slots[f"weapon_{s_num}"] = (slot_x, y_top, S, S)

        # Weapon Swap (directly to the left of Weapon 1)
        w1_x = slots["weapon_1"][0]
        swap_w = int(round(S * 0.72))
        swap_h = int(round(S * 0.72))
        swap_x = max(0, w1_x - swap_w - gap - 4)
        swap_y = y_top + int(round(S * 0.14))
        slots["weapon_swap"] = (swap_x, swap_y, swap_w, swap_h)

        # Right 5 Utility/Heal/Elite Skills: 6, 7, 8, 9, 0 (exact squares S x S)
        right_keys = ["heal", "utility_1", "utility_2", "utility_3", "elite"]
        for i, s_key in enumerate(right_keys):
            slot_x = s6_left + i * stride
            slots[s_key] = (slot_x, y_top, S, S)

        # Mechanic Bar Slots (F1 - F5): positioned directly above weapon skills 1 - 5
        mech_s = int(round(S * 0.72))
        mech_y = y_top - mech_s - int(round(gap * 2.2))
        mech_gap = max(2, int(round(gap * 0.85)))
        # Center 5 mechanic slots over the weapon skill row
        w1_start = slots["weapon_1"][0]
        w5_end = slots["weapon_5"][0] + S
        mech_total_w = 5 * mech_s + 4 * mech_gap
        mech_start_x = int(round((w1_start + w5_end - mech_total_w) / 2.0))

        for i, f_num in enumerate([1, 2, 3, 4, 5]):
            mx = mech_start_x + i * (mech_s + mech_gap)
            slots[f"mech_f{f_num}"] = (mx, mech_y, mech_s, mech_s)

        # -------------------------------------------------------------
        # 5. Standard HUD ROI & Normalized Coordinates Calculation
        # -------------------------------------------------------------
        if w < screen_w or h < screen_h:
            # Frame is already a cropped HUD image (e.g. captured by ScreenMonitor)
            roi_x = 0
            roi_y = 0
            roi_w = w
            roi_h = h
        else:
            # Frame is a full-screen image: use standard orb-centered HUD bounds
            half_w = int(round(0.3562 * screen_h))
            top_h = int(round(0.0917 * screen_h))
            bot_h = int(round(0.0806 * screen_h))

            roi_x = max(0, int(round(ocx - half_w)))
            roi_y = max(0, int(round(ocy - top_h)))
            roi_w = max(10, min(screen_w - roi_x, int(round(half_w * 2))))
            roi_h = max(10, min(screen_h - roi_y, int(round(top_h + bot_h))))

        # Normalized coordinates relative to the HUD ROI
        norm_slots: Dict[str, Tuple[float, float, float, float]] = {}
        for s_id, (sx, sy, sw, sh) in slots.items():
            nx = float((sx - roi_x) / float(roi_w))
            ny = float((sy - roi_y) / float(roi_h))
            nw_norm = float(sw / float(roi_w))
            nh_norm = float(sh / float(roi_h))
            norm_slots[s_id] = (round(nx, 4), round(ny, 4), round(nw_norm, 4), round(nh_norm, 4))

        # Bottom-center invariant config for settings.yaml
        bc = absolute_to_bottom_center(roi_x, roi_y, roi_w, roi_h, screen_w, screen_h)

        return SkillBarGeometry(
            orb_center=(ocx, ocy),
            orb_radius=orb_r,
            slot_size=S,
            y_top=y_top,
            slots=slots,
            normalized_slots=norm_slots,
            tight_roi_abs=(roi_x, roi_y, roi_w, roi_h),
            bottom_center_roi=bc
        )

    @classmethod
    def auto_calibrate_and_save(
        cls,
        frame: Optional[np.ndarray] = None,
        settings_path: Optional[str] = None,
        profession: Optional[str] = None,
        spec: Optional[str] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Takes full screenshot (or accepts frame), detects the action bar and all slots,
        and saves both tight region and calibrated_slots into settings.yaml.

        If profession + spec are provided, the detected mech_f* coordinates are also
        written back into config/specs/{profession}_{spec}.yaml so the spec file stays
        in sync with the current screen layout.
        """
        enable_dpi_awareness()
        screen_w, screen_h = get_screen_resolution()

        if frame is None:
            import mss
            with mss.MSS() as sct:
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(mon)
                frame = cv2.cvtColor(np.array(raw, dtype=np.uint8), cv2.COLOR_BGRA2BGR)

        geom = cls.detect_skill_bar(frame, screen_w=screen_w, screen_h=screen_h)
        if not geom:
            return False, "Could not find Guild Wars 2 health globe on screen. Ensure game is visible and not minimized.", {}

        # Resolve settings path
        if not settings_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(base_dir, "config", "settings.yaml")

        settings: Dict[str, Any] = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                settings = yaml.safe_load(f) or {}

        # Save tight region and ALL calibrated slot coordinates (including mech_* slots)
        settings["region"] = dict(geom.bottom_center_roi)
        settings["calibrated_slots"] = {k: [float(x) for x in v] for k, v in geom.normalized_slots.items()}

        with open(settings_path, "w") as f:
            yaml.safe_dump(settings, f, default_flow_style=False, sort_keys=False)

        # If profession+spec given, update the mech slot coords in the spec YAML so it
        # stays in sync. This is the key step that makes calibration persist across runs.
        if profession and spec:
            cls._update_spec_mech_slots(profession, spec, geom.normalized_slots)

        # Save visual diagnostic confirmation image to scratch/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scratch_dir = os.path.join(base_dir, "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        annotated = cls.draw_annotated_preview(frame, geom)
        cv2.imwrite(os.path.join(scratch_dir, "detected_skill_squares.png"), annotated)

        spec_note = f" Spec YAML updated for {profession}/{spec}." if profession and spec else ""
        msg = (
            f"Successfully detected Health Orb at ({geom.orb_center[0]:.0f}, {geom.orb_center[1]:.0f})! "
            f"Locked all 10 skill slots ({geom.slot_size}x{geom.slot_size}px squares) directly to the orb."
            f"{spec_note}"
        )
        return True, msg, {
            "geometry": geom,
            "region": geom.bottom_center_roi,
            "calibrated_slots": geom.normalized_slots
        }

    @classmethod
    def _update_spec_mech_slots(
        cls,
        profession: str,
        spec: str,
        normalized_slots: Dict[str, Any],
    ) -> None:
        """
        Writes the detected mech_f* coordinates back into the spec YAML file.
        Only updates standard 5-slot specs; non-5-slot specs (such as Mechanist with 3 slots,
        or specs with custom dragged layouts) are preserved so auto-HUD detection does
        not overwrite carefully calibrated positions.
        """
        try:
            from core.spec_manager import load_spec_config, save_spec_config, get_resolution_tag
            res_tag = get_resolution_tag()
            spec_data = load_spec_config(profession, spec, resolution_tag=res_tag)
            mech_bar = spec_data.get("mechanic_bar", {})
            f_count = mech_bar.get("f_slots_count", 0)

            # Only auto-update if the spec is a standard 5-slot mechanic bar
            if f_count != 5:
                print(f"[SkillDetector] Preserving custom mechanic slots for [{profession} > {spec}] ({f_count} slots).")
                return

            existing_slots = mech_bar.get("slots", {})
            updated = False
            for slot_id, coords in normalized_slots.items():
                if slot_id.startswith("mech_") and slot_id in existing_slots:
                    existing_slots[slot_id] = [round(float(v), 4) for v in coords]
                    updated = True

            if updated:
                mech_bar["slots"] = existing_slots
                spec_data["mechanic_bar"] = mech_bar
                save_spec_config(profession, spec, spec_data, resolution_tag=res_tag)
                save_spec_config(profession, spec, spec_data)
        except Exception as e:
            print(f"[SkillDetector] Warning: could not update spec YAML: {e}")

    @classmethod
    def draw_annotated_preview(cls, frame: np.ndarray, geom: SkillBarGeometry) -> np.ndarray:
        """
        Draws visual verification bounding boxes over the frame with distinct labels.
        """
        out = frame.copy()

        # Circle health orb
        ocx, ocy = int(round(geom.orb_center[0])), int(round(geom.orb_center[1]))
        cv2.circle(out, (ocx, ocy), int(round(geom.orb_radius)), (0, 0, 255), 2)
        cv2.circle(out, (ocx, ocy), 3, (0, 0, 255), -1)

        # Draw ROI outline
        rx, ry, rw, rh = geom.tight_roi_abs
        cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), (200, 200, 200), 1)

        # Left Skills 1-5 (Emerald Green)
        for num in [1, 2, 3, 4, 5]:
            k = f"weapon_{num}"
            if k in geom.slots:
                x, y, w, h = geom.slots[k]
                cv2.rectangle(out, (x, y), (x + w, y + h), (50, 230, 80), 2)
                cv2.putText(out, str(num), (x + int(w * 0.35), y + int(h * 0.65)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 230, 80), 2)

        # Weapon Swap (Magenta)
        if "weapon_swap" in geom.slots:
            x, y, w, h = geom.slots["weapon_swap"]
            cv2.rectangle(out, (x, y), (x + w, y + h), (220, 80, 240), 2)
            cv2.putText(out, "~", (x + 8, y + int(h * 0.70)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 80, 240), 2)

        # Right Skills 6-0 (Golden Amber)
        labels = [("heal", "6"), ("utility_1", "7"), ("utility_2", "8"), ("utility_3", "9"), ("elite", "0")]
        for k, lbl in labels:
            if k in geom.slots:
                x, y, w, h = geom.slots[k]
                cv2.rectangle(out, (x, y), (x + w, y + h), (0, 215, 255), 2)
                cv2.putText(out, lbl, (x + int(w * 0.35), y + int(h * 0.65)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 215, 255), 2)

        # Mechanic Bar (Cyan)
        for f in [1, 2, 3, 4, 5]:
            k = f"mech_f{f}"
            if k in geom.slots:
                x, y, w, h = geom.slots[k]
                cv2.rectangle(out, (x, y), (x + w, y + h), (255, 220, 60), 1)
                cv2.putText(out, f"F{f}", (x + 4, y + int(h * 0.75)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 220, 60), 1)

        return out
