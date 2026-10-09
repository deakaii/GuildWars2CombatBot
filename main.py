"""
Main Entrypoint for the Screen Monitoring & Prioritization Bot.

Usage:
  python main.py             # Runs the prioritization loop
  python main.py --calibrate # Launch visual click-and-drag screen calibrator
  python main.py --hud       # Launch live visual diagnostic HUD (read-only)
  python main.py --test-input# Test DirectInput key press with 3s countdown
"""

import os
import sys
import time
import argparse
import yaml

from core.dpi_utils import enable_dpi_awareness
from core.capture import ScreenMonitor
from core.detector import VisualDetector
from core.input_controller import InputController
from core.engine import PrioritizationEngine
from behaviors.behavior_one import BehaviorOne


def load_config(config_path: str = "config/settings.yaml") -> dict:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, config_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Configuration file not found at: {full_path}")
    with open(full_path, "r") as f:
        return yaml.safe_load(f) or {}


def test_input_mode(cfg: dict):
    """Safe test of DirectInput keystroke simulation."""
    b1_cfg = cfg.get("behavior_one", {})
    key = b1_cfg.get("key_to_press", "1")
    print("\n" + "=" * 55)
    print("  DIRECTINPUT KEY SIMULATION TEST")
    print(f"  Target Key: '{key}'")
    print("  Focus your target window now. Starting in 3 seconds...")
    print("=" * 55)
    for i in range(3, 0, -1):
        print(f"  [{i}]...")
        time.sleep(1.0)
    
    ctrl = InputController(cfg.get("stealth", {}), cfg.get("safety", {}))
    print(f"  --> Dispatching DirectInput key press '{key}' now!")
    success = ctrl.press_key(key)
    ctrl.close()
    if success:
        print("  [SUCCESS] Key press dispatched successfully.\n")
    else:
        print("  [FAILED] Key press was not sent.\n")


def main():
    enable_dpi_awareness()

    parser = argparse.ArgumentParser(description="Screen Monitoring & Prioritization Bot")
    parser.add_argument("--gui", action="store_true", help="Launch modern graphical control dashboard")
    parser.add_argument("--calibrate", action="store_true", help="Launch interactive visual region calibrator")
    parser.add_argument("--calibrate-bar", action="store_true", help="Launch interactive action bar equidistant grid calibrator")
    parser.add_argument("--auto-detect-hud", action="store_true", help="Automatically detect GW2 action bar and configure settings.yaml")
    parser.add_argument("--hud", action="store_true", help="Launch live diagnostic HUD window (read-only)")
    parser.add_argument("--profile", default="auto", help="Active character profile ('auto', 'mech', 'charges', 'guardian', etc.)")
    parser.add_argument("--profession", default=None, help="Profession for HUD or engine (e.g. Guardian, Engineer)")
    parser.add_argument("--spec", default=None, help="Specialization for HUD or engine (e.g. Core, Mechanist)")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML settings file")
    args = parser.parse_args()

    # Route sub-tools
    if args.gui:
        from tools.gui_launcher import start_gui
        start_gui()
        return

    if args.auto_detect_hud:
        from tools.auto_calibrate_hud import main as run_auto_detect
        run_auto_detect()
        return

    if args.calibrate_bar:
        from tools.calibrate_bar import BarGridCalibrator
        app = BarGridCalibrator(config_path=args.config)
        app.run()
        return

    if args.calibrate:
        from tools.calibrate_roi import RegionCalibrator
        app = RegionCalibrator(config_path=args.config)
        app.run()
        return

    if args.hud:
        from tools.live_hud import run_live_hud
        run_live_hud(config_path=args.config, profession=args.profession, spec=args.spec)
        return

    config = load_config(args.config)

    # Normal Mode: Start Prioritization Loop
    base_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(base_dir, "config", "templates")
    os.makedirs(templates_dir, exist_ok=True)

    monitor = ScreenMonitor(config.get("region", {}))
    detector = VisualDetector(templates_dir=templates_dir)
    ctrl_cfg = config.get("control", config.get("safety", {}))
    input_ctrl = InputController(config.get("stealth", {}), ctrl_cfg)

    # Initialize Profile Manager
    from profiles.profile_manager import ProfileManager
    from profiles.profile_mech import ProfileMech
    from profiles.profile_charges import ProfileCharges
    from profiles.profile_core_guardian import ProfileCoreGuardian

    profile_mgr = ProfileManager(detector)
    profile_mgr.register_profile(ProfileCoreGuardian())
    profile_mgr.register_profile(ProfileMech())
    profile_mgr.register_profile(ProfileCharges())

    # Auto-detect or select requested profile
    if args.profile.lower() != "auto":
        profile_mgr.set_active_profile(args.profile)
    else:
        # Grab initial frame to auto-detect character from mechanic zone
        initial_frame = monitor.grab_frame()
        detected = profile_mgr.auto_detect_profile(initial_frame)
        if detected:
            print(f"[Engine] Auto-detected active character: '{detected.name}'")

    engine = PrioritizationEngine(
        config=config,
        monitor=monitor,
        detector=detector,
        input_controller=input_ctrl
    )

    # Register active profile's behaviors into engine
    active_prof = profile_mgr.active_profile
    if active_prof:
        for b in active_prof.behaviors:
            engine.register_behavior(b)

    # Start loop
    engine.run_loop()


if __name__ == "__main__":
    main()

