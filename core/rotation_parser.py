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
import re
import json
import shutil
import time
from typing import Dict, List, Any, Optional
import yaml

from core.rotation_framework import RotationAction


STANDARDIZED_LLM_TEMPLATE = """You are an expert Guild Wars 2 Combat Rotation Serializer for an automated rotation engine.
Convert the provided combat rotation guide/text into a strictly valid JSON object matching the exact schema below.

================================================================================
CRITICAL ENGINE CAPABILITIES & ROTATION TYPES:
================================================================================
Our rotation engine executes three distinct rotation archetypes. You MUST set "rotation_type" to one of:
1. "strict_rotation" (or "rigid_loop"):
   - For builds with a deterministic, repeating step-by-step skill sequence (e.g. Core Guardian GS/Sword loop, Condition Firebrand, Power Chronomancer).
   - "opener": Strict ordered sequence executed ONCE on combat pull.
   - "loop": Strict ordered cycle that repeats indefinitely until combat ends.
   - "mechanic_skills": Off-GCD skills (Virtues, Mech commands, toolbelt, instant buffs) weaved dynamically.
   - Use "is_auto_attack": true for points where the bot yields to the game's natural auto-attack chain.
   - Use key "~" for weapon swaps between weapon sets.

2. "priority_loop" (or "priority_list"):
   - For builds that do NOT follow a rigid step sequence, but cast the highest-priority skill available off cooldown (e.g. Power Mechanist Rifle, Condition Scourge).
   - "opener": Optional burst sequence.
   - "priority_list": Skills ranked by "priority" (1-120, highest first). The engine visually checks slot readiness on screen and fires the highest-priority ready skill.
   - "mechanic_skills": Off-GCD skills.

3. "hybrid":
   - Combines a strict opener sequence with a dynamic priority list, or a rigid loop with off-cooldown priority weaves.

================================================================================
STANDARDIZED KEYBINDS & ACTION ATTRIBUTES:
================================================================================
- Skill Keys:
  * Weapon Skills: "1", "2", "3", "4", "5"
  * Weapon Swap: "~" (or "`") - Bound to weapon swap icon.
  * Healing: "q" (or "6")
  * Utilities: "e", "r", "t" (or "7", "8", "9")
  * Elite: "mouse3" (or "0")
  * Profession Mechanics (F-skills): "f1", "f2", "f3", "f4", "f5"
- Action Flags:
  * "double_tap": true -> Ground-targeted AOE reticles, symbols, wells, traps, or targeted leaps (e.g. Symbol of Punishment, Jump Shot, Throw Mine, Well of Calamity).
  * "is_auto_attack": true -> Passive auto-attack filler windows where the bot yields without spamming key 1.
  * "is_instant": true -> Off-GCD instant-cast skills (Virtues, Shouts, Stances, Signet passives).
  * "cancellable": false -> Uninterruptible channels that must never be clipped (e.g. Whirling Wrath, Zealot's Defense, Leap of Faith).
  * "cast_delay": duration in seconds (e.g. 0.4, 0.75, 1.5) that the engine locks/protects for channel animations.
  * "cooldown": base skill cooldown in seconds.
  * "min_resource": minimum charges / pips / energy required before firing (e.g. 5 for Virtuoso Bladesong, 3 for Chrono Mind Wrack, 50 for Reaper Shroud).
  * "max_resource": fire only when resource is at or below this value (e.g. 15 energy for Revenant Legend Swap).

================================================================================
OUTPUT JSON SCHEMA:
================================================================================
{
  "name": "Build Name",
  "profession": "Guardian",
  "elite_spec": "Core",
  "description": "Short summary of build and playstyle",
  "rotation_type": "strict_rotation",
  "mechanic": {
    "type": "discrete_pips",
    "resource_name": "clones",
    "max_resource": 3,
    "f_slots_count": 5
  },
  "opener": [
    {
      "name": "Shield of Wrath (Focus 5)",
      "key": "5",
      "cast_delay": 0.5,
      "cooldown": 35.0,
      "cancellable": true
    },
    {
      "name": "Weapon Swap to Greatsword",
      "key": "~",
      "cast_delay": 0.15,
      "cooldown": 9.8,
      "is_instant": true
    }
  ],
  "loop": [
    {
      "name": "Whirling Wrath (GS 2)",
      "key": "2",
      "cast_delay": 1.5,
      "cooldown": 8.0,
      "cancellable": false
    },
    {
      "name": "GS Auto-Attacks (Strike x2)",
      "key": "1",
      "cast_delay": 2.2,
      "is_auto_attack": true
    },
    {
      "name": "Weapon Swap to Sword/Focus",
      "key": "~",
      "cast_delay": 0.15,
      "cooldown": 9.8,
      "is_instant": true
    }
  ],
  "priority_list": [],
  "mechanic_skills": [
    {
      "name": "Mind Wrack (F1)",
      "key": "f1",
      "priority": 100,
      "cooldown": 8.0,
      "min_resource": 3,
      "is_instant": true
    }
  ]
}

CRITICAL RULES:
1. Return ONLY the valid JSON object enclosed in ```json ... ```.
2. Populate the appropriate tracks based on whether the rotation is strict_rotation (opener + loop), priority_loop (opener + priority_list), or hybrid.
3. Every weapon swap MUST use key "~" with is_instant: true.
4. Set double_tap: true on all ground-targeted reticles.
5. In "mechanic", declare:
   - "type": "discrete_pips" (for Mesmer/Virtuoso/Thief/Warrior), "continuous_gauge" (for Necro/Revenant/Holosmith), or "none" (for Guardian/Scrapper/Ranger).
   - "resource_name": e.g. "clones", "blades", "life_force", "energy", "initiative", "malice", "heat", "adrenaline".
   - "max_resource": e.g. 3, 5, 15, 100, 150.
   - "f_slots_count": number of F-skills (1 to 5).

================================================================================
PASTE YOUR ROTATION GUIDE OR TEXT BELOW:
================================================================================
"""


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
    min_resource = data.get("min_resource")
    max_resource = data.get("max_resource")
    resource_type = data.get("resource_type")

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
        double_tap=double_tap,
        min_resource=float(min_resource) if min_resource is not None else None,
        max_resource=float(max_resource) if max_resource is not None else None,
        resource_type=resource_type
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
    if action.min_resource is not None:
        d["min_resource"] = action.min_resource
    if action.max_resource is not None:
        d["max_resource"] = action.max_resource
    if action.resource_type:
        d["resource_type"] = action.resource_type
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
    raw_type = str(build_data.get("rotation_type", "")).lower().strip()
    if raw_type in ["strict_rotation", "strict", "rigid", "rigid_loop", "sequential"]:
        rotation_type = "rigid_loop"
    elif raw_type in ["priority_loop", "priority_list", "priority"]:
        rotation_type = "priority_list"
    elif raw_type == "hybrid":
        rotation_type = "hybrid"
    else:
        rotation_type = ""
    
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
    if not rotation_type:
        if loop_actions and opener_actions:
            rotation_type = "rigid_loop"
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


