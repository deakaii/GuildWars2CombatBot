"""
Automated unit & integration test suite for the screen monitoring prioritization engine.
Validates capture, perception, priority order, cooldowns, and safety kill-switch.
"""

import os
import sys
import time
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, normalized_to_absolute, absolute_to_normalized
from core.capture import ScreenMonitor
from core.detector import VisualDetector, DetectionResult
from core.input_controller import InputController
from core.engine import PrioritizationEngine
from behaviors.base import BaseBehavior


def test_dpi_and_resolutions():
    print("[TEST 1/5] DPI Awareness & Resolution Scaling...")
    assert enable_dpi_awareness() in [True, False]
    w, h = get_screen_resolution()
    assert w > 0 and h > 0, f"Invalid screen resolution: {w}x{h}"
    
    # Test normalized conversion round-trip
    nx, ny, nw, nh = 0.25, 0.50, 0.10, 0.20
    ax, ay, aw, ah = normalized_to_absolute(nx, ny, nw, nh, w, h)
    rx, ry, rw, rh = absolute_to_normalized(ax, ay, aw, ah, w, h)
    
    assert abs(rx - nx) < 0.01
    assert abs(ry - ny) < 0.01
    print(f"  [OK] Screen: {w}x{h} px | Round-trip normalized coordinates passed.")


def test_screen_capture():
    print("[TEST 2/5] Passive Screen Capture Latency & Dimensions...")
    region_cfg = {"mode": "absolute", "abs_x": 100, "abs_y": 100, "abs_w": 200, "abs_h": 150}
    with ScreenMonitor(region_cfg) as monitor:
        frame = monitor.grab_frame()
        assert frame is not None
        assert frame.shape == (150, 200, 3)
        assert monitor.last_latency_ms < 50.0  # Should be ultrafast (< 10ms typically)
        print(f"  [OK] Frame captured: shape={frame.shape}, latency={monitor.last_latency_ms:.2f}ms")


def test_detector_multiscale():
    print("[TEST 3/5] Visual Perception & Multi-Scale Template Matching...")
    # Create synthetic frame and template
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    # Draw a distinct pattern
    cv2.circle(frame, (150, 100), 25, (0, 255, 200), -1)
    cv2.rectangle(frame, (140, 90), (160, 110), (0, 0, 255), -1)

    # Crop out the icon to serve as template
    template_crop = frame[75:125, 125:175]
    
    detector = VisualDetector()
    detector._template_cache["synthetic_icon.png"] = template_crop

    # Exact scale match
    res_exact = detector.match_template(frame, "synthetic_icon.png", threshold=0.85, multi_scale=True)
    assert res_exact.matched
    assert res_exact.confidence > 0.95
    print(f"  [OK] Exact match confidence: {res_exact.confidence * 100:.1f}%")

    # Scaled frame (simulating different screen resolution)
    scaled_frame = cv2.resize(frame, (int(300 * 1.15), int(200 * 1.15)))
    res_scaled = detector.match_template(scaled_frame, "synthetic_icon.png", threshold=0.80, multi_scale=True)
    assert res_scaled.matched
    print(f"  [OK] Multi-scale match across resolution shift: {res_scaled.confidence * 100:.1f}% at scale {res_scaled.best_scale}")


