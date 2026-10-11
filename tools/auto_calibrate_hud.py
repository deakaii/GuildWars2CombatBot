"""
Standalone Auto-Calibration Tool for Guild Wars 2 HUD.
Run this tool to automatically detect the health globe and configure
the screen capture Region of Interest (ROI) for settings.yaml.
Supports single-monitor, multi-monitor, and ultrawide setups.
"""

import os
import sys
import argparse
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, bottom_center_to_absolute


def main():
    parser = argparse.ArgumentParser(description="Auto-calibrate GW2 Action Bar Region")
    parser.add_argument("--image", type=str, default=None,
                        help="Path to static image (optional, default captures screen)")
    parser.add_argument("--config", type=str, default="config/settings.yaml",
                        help="Path to settings.yaml")
    parser.add_argument("--profession", type=str, default=None,
                        help="Active profession, e.g. 'engineer'. "
                             "Writes calibrated mech coords back into the spec YAML.")
    parser.add_argument("--spec", type=str, default=None,
                        help="Active elite spec, e.g. 'mechanist'. Used with --profession.")
    args = parser.parse_args()

    enable_dpi_awareness()
    screen_w, screen_h = get_screen_resolution()
    print("=" * 65)
    print("  GUILD WARS 2 HUD AUTO-CALIBRATION")
    print(f"  - Screen Resolution: {screen_w}x{screen_h}")
    if args.profession and args.spec:
        print(f"  - Active Spec: {args.profession.title()} / {args.spec.title()}")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_config_path = os.path.join(base_dir, args.config)

    frame = None
    if args.image:
        if os.path.exists(args.image):
            frame = cv2.imread(args.image)
            print(f"  - Using reference image: {args.image}")
        else:
            print(f"  [ERROR] Image not found: {args.image}")
            sys.exit(1)

    print("  - Scanning display for GW2 Health Orb...")

    # Use ActionSkillDetector directly so we can pass profession/spec
    from core.skill_detector import ActionSkillDetector
    success, message, data = ActionSkillDetector.auto_calibrate_and_save(
        frame=frame,
        settings_path=full_config_path,
        profession=args.profession,
        spec=args.spec,
    )

    bc = data.get("region", {})

    print("\n  Detection Result:")
    print(f"  - Status: {'SUCCESS' if success else 'WARNING'}")
    print(f"  - {message}")

    if success and bc:
        rx, ry, rw, rh = bottom_center_to_absolute(
            bc["center_offset_ratio_x"],
            bc["bottom_offset_ratio_y"],
            bc["width_ratio"],
            bc["height_ratio"],
            screen_w,
            screen_h
        )
        print(f"\n  Calibrated Screen Region:")
        print(f"  - X: {rx}, Y: {ry}, Width: {rw}, Height: {rh}")
        print(f"  - Width Ratio:  {bc['width_ratio']}")
        print(f"  - Height Ratio: {bc['height_ratio']}")

        # Print slot coordinate table so you can immediately verify alignment
        calibrated = data.get("calibrated_slots", {})
        if calibrated:
            print("\n  Calibrated Slot Coordinates (nx, ny, nw, nh):")
            print(f"  {'Slot':<16} {'NX':>7} {'NY':>7} {'NW':>7} {'NH':>7}")
            print("  " + "-" * 44)
            for slot_name in sorted(calibrated.keys()):
                c = calibrated[slot_name]
                if hasattr(c, '__iter__') and len(tuple(c)) == 4:
                    c = tuple(c)
                    print(f"  {slot_name:<16} {c[0]:>7.4f} {c[1]:>7.4f} {c[2]:>7.4f} {c[3]:>7.4f}")

    if not success:
        print("\n  [!] Auto-detection failed. Make sure GW2 is running,")
        print("      the character is in a zone (not in a menu), and")
        print("      the health globe is fully visible on screen.")
        print("  [!] Use tools/calibrate_bar.py for manual calibration.")

    print("\n  Settings successfully updated! Ready for Live HUD.")
    print("=" * 65)


if __name__ == "__main__":
    main()
