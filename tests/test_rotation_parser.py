"""
Unit & Integration Tests for Standardized Rotation Ingestion,
Rotation Parser, Automated Backups, and Dynamic ConfigurableProfile.
"""

import os
import sys
import tempfile
import time
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rotation_parser import (
    dict_to_action,
    action_to_dict,
    parse_build_rotation,
    load_database,
    save_database,
    save_build,
    delete_build,
    create_database_backup
)
from profiles.configurable_profile import ConfigurableProfile, ConfigurableRotationBehavior
from core.rotation_framework import RotationPhase, RotationAction
from core.detector import VisualDetector
from core.input_controller import InputController


def test_action_serialization_roundtrip():
    print("[TEST 1/5] RotationAction Serialization & Deserialization...")
    original = RotationAction(
        name="Test Jump Shot",
        key="5",
        cooldown=18.0,
        cast_delay=0.85,
        priority=60,
        double_tap=True,
        is_auto_attack=False,
        is_instant=False,
        cancellable=False
    )
    d = action_to_dict(original)
    restored = dict_to_action(d)

    assert restored.name == original.name
    assert restored.key == original.key
    assert restored.cooldown == original.cooldown
    assert restored.cast_delay == original.cast_delay
    assert restored.priority == original.priority
    assert restored.double_tap is True
    assert restored.cancellable is False
    print("  [OK] Round-trip serialization preserved all flags and timings.")


def test_parse_standardized_and_legacy_schemas():
    print("[TEST 2/5] Parsing Standardized Schema vs Legacy Flat Format...")
    
    # 1. Standardized build
    standard_data = {
        "name": "Standardized Power Build",
        "rotation_type": "priority_list",
        "opener": [
            {"name": "Opener Skill 1", "key": "3", "cooldown": 8.0, "cast_delay": 0.4},
            {"name": "Opener Skill 2", "key": "5", "cooldown": 18.0, "double_tap": True},
        ],
        "loop": [],
        "priority_list": [
            {"name": "Loop Skill 1", "key": "2", "priority": 90, "cooldown": 8.0},
            {"name": "Loop Skill 2", "key": "1", "priority": 20, "is_auto_attack": True},
        ],
        "mechanic_skills": [
            {"name": "Pet Command", "key": "f1", "priority": 85, "is_instant": True}
        ]
    }
    parsed_std = parse_build_rotation(standard_data)
    assert parsed_std["rotation_type"] == "priority_list"
    assert len(parsed_std["opener"]) == 2
    assert len(parsed_std["loop"]) == 0
    assert len(parsed_std["priority_list"]) == 2
    assert len(parsed_std["mechanic_skills"]) == 1
    assert parsed_std["opener"][1].double_tap is True
    assert parsed_std["priority_list"][1].is_auto_attack is True

    # 2. Legacy flat format backward compatibility
    legacy_data = {
        "name": "Legacy Flat Build",
        "rotation": [
            {"name": "Skill A", "key": "1", "priority": 100},
            {"name": "Skill B", "key": "2", "priority": 50},
        ]
    }
    parsed_legacy = parse_build_rotation(legacy_data)
    assert parsed_legacy["rotation_type"] == "priority_list"
    assert len(parsed_legacy["opener"]) == 0
    assert len(parsed_legacy["priority_list"]) == 2
    assert parsed_legacy["priority_list"][0].name == "Skill A"
    print("  [OK] Both standardized and legacy flat schemas parsed accurately.")


def test_database_crud_and_automated_backups():
    print("[TEST 3/5] Database CRUD (Create, Update, Delete) & Timestamped Backups...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_professions.yaml")
        initial_db = {
            "professions": {
                "Engineer": {
                    "elite_specs": {
                        "Mechanist": {
                            "builds": []
                        }
                    }
                }
            }
        }
        with open(db_file, "w") as f:
            yaml.dump(initial_db, f)

        # 1. Save new build
        new_build = {
            "name": "Unit Test Mech",
            "rotation_type": "priority_list",
            "opener": [{"name": "Opener 1", "key": "3"}],
            "priority_list": [{"name": "Prio 1", "key": "2", "priority": 90}]
        }
        saved = save_build(db_file, "Engineer", "Mechanist", new_build)
        assert saved

        # Check backup created
        backup_dir = os.path.join(tmpdir, "backups")
        assert os.path.exists(backup_dir)
        backups = os.listdir(backup_dir)
        assert len(backups) >= 1
        assert "professions_database_" in backups[0]

        # 2. Read back
        loaded = load_database(db_file)
        b_list = loaded["professions"]["Engineer"]["elite_specs"]["Mechanist"]["builds"]
        assert len(b_list) == 1
        assert b_list[0]["name"] == "Unit Test Mech"

        # 3. Update existing build
        new_build["description"] = "Updated description"
        save_build(db_file, "Engineer", "Mechanist", new_build)
        loaded = load_database(db_file)
        b_list = loaded["professions"]["Engineer"]["elite_specs"]["Mechanist"]["builds"]
        assert len(b_list) == 1
        assert b_list[0]["description"] == "Updated description"

        # 4. Delete build
        deleted = delete_build(db_file, "Engineer", "Mechanist", "Unit Test Mech")
        assert deleted
        loaded = load_database(db_file)
        b_list = loaded["professions"]["Engineer"]["elite_specs"]["Mechanist"]["builds"]
        assert len(b_list) == 0
        print("  [OK] Create, Update, Delete, and Automated Backup verified.")