def test_priority_and_cooldown_logic():
    print("[TEST 4/5] Prioritization Engine Hierarchy & Cooldowns...")
    
    class MockBehavior(BaseBehavior):
        def __init__(self, name, priority, cooldown, should_match=True):
            super().__init__(name, priority, cooldown, cooldown_jitter_ratio=0.0)
            self.should_match = should_match
            self.actions_fired = 0

        def evaluate_condition(self, frame, detector):
            return self.should_match, None

        def execute_action(self, input_ctrl):
            self.actions_fired += 1
            return True

    # High priority vs Low priority
    high_p = MockBehavior("EmergencyHeal", priority=100, cooldown=1.0)
    low_p = MockBehavior("BasicRotation", priority=10, cooldown=0.2)

    cfg = {"timing": {"tick_interval": 0.05, "tick_jitter_range": [0, 0]}}
    region = {"mode": "absolute", "abs_x": 0, "abs_y": 0, "abs_w": 50, "abs_h": 50}
    
    monitor = ScreenMonitor(region)
    detector = VisualDetector()
    input_ctrl = InputController({}, {"emergency_stop_key": "f12", "require_game_focus": False})

    engine = PrioritizationEngine(cfg, monitor, detector, input_ctrl)
    engine.register_behavior(low_p)
    engine.register_behavior(high_p)

    # First tick: Both conditions match. High priority (100) MUST fire first!
    fired_1 = engine.run_tick()
    assert fired_1 == "EmergencyHeal"
    assert high_p.actions_fired == 1
    assert low_p.actions_fired == 0
    print("  [OK] Tick 1: High priority preempted low priority correctly.")

    # Second tick (immediately after): High priority is on cooldown, so Low priority MUST fire!
    fired_2 = engine.run_tick()
    assert fired_2 == "BasicRotation"
    assert low_p.actions_fired == 1
    print("  [OK] Tick 2: Cooldown respected, low priority fired while high was on cooldown.")


    monitor.close()
    input_ctrl.close()


def test_safety_killswitch():
    print("[TEST 5/5] Safety Kill-Switch Suppression...")
    ctrl = InputController({}, {"emergency_stop_key": "f12", "require_game_focus": False})
    assert not ctrl.is_stopped()

    # Trigger emergency stop
    ctrl.trigger_emergency_stop()
    assert ctrl.is_stopped()
    
    # Try sending key while stopped
    dispatched = ctrl.press_key("1")
    assert dispatched is False, "InputController dispatched key even after emergency stop!"
    print("  [OK] Kill-switch immediately suppresses and blocks input simulation.")
    ctrl.close()


def test_hud_zones_and_profiles():
    print("[TEST 6/6] HUD Sub-Zones & Multi-Character Auto-Detection...")
    from core.hud_zones import HudZones
    from profiles.profile_manager import ProfileManager
    from profiles.profile_mech import ProfileMech
    from profiles.profile_charges import ProfileCharges

    # Test synthetic HUD
    hud = np.zeros((284, 1024, 3), dtype=np.uint8)
    mech_zone = HudZones.get_zone(hud, "mechanic")
    assert mech_zone.shape[0] > 0 and mech_zone.shape[1] > 0
    weapon_zone = HudZones.get_zone(hud, "weapon_bar")
    assert weapon_zone.shape[0] > 0 and weapon_zone.shape[1] > 0

    det = VisualDetector()
    pm = ProfileManager(det)
    pm.register_profile(ProfileMech())
    pm.register_profile(ProfileCharges())

    assert len(pm.profile_list) == 2
    assert pm.set_active_profile("ChargeCharacter")
    assert pm.active_profile.name == "ChargeCharacter"
    assert pm.set_active_profile("1")
    assert pm.active_profile.name == "MechEngineer"
    print("  [OK] HUD Sub-Zones and ProfileManager registration & switching verified.")


