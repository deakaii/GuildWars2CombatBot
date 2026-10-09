"""
Standardized Rotation Parser and Database Persistence Engine.
Parses combat rotations partitioned into:
1. Opener Sequence (deterministic ordered execution upon engaging)
2. Rotation Loop (rigid sequential cycle with weapon swaps & auto-attack windows)
3. Priority List (dynamic off-cooldown priority hierarchy)
4. Mechanic Skills (off-GCD / instant-cast pet commands, virtues, etc.)

Also provides safe YAML database read/write with automated timestamped backups.
"""

import os
import shutil
import time
from typing import Dict, List, Any, Optional
import yaml

from core.rotation_framework import RotationAction


def dict_to_action(data: Dict[str, Any]) -> RotationAction:
    """Converts a dictionary representation into a RotationAction instance."""
    name = str(data.get("name", "Unnamed Action"))
    key = str(data.get("key", "1"))
    cooldown = float(data.get("cooldown", 0.0))
    cast_delay = float(data.get("cast_delay", 0.45))
    priority = int(data.get("priority", 50))
    double_tap = bool(data.get("double_tap", False))
    is_auto_attack = bool(data.get("is_auto_attack", False))
    is_instant = bool(data.get("is_instant", False))
    cancellable = bool(data.get("cancellable", True))
    requires_kit = data.get("requires_kit")
    kit_toggle_key = str(data.get("kit_toggle_key", "r"))

    return RotationAction(
        name=name,
        key=key,
        cooldown=cooldown,
        requires_kit=requires_kit,
        kit_toggle_key=kit_toggle_key,
        cast_delay=cast_delay,
        priority=priority,
        is_instant=is_instant,
        cancellable=cancellable,
        is_auto_attack=is_auto_attack,
        double_tap=double_tap
    )


def action_to_dict(action: RotationAction) -> Dict[str, Any]:
    """Converts a RotationAction instance into a serialized dictionary for YAML storage."""
    d: Dict[str, Any] = {
        "name": action.name,
        "key": action.key,
    }
    if action.priority != 50:
        d["priority"] = action.priority
    if action.cooldown > 0.0:
        d["cooldown"] = round(action.cooldown, 2)
    if action.cast_delay != 0.45:
        d["cast_delay"] = round(action.cast_delay, 2)
    if action.double_tap:
        d["double_tap"] = True
    if action.is_auto_attack:
        d["is_auto_attack"] = True
    if action.is_instant:
        d["is_instant"] = True
    if not action.cancellable:
        d["cancellable"] = False
    if action.requires_kit:
        d["requires_kit"] = action.requires_kit
        d["kit_toggle_key"] = action.kit_toggle_key
    return d


