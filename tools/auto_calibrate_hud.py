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
from core.hud_detector import AutoHUDDetector
from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, bottom_center_to_absolute


def main():
    parser = argparse.ArgumentParser(description="Auto-calibrate GW2 Action Bar Region")
    parser.add_argument("--image", type=str, default=None, help="Path to static image (optional, default captures screen)")
    parser.add_argument("--config", type=str, default="config/settings.yaml", help="Path to settings.yaml")
    args = parser.parse_args()

    enable_dpi_awareness()
    screen_w, screen_h = get_screen_resolution()
    print("=" * 65)
    print("  GUILD WARS 2 HUD AUTO-CALIBRATION")
    print(f"  - Screen Resolution: {screen_w}x{screen_h}")
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
    success, message, bc = AutoHUDDetector.auto_calibrate_and_save(frame=frame, settings_path=full_config_path)

    print("\n  Detection Result:")
    print(f"  - Status: {'SUCCESS' if success else 'WARNING'}")
    print(f"  - {message}")

    # Display calculated physical bounds on primary display
    rx, ry, rw, rh = bottom_center_to_absolute(
        bc["center_offset_ratio_x"],
        bc["bottom_offset_ratio_y"],
        bc["width_ratio"],
        bc["height_ratio"],
        screen_w,
        screen_h
    )
    print(f"\n  Calibrated Screen Region (3440x1440 Ultrawide / Native):")
    print(f"  - X: {rx}, Y: {ry}, Width: {rw}, Height: {rh}")
    print(f"  - Center Offset Ratio X: {bc['center_offset_ratio_x']}")
    print(f"  - Width Ratio: {bc['width_ratio']}")
    print(f"  - Height Ratio: {bc['height_ratio']}")
    print("\n  Settings successfully updated! Ready for Live HUD.")
    print("=" * 65)


if __name__ == "__main__":
    main()