def test_configurable_profile_execution():
    print("[TEST 4/5] Dynamic ConfigurableProfile Execution & Opener Transition...")
    build_data = {
        "name": "Dynamic Test Profile",
        "rotation_type": "priority_list",
        "opener": [
            {"name": "Net Shot", "key": "3", "cooldown": 8.0, "cast_delay": 0.3},
            {"name": "Jump Shot", "key": "5", "cooldown": 18.0, "cast_delay": 0.5, "double_tap": True}
        ],
        "priority_list": [
            {"name": "Blunderbuss", "key": "2", "priority": 90, "cooldown": 8.0, "cast_delay": 0.4},
            {"name": "Rifle Burst", "key": "1", "priority": 20, "cooldown": 1.2, "is_auto_attack": True}
        ],
        "mechanic_skills": [
            {"name": "Mech F1", "key": "f1", "priority": 85, "cooldown": 8.0, "is_instant": True}
        ]
    }

    det = VisualDetector()
    prof = ConfigurableProfile(build_data, profession="engineer", spec="mechanist")
    prof.setup_behaviors(det)
    rot = prof.rotation_behavior
    rot.state_machine.cancel_slip_probability = 0.0

    mock_ctrl = InputController({}, {"require_game_focus": False})

    # Debounce mech skill to test pure weapon opener
    for m in rot.state_machine.mech_skills:
        m.last_cast_time = time.time() + 999.0

    # Step 1 of Opener: Net Shot (3)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "3" and act.name == "Net Shot"
    rot.execute_action(mock_ctrl)

    # Step 2 of Opener: Jump Shot (5)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "5" and act.name == "Jump Shot"
    assert act.double_tap is True
    rot.execute_action(mock_ctrl)

    # Opener completed -> must now be in LOOP phase
    assert rot.state_machine.phase == RotationPhase.LOOP

    # Simulate channel completion
    rot.state_machine.channel_end_time = 0.0

    # Off-cooldown priority evaluation: Blunderbuss (2) vs Rifle Burst (1)
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "2" and act.name == "Blunderbuss"
    print("  [OK] ConfigurableProfile executed Opener, double-tap, and off-cooldown loop seamlessly.")


def test_rigid_loop_configurable_profile():
    print("[TEST 5/5] Rigid Loop Sequential Profile with Auto-Attack Windows...")
    build_data = {
        "name": "Rigid Loop Test",
        "rotation_type": "rigid_loop",
        "opener": [],
        "loop": [
            {"name": "Skill 2", "key": "2", "cooldown": 8.0, "cast_delay": 0.5},
            {"name": "Auto Chain", "key": "1", "cooldown": 0.0, "cast_delay": 2.0, "is_auto_attack": True},
            {"name": "Skill 4", "key": "4", "cooldown": 12.0, "cast_delay": 0.5}
        ]
    }
    det = VisualDetector()
    prof = ConfigurableProfile(build_data, profession="guardian", spec="core")
    prof.setup_behaviors(det)
    rot = prof.rotation_behavior

    mock_ctrl = InputController({}, {"require_game_focus": False})

    # Starts in LOOP phase because opener is empty
    # Step 1: Skill 2
    matched, act = rot.evaluate_condition(None, det)
    assert matched and act.key == "2"
    rot.execute_action(mock_ctrl)

    # Step 2: Auto Chain -> yields passively
    rot.state_machine.channel_end_time = 0.0
    matched, act = rot.evaluate_condition(None, det)
    # Because Step 2 is auto_attack, evaluate_condition yields None and sets auto_attack_until
    assert not matched
    assert rot.state_machine.auto_attack_until > time.time()
    print("  [OK] Rigid Loop sequential execution and auto-attack yielding verified.")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RUNNING ROTATION PARSER & CONFIGURABLE PROFILE TESTS")
    print("=" * 60 + "\n")

    test_action_serialization_roundtrip()
    test_parse_standardized_and_legacy_schemas()
    test_database_crud_and_automated_backups()
    test_configurable_profile_execution()
    test_rigid_loop_configurable_profile()

    print("\n" + "=" * 60)
    print("  ALL 5 ROTATION PARSER TESTS PASSED! [100% OK]")
    print("=" * 60 + "\n")
