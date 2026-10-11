"""
Unit tests for Universal Resource Perception Engine, Bottom-Center Anchoring,
and Resource-Gated Rotation Actions.
"""

import os
import sys
import unittest
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dpi_utils import bottom_center_to_absolute, absolute_to_bottom_center
from core.resource_detector import (
    DiscretePipDetector,
    ContinuousGaugeDetector,
    UniversalResourceDetector,
    ResourceState
)
from core.rotation_framework import RotationAction, RotationStateMachine
from core.rotation_parser import (
    action_to_dict,
    dict_to_action,
    ingest_llm_payload
)
from profiles.configurable_profile import ConfigurableRotationBehavior


def test_bottom_center_anchoring():
    print("[TEST 1/6] Machine-Agnostic Bottom-Center Anchor Math...")
    # Simulate an Ultrawide 2K display (2560x1080)
    screen_w_uw, screen_h_uw = 2560, 1080
    hud_w, hud_h = 1000, 220
    # Center horizontally: abs_x = (2560 - 1000) / 2 = 780
    abs_x_uw = 780
    abs_y_uw = 1080 - 220  # pinned to bottom: 860

    params = absolute_to_bottom_center(abs_x_uw, abs_y_uw, hud_w, hud_h, screen_w_uw, screen_h_uw)
    assert params["mode"] == "bottom_center"
    assert abs(params["center_offset_ratio_x"]) < 0.001, f"Expected near 0 offset, got {params['center_offset_ratio_x']}"
    assert abs(params["bottom_offset_ratio_y"]) < 0.001, f"Expected bottom offset 0, got {params['bottom_offset_ratio_y']}"

    # Now load those same parameters on a 16:9 1080p display (1920x1080)
    x1, y1, w1, h1 = bottom_center_to_absolute(
        params["center_offset_ratio_x"],
        params["bottom_offset_ratio_y"],
        params["width_ratio"],
        params["height_ratio"],
        screen_w=1920,
        screen_h=1080
    )
    # The HUD should remain centered: (1920 - 1000) / 2 = 460
    assert abs(x1 - 460) <= 2, f"Expected x ~ 460 on 1080p, got {x1}"
    assert abs(y1 - 860) <= 2, f"Expected y ~ 860 on 1080p, got {y1}"
    assert abs(w1 - 1000) <= 2, f"Expected w ~ 1000, got {w1}"
    assert abs(h1 - 220) <= 2, f"Expected h ~ 220, got {h1}"

    # Now load on a 16:9 1440p 2K display (2560x1440)
    x2, y2, w2, h2 = bottom_center_to_absolute(
        params["center_offset_ratio_x"],
        params["bottom_offset_ratio_y"],
        params["width_ratio"],
        params["height_ratio"],
        screen_w=2560,
        screen_h=1440
    )
    # Scales proportionally with 1440 / 1080 = 1.333x
    expected_w = int(round(1000 * (1440 / 1080)))
    expected_x = int(round((2560 - expected_w) / 2))
    assert abs(x2 - expected_x) <= 3, f"Expected centered x ~ {expected_x}, got {x2}"
    assert abs(w2 - expected_w) <= 3, f"Expected w ~ {expected_w}, got {w2}"
    print("  [OK] Bottom-center anchor math maintains 100% centering across Ultrawide and 16:9.")


