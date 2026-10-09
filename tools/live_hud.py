"""
Diagnostic Live HUD & Visualizer.
Streams the calibrated screen ROI in real-time, displays live FPS and detection confidence,
and visually highlights detected triggers WITHOUT sending any keystrokes.
"""

import os
import sys
import time
import yaml
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.capture import ScreenMonitor
from core.detector import VisualDetector
from core.dpi_utils import enable_dpi_awareness, get_screen_resolution


def run_live_hud(config_path: str = "config/settings.yaml", profession: str = None, spec: str = None):
    enable_dpi_awareness()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_config_path = os.path.join(base_dir, config_path)

    cfg = {}
    if os.path.exists(full_config_path):
        with open(full_config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    # Resolve profession and specialization from arguments or saved settings
    if not profession:
        profession = cfg.get("last_selected", {}).get("profession", "Guardian")
    if not spec:
        spec = cfg.get("last_selected", {}).get("elite_spec", "Core")

    region_cfg = cfg.get("region", {})
    behavior_cfg = cfg.get("behavior_one", {})
    template_name = behavior_cfg.get("template_filename", "trigger_icon.png")
    threshold = float(behavior_cfg.get("confidence_threshold", 0.82))

    from core.cooldown_detector import UniversalCooldownDetector
    from core.resource_detector import UniversalResourceDetector
    cd_det = UniversalCooldownDetector(profession=profession, spec=spec)
    res_det = UniversalResourceDetector(profession=profession, spec=spec)

    screen_w, screen_h = get_screen_resolution()
    print("\n" + "=" * 60)
    print("  LIVE DIAGNOSTIC HUD (READ-ONLY MONITORING)")
    print(f"  - Active Duo: [{profession.upper()} | {spec.upper()}]")
    print(f"  - Screen Resolution: {screen_w}x{screen_h}")
    print(f"  - Target Template: {template_name} (Threshold: {threshold})")
    print("  - Keys: [A] Auto-Detect HUD | [S] Snapshot frame | [R] Reload | [Q] Exit")
    print("=" * 60 + "\n")

    monitor = ScreenMonitor(region_cfg)
    detector = VisualDetector(templates_dir=os.path.join(base_dir, "config", "templates"))

    window_name = f"Antigrav HUD [{profession} > {spec}] (Press 'Q' to quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    prev_time = time.perf_counter()
    last_cfg_check = 0.0
    fps = 0.0

    try:
        while True:
            frame = monitor.grab_frame()
            now = time.perf_counter()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # Auto-sync with GUI selection changes in settings.yaml every 400ms
            if now - last_cfg_check > 0.40:
                last_cfg_check = now
                try:
                    if os.path.exists(full_config_path):
                        with open(full_config_path, "r") as f:
                            fresh_cfg = yaml.safe_load(f) or {}
                        sel = fresh_cfg.get("last_selected", {})
                        sel_prof = sel.get("profession", profession)
                        sel_spec = sel.get("elite_spec", spec)
                        if sel_prof != profession or sel_spec != spec:
                            profession = sel_prof
                            spec = sel_spec
                            cd_det.set_composite(profession, spec)
                            res_det.configure(profession=profession, spec=spec)
                            print(f"[HUD] Auto-switched to [{profession} > {spec}] ({len([k for k in cd_det.slots if k.startswith('mech_')])} mechanics)")
                            try:
                                cv2.setWindowTitle(window_name, f"Antigrav HUD [{profession} > {spec}] (Press 'Q' to quit)")
                            except Exception:
                                pass
                        # Also auto-sync region if changed in settings.yaml
                        fresh_reg = fresh_cfg.get("region", {})
                        if fresh_reg and fresh_reg != monitor.region_config:
                            monitor.update_roi(fresh_reg)
                            print(f"[HUD] Auto-synced updated capture region from settings.yaml: {monitor.roi}")
                except Exception:
                    pass

            # Evaluate template match
            result = detector.match_template(
                frame=frame,
                template_name=template_name,
                threshold=threshold,
                multi_scale=behavior_cfg.get("multi_scale", True),
                scale_range=tuple(behavior_cfg.get("scale_range", [0.8, 1.25])),
                scale_steps=int(behavior_cfg.get("scale_steps", 5))
            )

            # Create display image with overlay
            display = frame.copy()
            h, w = display.shape[:2]

            # Draw real-time skill slot readiness indicators using composite duo layout
            slot_statuses = cd_det.get_all_slot_statuses(frame)
            for s_id, st in slot_statuses.items():
                sx, sy, sw, sh = st.bounding_box
                box_color = (60, 220, 80) if st.is_ready else (40, 50, 230)
                cv2.rectangle(display, (sx, sy), (sx + sw, sy + sh), box_color, 2)

                # Context-sensitive mechanic label from active spec file or fallback
                if getattr(cd_det, "slot_labels", None) and s_id in cd_det.slot_labels:
                    short_name = cd_det.slot_labels[s_id]
                elif s_id.startswith("mech_"):
                    m_num = s_id.replace("mech_f", "")
                    if "guardian" in profession.lower():
                        v_names = {"1": "V1(M5)", "2": "V2(M4)", "3": "V3(Shift+M5)"}
                        short_name = v_names.get(m_num, f"V{m_num}")
                    elif "mechanist" in spec.lower() or "mechanist" in profession.lower():
                        p_names = {"1": "M1(M5)", "2": "M2(M4)", "3": "M3(Shift+M5)"}
                        short_name = p_names.get(m_num, f"M{m_num}")
                    else:
                        short_name = f"F{m_num}"
                elif s_id == "weapon_swap":
                    short_name = "SWAP(~)"
                else:
                    short_name = s_id.replace("weapon_", "W").replace("utility_", "U").replace("heal", "Heal").replace("elite", "Elite")

                tag = f"{short_name}" if st.is_ready else f"{short_name}:CD"
                cv2.putText(display, tag, (sx + 3, sy + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.33, box_color, 1)

            # Draw detection bounding box if matched
            if result.matched and result.bounding_box:
                bx, by, bw, bh = result.bounding_box
                # Glowing neon emerald box
                cv2.rectangle(display, (bx, by), (bx + bw, by + bh), (50, 230, 80), 2)
                tag = f"MATCH: {result.confidence * 100:.1f}% (x{result.best_scale:.2f})"
                cv2.putText(display, tag, (bx, max(15, by - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 230, 80), 2)
                status_color = (50, 230, 80)
                status_text = "STATE: TRIGGER DETECTED"
            else:
                score_info = f"Best: {result.confidence * 100:.1f}%" if result.confidence > 0 else "No Template Found"
                status_color = (80, 180, 255)
                status_text = f"STATE: SEARCHING ({score_info})"

            # Render resource indicator (e.g. Clones / Blades / Life Force)
            res_state = res_det.get_resource_state(frame)
            if res_state.resource_type != "none":
                crop_bbox = res_state.details.get("crop_bbox")
                if crop_bbox:
                    rx, ry, rw, rh = crop_bbox
                    cv2.rectangle(display, (rx, ry), (rx + rw, ry + rh), (220, 100, 240), 1)

            # Build telemetry strings
            mech_count = len([k for k in slot_statuses.keys() if k.startswith("mech_")])
            res_tag = f" | {res_state.resource_name.upper()}: {int(res_state.current_value)}/{int(res_state.max_value)}" if res_state.resource_type != "none" else ""
            duo_text = f"DUO: [{profession.upper()} | {spec.upper()}]{res_tag} ({mech_count} Mechanics) | FPS: {fps:.0f} | Latency: {monitor.last_latency_ms:.1f}ms"

            # Render onto dedicated outer canvas so the captured game HUD is 100% visible and unclipped
            header_h = 24
            footer_h = 24
            canvas = np.zeros((header_h + h + footer_h, w, 3), dtype=np.uint8)

            # Top Header Bar (dark charcoal background)
            canvas[0:header_h, :] = (25, 25, 25)
            cv2.putText(canvas, duo_text, (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 220, 255), 1)

            # Game capture frame in the middle (completely unobstructed)
            canvas[header_h : header_h + h, 0:w] = display

            # Bottom Footer Bar (dark charcoal background)
            canvas[header_h + h :, :] = (30, 30, 30)
            cv2.putText(canvas, status_text, (8, header_h + h + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, status_color, 1)

            cv2.imshow(window_name, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key in [ord("q"), ord("Q"), 27]:  # 27 = ESC
                break
            elif key in [ord("a"), ord("A")]:
                from core.hud_detector import AutoHUDDetector
                success, msg, bc = AutoHUDDetector.auto_calibrate_and_save(settings_path=full_config_path)
                print(f"[HUD] Auto-Detect: {msg}")
                monitor.update_roi(bc)
                last_cfg_check = 0.0
            elif key in [ord("r"), ord("R")]:
                last_cfg_check = 0.0
                print(f"[HUD] Refreshed [{profession} > {spec}] layout and calibrated slots.")
            elif key in [ord("s"), ord("S")]:
                out_path = os.path.join(base_dir, "config", "templates", template_name)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                cv2.imwrite(out_path, frame)
                print(f"[HUD] Saved snapshot of current ROI to {out_path}")

    finally:
        monitor.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_live_hud()