def test_universal_cooldown_detection():
    print("[TEST 7/7] Universal Character-Agnostic Cooldown & Readiness Detector...")
    from core.cooldown_detector import UniversalCooldownDetector

    detector = UniversalCooldownDetector()

    # 1. Test synthetic ready slot (bright, high saturation, no black sweep, no digits)
    ready_slot = np.full((76, 76, 3), (40, 180, 230), dtype=np.uint8)  # Bright orange/gold skill
    cv2.circle(ready_slot, (38, 38), 20, (20, 220, 255), -1)
    status_ready = detector.evaluate_slot_crop(ready_slot, "test_slot")
    assert status_ready.is_ready, f"Ready slot flagged as cooldown: {status_ready}"

    # 2. Test synthetic cooldown slot (black sweep mask covering 60% of icon)
    cd_slot = ready_slot.copy()
    cd_slot[0:55, 0:76] = 5  # Pitch black sweep overlay (RGB <= 14)
    status_cd = detector.evaluate_slot_crop(cd_slot, "test_slot")
    assert not status_cd.is_ready, f"Cooldown slot flagged as ready: {status_cd}"
    assert status_cd.black_sweep_ratio >= 0.30

    # 3. Test synthetic digit overlay (white countdown text '15' rendered on icon)
    digit_slot = ready_slot.copy()
    digit_slot[0:50, :] = 10  # Dark background
    cv2.putText(digit_slot, "15", (22, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (245, 245, 245), 2)
    status_digit = detector.evaluate_slot_crop(digit_slot, "test_slot")
    assert not status_digit.is_ready, f"Slot with countdown digit flagged as ready: {status_digit}"
    assert status_digit.digit_detected

    print("  [OK] Universal Cooldown Detector successfully discriminates Ready vs Cooldown across sweep & digits.")


def test_human_eager_skill_cancelling():
    print("[TEST 8/8] Human Imperfection: ~15% Eager Skill Cancellation Slips...")
    from core.rotation_framework import RotationStateMachine, RotationAction, RotationPhase

    # 1. 100% slip test: eagerly clips channel early when higher priority skill is ready
    sm_slip = RotationStateMachine("TestEager", cancel_slip_probability=1.0)
    sm_slip.phase = RotationPhase.LOOP
    sm_slip.set_loop_skills([
        RotationAction("Blunderbuss", "2", 8.0, priority=90),
        RotationAction("Overcharged Shot", "4", 12.0, priority=60, cancellable=True, cast_delay=1.0)
    ])
    now = time.time()
    overcharge = sm_slip.loop_skills[1]
    sm_slip.record_action_cast(overcharge, now)

    # Candidate 0.2s later (mid-channel)
    clipped = sm_slip.get_next_action(now + 0.2)
    assert clipped is not None and clipped.name == "Blunderbuss", f"Expected eager clip, got: {clipped}"

    # 2. 0% slip test: patient human waits for channel to complete
    sm_patient = RotationStateMachine("TestPatient", cancel_slip_probability=0.0)
    sm_patient.phase = RotationPhase.LOOP
    sm_patient.set_loop_skills([
        RotationAction("Blunderbuss", "2", 8.0, priority=90),
        RotationAction("Overcharged Shot", "4", 12.0, priority=60, cancellable=True, cast_delay=1.0)
    ])
    sm_patient.record_action_cast(sm_patient.loop_skills[1], now)
    waited = sm_patient.get_next_action(now + 0.2)
    assert waited is None, f"Expected channel lock, got: {waited}"

    print("  [OK] Channel protection and humanized ~15% eager cancellation slips verified.")


def test_core_guardian_profile():
    print("[TEST 9/9] Core Guardian Profile (Sword/Focus + Greatsword & Passive Auto-Attacking)...")
    from profiles.profile_core_guardian import ProfileCoreGuardian
    from core.rotation_framework import RotationPhase
    from core.detector import VisualDetector

    det = VisualDetector()
    prof = ProfileCoreGuardian()
    prof.setup_behaviors(det)
    assert len(prof.behaviors) == 1

    rot = prof.rotation_behavior
    assert rot.active_weapon_set == "sword_focus"

    # 1. Opener step 1: Shield of Wrath (Focus 5)
    matched, act = rot.evaluate_condition(None, det)
    assert matched
    assert act.name == "Shield of Wrath (Focus 5)"
    assert act.key == "5"
    mock_ctrl = InputController({}, {"require_game_focus": False})
    rot.execute_action(mock_ctrl)

    # 2. Advance opener steps 2-5 through to Weapon Swap
    for _ in range(4):
        _, a = rot.evaluate_condition(None, det)
        rot.execute_action(mock_ctrl)
    
    # Step 6 of opener is Weapon Swap (`)
    _, swap_act = rot.evaluate_condition(None, det)
    assert swap_act.key == "`"
    rot.execute_action(mock_ctrl)
    assert rot.active_weapon_set == "greatsword"

    # 3. Sequential Looping and Passive Auto-Attack test:
    assert len(rot.state_machine.loop_steps) == 19
    # Debounce off-GCD virtues to test pure weapon auto-attack yielding
    for m in rot.state_machine.mech_skills:
        m.last_cast_time = time.time() + 100.0

    # When in an auto-attack window, evaluate_condition MUST return False
    # to let the game auto-attack passively without hammering '1'!
    rot.state_machine.auto_attack_until = time.time() + 10.0
    matched_auto, _ = rot.evaluate_condition(None, det)
    assert not matched_auto, "Bot should yield and NOT press key 1 during passive auto-attack window!"

    rot.state_machine.auto_attack_until = 0.0
    print("  [OK] Core Guardian opener, weapon swap, and passive auto-attack policy verified.")


def test_power_mechanist_rotation():
    print("[TEST 10/10] Power Mechanist Profile (Rifle Opener, Off-Cooldown Priority, and Double-Tap)...")
    from profiles.profile_power_mechanist import ProfilePowerMechanist
    from core.rotation_framework import RotationPhase
    from core.detector import VisualDetector

    det = VisualDetector()
    prof = ProfilePowerMechanist()
    prof.setup_behaviors(det)
    rot = prof.rotation_behavior
    rot.state_machine.cancel_slip_probability = 0.0

    mock_ctrl = InputController({}, {"require_game_focus": False})

    # Debounce mech skills to test clean Rifle rotation sequence
    for m in rot.state_machine.mech_skills:
        m.last_cast_time = time.time() + 999.0

    # 1. Opener Step 1: Net Shot (3)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "3" and "Net Shot" in act.name
    rot.execute_action(mock_ctrl)

    # 2. Opener Step 2: Blunderbuss (2)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "2" and "Blunderbuss" in act.name
    rot.execute_action(mock_ctrl)

    # 3. Opener Step 3: Overcharged Shot (4)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "4" and "Overcharged Shot" in act.name
    rot.execute_action(mock_ctrl)

    # 4. Opener Step 4: Jump Shot (5) - Ground Targeted Double-Tap!
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "5" and "Jump Shot" in act.name
    assert act.double_tap is True
    rot.execute_action(mock_ctrl)

    # Opener must now be complete, transitioning into LOOP phase!
    assert rot.state_machine.phase == RotationPhase.LOOP

    # 5. Off-cooldown priority testing:
    # Clear channel lock from opener's Jump Shot to simulate channel completion
    rot.state_machine.channel_end_time = 0.0
    now = time.time()
    for s in rot.state_machine.loop_skills:
        s.last_cast_time = now

    # A) Only Blunderbuss is off cooldown -> Must pick Blunderbuss (2)
    for s in rot.state_machine.loop_skills:
        if s.key == "2":
            s.last_cast_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "2"

    # B) Put Blunderbuss on CD, make Net Shot ready -> Must pick Net Shot (3)
    for s in rot.state_machine.loop_skills:
        if s.key == "2":
            s.last_cast_time = now
        elif s.key == "3":
            s.last_cast_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "3"

    # C) Put Net Shot on CD, make Overcharged Shot ready -> Must pick Overcharged Shot (4)
    for s in rot.state_machine.loop_skills:
        if s.key == "3":
            s.last_cast_time = now
        elif s.key == "4":
            s.last_cast_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "4"

    # D) Put Overcharged Shot on CD, make Jump Shot ready -> Must pick Jump Shot (5, double_tap=True)
    for s in rot.state_machine.loop_skills:
        if s.key == "4":
            s.last_cast_time = now
        elif s.key == "5":
            s.last_cast_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "5" and act.double_tap is True

    # E) Put Jump Shot on CD, make Throw Mine ready -> Must pick Throw Mine (e, double_tap=True)
    for s in rot.state_machine.loop_skills:
        if s.key == "5":
            s.last_cast_time = now
        elif s.key.lower() == "e":
            s.last_cast_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key.lower() == "e" and act.double_tap is True

    print("  [OK] Power Mechanist 4-step Opener and off-cooldown priority hierarchy verified.")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RUNNING PIPELINE INTEGRATION TESTS")
    print("=" * 60 + "\n")
    
    test_dpi_and_resolutions()
    test_screen_capture()
    test_detector_multiscale()
    test_priority_and_cooldown_logic()
    test_safety_killswitch()
    test_hud_zones_and_profiles()
    test_universal_cooldown_detection()
    test_human_eager_skill_cancelling()
    test_core_guardian_profile()
    test_power_mechanist_rotation()
    
    print("\n" + "=" * 60)
    print("  ALL 10 INTEGRATION TESTS PASSED PERFECTLY! [100% OK]")
    print("=" * 60 + "\n")



