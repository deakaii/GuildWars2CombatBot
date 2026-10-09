"""
Specialization Configuration Manager.
Manages modular, per-class and per-spec YAML configuration files in config/specs/.
Allows each class/spec to independently define:
- Mechanic slot locations (F1 - F5) and keybind badges.
- Class-specific resources (Discrete Pips like Blades/Clones/Initiative, Continuous Gauges like Life Force/Energy/Heat).
- Visual threshold overrides and presets.
"""

import os
import yaml
from typing import Dict, Any, Optional, List, Tuple


SPECS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "specs")


def sanitize_filename(profession: str, spec: str) -> str:
    """Returns normalized filename, e.g. 'mesmer_virtuoso.yaml'."""
    p = profession.lower().strip().replace(" ", "_")
    s = spec.lower().strip().replace(" ", "_")
    return f"{p}_{s}.yaml"


def get_spec_file_path(profession: str, spec: str) -> str:
    """Returns the absolute path to the spec's YAML file."""
    return os.path.join(SPECS_DIR, sanitize_filename(profession, spec))


def load_spec_config(profession: str, spec: str) -> Dict[str, Any]:
    """
    Loads the specification configuration.
    Priority order:
    1. config/specs/{profession}_{spec}.yaml
    2. config/professions_database.yaml (fallback)
    3. Default archetype generation
    """
    p_clean = profession.lower().strip()
    s_clean = spec.lower().strip()
    target_path = get_spec_file_path(p_clean, s_clean)

    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if data:
                    return data
        except Exception as e:
            print(f"[SpecManager] Warning: Failed to load {target_path}: {e}")

    # Fallback to professions_database.yaml
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "professions_database.yaml")
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = yaml.safe_load(f) or {}
            profs = db.get("professions", {})
            for p_name, p_data in profs.items():
                if p_name.lower() == p_clean or p_clean in p_name.lower():
                    specs = p_data.get("elite_specs", {})
                    for s_name, s_data in specs.items():
                        if s_name.lower() == s_clean or s_clean in s_name.lower():
                            converted = {
                                "profession": p_name,
                                "elite_spec": s_name,
                                "display_name": f"{p_name} - {s_name}",
                                "mechanic_bar": {
                                    "f_slots_count": s_data.get("f_slots_count", 3),
                                    "slots": s_data.get("mechanic_slots", {}),
                                    "labels": {}
                                },
                                "resource": s_data.get("resource", {"type": "none"})
                            }
                            return converted
        except Exception:
            pass

    # Generic fallback
    return {
        "profession": profession.title(),
        "elite_spec": spec.title(),
        "display_name": f"{profession.title()} - {spec.title()}",
        "mechanic_bar": {
            "f_slots_count": 0,
            "slots": {},
            "labels": {}
        },
        "resource": {"type": "none"}
    }


def save_spec_config(profession: str, spec: str, data: Dict[str, Any]) -> str:
    """Saves specification configuration to config/specs/{profession}_{spec}.yaml."""
    os.makedirs(SPECS_DIR, exist_ok=True)
    target_path = get_spec_file_path(profession, spec)
    with open(target_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return target_path


def list_available_specs() -> List[Dict[str, str]]:
    """Returns a list of all available spec configurations found in config/specs/."""
    results = []
    if not os.path.exists(SPECS_DIR):
        return results

    for fn in os.listdir(SPECS_DIR):
        if fn.endswith(".yaml") or fn.endswith(".yml"):
            fp = os.path.join(SPECS_DIR, fn)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                results.append({
                    "filename": fn,
                    "path": fp,
                    "profession": d.get("profession", ""),
                    "elite_spec": d.get("elite_spec", ""),
                    "display_name": d.get("display_name", fn)
                })
            except Exception:
                continue
    return results