def test_discrete_pip_detector():
    print("[TEST 2/6] DiscretePipDetector on Empty vs Filled Pips...")
    detector_3 = DiscretePipDetector(max_pips=3)
    detector_5 = DiscretePipDetector(max_pips=5)

    # 1. Synthetic empty pip strip (dark background RGB ~ 25)
    empty_strip = np.full((30, 150, 3), 25, dtype=np.uint8)
    count_3, _ = detector_3.evaluate_pips(empty_strip)
    assert count_3 == 0, f"Expected 0 active pips on empty strip, got {count_3}"

    count_5, _ = detector_5.evaluate_pips(empty_strip)
    assert count_5 == 0, f"Expected 0 active pips on empty strip, got {count_5}"

    # 2. Synthetic filled pips (bright magenta / pink glow: BGR [220, 40, 240])
    # Create 3-pip strip where pips 1 and 2 are filled, pip 3 is empty
    strip_2_of_3 = empty_strip.copy()
    strip_2_of_3[:, 10:40] = [220, 40, 240]  # Pip 1 filled
    strip_2_of_3[:, 60:90] = [220, 40, 240]  # Pip 2 filled
    # Pip 3 (100:150) remains dark

    active_count, statuses = detector_3.evaluate_pips(strip_2_of_3)
    assert active_count == 2, f"Expected 2 active pips, got {active_count}"
    assert statuses[0].is_active is True
    assert statuses[1].is_active is True
    assert statuses[2].is_active is False

    # 3. Create 5-pip strip where all 5 pips are filled (Virtuoso full blades)
    strip_5_of_5 = np.full((25, 200, 3), 20, dtype=np.uint8)
    # Fill all 5 sectors (each sector is 40px wide)
    for i in range(5):
        strip_5_of_5[:, (i * 40 + 10):(i * 40 + 30)] = [230, 50, 250]

    count_all_5, st_5 = detector_5.evaluate_pips(strip_5_of_5)
    assert count_all_5 == 5, f"Expected 5 active blades, got {count_all_5}"
    assert all(s.is_active for s in st_5)
    print("  [OK] DiscretePipDetector correctly identifies 0/3, 2/3, and 5/5 charges.")


def test_continuous_gauge_detector():
    print("[TEST 3/6] ContinuousGaugeDetector on Fill Bars...")
    gauge_det = ContinuousGaugeDetector(resource_name="life_force", max_value=100.0)

    # 1. Empty bar (dark)
    empty_gauge = np.full((12, 100, 3), 20, dtype=np.uint8)
    val_empty, pct_empty = gauge_det.evaluate_gauge(empty_gauge)
    assert val_empty == 0.0
    assert pct_empty == 0.0

    # 2. 75% filled Life Force bar (Teal / Green: BGR [180, 220, 40])
    partial_gauge = empty_gauge.copy()
    partial_gauge[:, :75] = [180, 220, 40]
    val_part, pct_part = gauge_det.evaluate_gauge(partial_gauge)
    assert abs(pct_part - 0.75) < 0.05, f"Expected ~75% fill, got {pct_part}"
    assert abs(val_part - 75.0) < 5.0, f"Expected ~75 Life Force, got {val_part}"
    print("  [OK] ContinuousGaugeDetector measured 0% and 75% fill accurately.")


def test_universal_resource_detector_facade():
    print("[TEST 4/6] UniversalResourceDetector Facade & Frame Queries...")
    spec_cfg = {
        "resource": {
            "type": "discrete_pips",
            "name": "blades",
            "max_pips": 5,
            "bbox": [0.10, 0.10, 0.40, 0.20]
        }
    }
    detector = UniversalResourceDetector(spec_config=spec_cfg)
    assert detector.resource_type == "discrete_pips"
    assert detector.max_value == 5.0

    # Create dummy HUD frame (200x500)
    hud_frame = np.full((200, 500, 3), 20, dtype=np.uint8)
    # Check on empty frame
    st = detector.get_resource_state(hud_frame)
    assert st.current_value == 0.0
    assert detector.is_resource_sufficient(hud_frame, min_required=5) is False
    assert detector.is_resource_under(hud_frame, max_allowed=2) is True

    # Paint 5 blades in the bbox region: y: [20, 60], x: [50, 250]
    for i in range(5):
        sx = 50 + i * 40 + 10
        ex = 50 + i * 40 + 30
        hud_frame[25:55, sx:ex] = [230, 45, 245]

    st_full = detector.get_resource_state(hud_frame)
    assert st_full.current_value == 5.0
    assert st_full.is_full is True
    assert detector.is_resource_sufficient(hud_frame, min_required=5) is True
    assert detector.is_resource_sufficient(hud_frame, min_required=6) is False
    print("  [OK] UniversalResourceDetector evaluated frame with sub-millisecond execution.")


def test_rotation_action_serialization():
    print("[TEST 5/6] RotationAction Serialization with min_resource & max_resource...")
    act = RotationAction(
        name="Bladesong Harmony (F1)",
        key="f1",
        cooldown=5.0,
        cast_delay=0.1,
        priority=110,
        is_instant=True,
        min_resource=5.0,
        resource_type="blades"
    )
    d = action_to_dict(act)
    assert d["min_resource"] == 5.0
    assert d["resource_type"] == "blades"

    restored = dict_to_action(d)
    assert restored.min_resource == 5.0
    assert restored.resource_type == "blades"
    assert restored.name == "Bladesong Harmony (F1)"
    assert restored.key == "f1"
    print("  [OK] RotationAction preserved min_resource and resource_type across round-trip.")