def ingest_llm_payload(payload_text: str) -> Dict[str, Any]:
    """
    Parses and sanitizes LLM output (JSON or YAML) into a valid combat build definition.
    Tolerates conversational text, markdown code blocks, and key/type synonyms.

    Returns:
    {
        "name": str,
        "profession": str,
        "elite_spec": str,
        "description": str,
        "rotation_type": str,
        "build_data": dict,
        "summary": dict
    }
    """
    raw = (payload_text or "").strip()
    if not raw:
        raise ValueError("Payload text cannot be empty.")

    data = None

    # 1. Attempt extracting text inside markdown code fences (```json ... ``` or ```yaml ... ```)
    fence_match = re.search(r"```(?:json|yaml)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fence_match:
        fenced_content = fence_match.group(1).strip()
        try:
            data = json.loads(fenced_content)
        except Exception:
            try:
                data = yaml.safe_load(fenced_content)
            except Exception:
                pass

    # 2. Attempt direct JSON parsing of the entire string
    if data is None:
        try:
            data = json.loads(raw)
        except Exception:
            pass

    # 3. Attempt finding outermost JSON curly braces in conversational text
    if data is None:
        first_brace = raw.find("{")
        last_brace = raw.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = raw[first_brace:last_brace + 1]
            try:
                data = json.loads(candidate)
            except Exception:
                pass

    # 4. Fallback to YAML safe loading
    if data is None:
        try:
            data = yaml.safe_load(raw)
        except Exception as e:
            raise ValueError(f"Failed to parse text as JSON or YAML: {e}")

    # 5. Unwrap wrapper objects if present (e.g. {"build": {...}} or {"rotation": {...}})
    if isinstance(data, dict):
        if "build" in data and isinstance(data["build"], dict):
            data = data["build"]
        elif "rotation" in data and isinstance(data["rotation"], dict) and "opener" in data["rotation"]:
            data = data["rotation"]

    if not isinstance(data, dict):
        raise ValueError("Parsed payload must be a JSON dictionary / object representing a combat build.")

    name = str(data.get("name", "Imported Build")).strip() or "Imported Build"
    profession = str(data.get("profession", "")).strip()
    elite_spec = str(data.get("elite_spec", "")).strip()
    description = str(data.get("description", "Imported via LLM")).strip()

    # Normalize rotation type
    raw_rot = str(data.get("rotation_type", "")).strip().lower()
    if raw_rot in ["strict_rotation", "strict", "rigid", "rigid_loop", "sequential"]:
        rot_type = "rigid_loop"
    elif raw_rot in ["priority_loop", "priority_list", "priority"]:
        rot_type = "priority_list"
    elif raw_rot == "hybrid":
        rot_type = "hybrid"
    else:
        rot_type = ""

    def sanitize_actions(raw_list: Any) -> List[Dict[str, Any]]:
        clean_list = []
        if not isinstance(raw_list, list):
            return clean_list
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            s_name = str(item.get("name", "Unnamed Skill")).strip()
            s_key = str(item.get("key", "1")).strip().lower()

            # Normalize weapon swap keys (~ / ` / swap / weapon_swap)
            if s_key in ["~", "`", "swap", "weapon_swap"] or "weapon swap" in s_name.lower():
                s_key = "~"
                item["is_instant"] = True

            # Normalize mouse buttons
            if s_key in ["m3", "middle"]:
                s_key = "mouse3"
            elif s_key in ["m4"]:
                s_key = "mouse4"
            elif s_key in ["m5"]:
                s_key = "mouse5"

            act_dict: Dict[str, Any] = {
                "name": s_name,
                "key": s_key,
            }

            if "priority" in item:
                try:
                    act_dict["priority"] = int(item["priority"])
                except (ValueError, TypeError):
                    act_dict["priority"] = 50

            if "cooldown" in item:
                try:
                    act_dict["cooldown"] = round(float(item["cooldown"]), 2)
                except (ValueError, TypeError):
                    pass

            if "cast_delay" in item:
                try:
                    act_dict["cast_delay"] = round(float(item["cast_delay"]), 2)
                except (ValueError, TypeError):
                    pass

            if item.get("double_tap"):
                act_dict["double_tap"] = True
            if item.get("is_auto_attack"):
                act_dict["is_auto_attack"] = True
            if item.get("is_instant"):
                act_dict["is_instant"] = True
            if item.get("cancellable") is False:
                act_dict["cancellable"] = False

            if "min_resource" in item and item["min_resource"] is not None:
                try:
                    act_dict["min_resource"] = float(item["min_resource"])
                except (ValueError, TypeError):
                    pass

            if "max_resource" in item and item["max_resource"] is not None:
                try:
                    act_dict["max_resource"] = float(item["max_resource"])
                except (ValueError, TypeError):
                    pass

            clean_list.append(act_dict)
        return clean_list

    opener = sanitize_actions(data.get("opener", []))
    loop = sanitize_actions(data.get("loop", []))
    priority_list = sanitize_actions(data.get("priority_list", []))
    mechanic_skills = sanitize_actions(data.get("mechanic_skills", []))

    # Automatic inference if not provided
    if not rot_type:
        if loop and opener:
            rot_type = "rigid_loop"
        elif loop:
            rot_type = "rigid_loop"
        elif opener and priority_list:
            rot_type = "hybrid"
        else:
            rot_type = "priority_list"

    build_data: Dict[str, Any] = {
        "name": name,
        "description": description,
        "rotation_type": rot_type,
        "opener": opener,
        "loop": loop,
        "priority_list": priority_list,
        "mechanic_skills": mechanic_skills,
    }

    if "mechanic" in data and isinstance(data["mechanic"], dict):
        build_data["mechanic"] = data["mechanic"]

    all_actions = opener + loop + priority_list + mechanic_skills
    swap_count = sum(1 for a in all_actions if a.get("key") == "~")
    double_tap_count = sum(1 for a in all_actions if a.get("double_tap"))
    auto_count = sum(1 for a in all_actions if a.get("is_auto_attack"))

    summary = {
        "opener_count": len(opener),
        "loop_count": len(loop),
        "priority_count": len(priority_list),
        "mechanics_count": len(mechanic_skills),
        "total_actions": len(all_actions),
        "weapon_swaps": swap_count,
        "double_taps": double_tap_count,
        "auto_attacks": auto_count,
    }

    return {
        "name": name,
        "profession": profession,
        "elite_spec": elite_spec,
        "description": description,
        "rotation_type": rot_type,
        "build_data": build_data,
        "summary": summary,
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

    # Persist mechanic & resource metadata at spec level if defined
    if "mechanic" in build_dict and isinstance(build_dict["mechanic"], dict):
        m_info = build_dict["mechanic"]
        res_type = m_info.get("type", "none").lower()
        res_name = m_info.get("resource_name", "resource").lower()
        max_res = m_info.get("max_resource", 0)
        spec_entry["has_unique_mechanic_bar"] = (res_type != "none")
        if res_type == "discrete_pips":
            spec_entry["resource"] = {
                "type": "discrete_pips",
                "name": res_name,
                "max_pips": int(max_res)
            }
        elif res_type == "continuous_gauge":
            spec_entry["resource"] = {
                "type": "continuous_gauge",
                "name": res_name,
                "max_value": float(max_res)
            }
        if "f_slots_count" in m_info:
            spec_entry["f_slots_count"] = int(m_info["f_slots_count"])

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