def parse_build_rotation(build_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a build dictionary into typed RotationAction lists.
    Guarantees backward compatibility with older flat 'rotation:' schemas.
    
    Returns:
    {
        "rotation_type": str ("priority_list", "rigid_loop", or "hybrid"),
        "opener": List[RotationAction],
        "loop": List[RotationAction],
        "priority_list": List[RotationAction],
        "mechanic_skills": List[RotationAction],
    }
    """
    rotation_type = build_data.get("rotation_type", "priority_list")
    
    # 1. Opener sequence
    opener_raw = build_data.get("opener", [])
    opener_actions = [dict_to_action(item) for item in opener_raw if isinstance(item, dict)]

    # 2. Sequential loop
    loop_raw = build_data.get("loop", [])
    loop_actions = [dict_to_action(item) for item in loop_raw if isinstance(item, dict)]

    # 3. Dynamic priority list
    prio_raw = build_data.get("priority_list", [])
    prio_actions = [dict_to_action(item) for item in prio_raw if isinstance(item, dict)]

    # 4. Mechanic track
    mech_raw = build_data.get("mechanic_skills", [])
    mech_actions = [dict_to_action(item) for item in mech_raw if isinstance(item, dict)]

    # Backward compatibility: If no structured sections, convert flat 'rotation'
    if not opener_actions and not loop_actions and not prio_actions and "rotation" in build_data:
        legacy_rot = build_data.get("rotation", [])
        if rotation_type == "rigid_loop":
            loop_actions = [dict_to_action(item) for item in legacy_rot if isinstance(item, dict)]
        else:
            prio_actions = [dict_to_action(item) for item in legacy_rot if isinstance(item, dict)]

    # Automatic inference if rotation_type was not explicitly set
    if "rotation_type" not in build_data:
        if loop_actions and opener_actions:
            rotation_type = "hybrid"
        elif loop_actions:
            rotation_type = "rigid_loop"
        elif opener_actions and prio_actions:
            rotation_type = "hybrid"
        else:
            rotation_type = "priority_list"

    return {
        "rotation_type": rotation_type,
        "opener": opener_actions,
        "loop": loop_actions,
        "priority_list": prio_actions,
        "mechanic_skills": mech_actions,
    }


def create_database_backup(db_path: str) -> Optional[str]:
    """Creates a timestamped backup copy in config/backups/ before saving modifications."""
    if not os.path.exists(db_path):
        return None
    try:
        base_dir = os.path.dirname(os.path.abspath(db_path))
        backup_dir = os.path.join(base_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"professions_database_{timestamp}.yaml"
        backup_path = os.path.join(backup_dir, backup_filename)
        shutil.copy2(db_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"[RotationParser] Warning: Failed to create database backup: {e}")
        return None


def load_database(db_path: str) -> Dict[str, Any]:
    """Loads the YAML database safely."""
    if not os.path.exists(db_path):
        return {"professions": {}}
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {"professions": {}}
    except Exception as e:
        print(f"[RotationParser] Error reading {db_path}: {e}")
        return {"professions": {}}


def save_database(db_path: str, data: Dict[str, Any], backup: bool = True) -> bool:
    """Saves the YAML database with optional automatic timestamped backup."""
    if backup and os.path.exists(db_path):
        create_database_backup(db_path)

    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with open(db_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
        return True
    except Exception as e:
        print(f"[RotationParser] Error writing to {db_path}: {e}")
        return False


def save_build(
    db_path: str,
    profession: str,
    elite_spec: str,
    build_dict: Dict[str, Any]
) -> bool:
    """
    Creates or updates a build definition within the database.
    If a build with the same name already exists in (profession > elite_spec), it is updated.
    Otherwise, it is appended.
    """
    db = load_database(db_path)
    profs = db.setdefault("professions", {})
    prof_entry = profs.setdefault(profession, {})
    specs = prof_entry.setdefault("elite_specs", {})
    spec_entry = specs.setdefault(elite_spec, {})
    builds = spec_entry.setdefault("builds", [])

    build_name = build_dict.get("name", "").strip()
    if not build_name:
        raise ValueError("Build must have a valid 'name' attribute.")

    # Check for existing build
    found_idx = -1
    for idx, b in enumerate(builds):
        if b.get("name", "").strip().lower() == build_name.lower():
            found_idx = idx
            break

    if found_idx >= 0:
        builds[found_idx] = build_dict
    else:
        builds.append(build_dict)

    return save_database(db_path, db, backup=True)


def delete_build(
    db_path: str,
    profession: str,
    elite_spec: str,
    build_name: str
) -> bool:
    """Deletes a build definition from the database."""
    db = load_database(db_path)
    try:
        builds = db["professions"][profession]["elite_specs"][elite_spec]["builds"]
        initial_len = len(builds)
        db["professions"][profession]["elite_specs"][elite_spec]["builds"] = [
            b for b in builds if b.get("name", "").strip().lower() != build_name.strip().lower()
        ]
        if len(db["professions"][profession]["elite_specs"][elite_spec]["builds"]) < initial_len:
            return save_database(db_path, db, backup=True)
        return False
    except KeyError:
        return False