def test_configurable_rotation_behavior_resource_gating():
    print("[TEST 6/6] ConfigurableRotationBehavior Resource-Gating Execution...")
    build_data = {
        "name": "TestVirtuoso",
        "profession": "Mesmer",
        "elite_spec": "Virtuoso",
        "rotation_type": "priority_list",
        "resource": {
            "type": "discrete_pips",
            "name": "blades",
            "max_pips": 5,
            "bbox": [0.10, 0.10, 0.40, 0.20]
        },
        "priority_list": [
            {
                "name": "Bladesong Harmony (F1)",
                "key": "f1",
                "priority": 100,
                "cooldown": 5.0,
                "min_resource": 5,
                "is_instant": True
            },
            {
                "name": "Mirror Blade (Skill 2)",
                "key": "2",
                "priority": 70,
                "cooldown": 6.0
            }
        ]
    }

    behavior = ConfigurableRotationBehavior(build_data=build_data, profession="Mesmer", spec="Virtuoso")
    
    # 1. Evaluate with empty frame (0 blades)
    empty_frame = np.full((200, 500, 3), 20, dtype=np.uint8)
    ready, act = behavior.evaluate_condition(empty_frame, None)
    assert ready is True
    # F1 is blocked because 0 blades < 5 required -> Behavior falls back to Mirror Blade (2)!
    assert act.key == "2", f"Expected fallback to Skill '2' when blades < 5, got '{act.key}' ({act.name})"

    # 2. Evaluate with 5 blades filled
    full_frame = empty_frame.copy()
    for i in range(5):
        sx = 50 + i * 40 + 10
        ex = 50 + i * 40 + 30
        full_frame[25:55, sx:ex] = [230, 45, 245]

    ready2, act2 = behavior.evaluate_condition(full_frame, None)
    assert ready2 is True
    # Now F1 condition is satisfied (5/5 blades) -> Fires high-priority burst spender!
    assert act2.key == "f1", f"Expected F1 to fire when 5 blades are stocked, got '{act2.key}'"
    print("  [OK] Gating verified: F1 held at 0 blades (fallback to builder 2); F1 fired at 5 blades!")


class TestDeadeyeOnRealFrames(unittest.TestCase):
    """Real Deadeye HUD frames (3440x1440) over a bright sand background: initiative zigzag + malice arc."""

    FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "resources")

    def _read(self, name):
        img = cv2.imread(os.path.join(self.FIX, name))
        self.assertIsNotNone(img, name)
        det = UniversalResourceDetector(profession="thief", spec="deadeye")
        return det.get_resource_state(img), det.get_resource_state(img, "malice")

    def test_idle_full_initiative_no_malice(self):
        init, malice = self._read("deadeye_idle_init15_malice0.png")
        self.assertEqual((init.current_value, init.max_value), (15, 15))
        self.assertEqual((malice.current_value, malice.max_value), (0, 5))

    def test_combat_low_initiative_full_malice(self):
        init, malice = self._read("deadeye_combat_init3_malice5.png")
        self.assertEqual(init.current_value, 3)
        self.assertEqual(malice.current_value, 5)
        self.assertTrue(malice.is_full)

    def test_unknown_resource_name_raises(self):
        det = UniversalResourceDetector(profession="thief", spec="deadeye")
        with self.assertRaises(KeyError):
            det.get_resource_state(np.zeros((222, 1026, 3), np.uint8), "adrenaline")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RUNNING UNIVERSAL RESOURCE & PERCEPTION ENGINE TESTS")
    print("=" * 60 + "\n")

    test_bottom_center_anchoring()
    test_discrete_pip_detector()
    test_continuous_gauge_detector()
    test_universal_resource_detector_facade()
    test_rotation_action_serialization()
    test_configurable_rotation_behavior_resource_gating()

    print("\n" + "=" * 60)
    print("  ALL 6 RESOURCE & PERCEPTION TESTS PASSED! [100% OK]")
    print("=" * 60 + "\n")
