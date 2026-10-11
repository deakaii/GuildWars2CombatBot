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


def get_resolution_tag() -> str:
    """Returns current screen resolution as a compact string, e.g. '3440x1440'."""
    try:
        from core.dpi_utils import get_screen_resolution
        w, h = get_screen_resolution()
        return f"{w}x{h}"
    except Exception:
        return ""


def _normalize_key(profession: str, spec: str) -> tuple:
    p = profession.lower().strip().replace(" ", "_")
    s = spec.lower().strip().replace(" ", "_")
    return p, s


def sanitize_filename(profession: str, spec: str, resolution_tag: Optional[str] = None) -> str:
    """Returns normalized filename, e.g. 'engineer_mechanist_3440x1440.yaml' or 'engineer_mechanist.yaml'."""
    p, s = _normalize_key(profession, spec)
    if resolution_tag:
        return f"{p}_{s}_{resolution_tag}.yaml"
    return f"{p}_{s}.yaml"


def get_spec_file_path(profession: str, spec: str, resolution_tag: Optional[str] = None) -> str:
    """Returns the absolute path to the spec's YAML file (resolution-specific or generic)."""
    return os.path.join(SPECS_DIR, sanitize_filename(profession, spec, resolution_tag))


def load_spec_config(
    profession: str,
    spec: str,
    resolution_tag: Optional[str] = None,
    auto_detect_resolution: bool = True
) -> Dict[str, Any]:
    """
    Loads the specification configuration.
    Priority order:
    1. config/specs/{profession}_{spec}_{WxH}.yaml (resolution-specific profile)
    2. config/specs/{profession}_{spec}.yaml (base fallback profile)
    3. config/professions_database.yaml (database fallback)
    4. Default archetype generation
    """
    p_clean, s_clean = _normalize_key(profession, spec)

    # 1. Try resolution-specific file
    res = resolution_tag or (get_resolution_tag() if auto_detect_resolution else None)
    if res:
        res_path = get_spec_file_path(p_clean, s_clean, res)
        if os.path.exists(res_path):
            try:
                with open(res_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    if data:
                        return data
            except Exception as e:
                print(f"[SpecManager] Warning: Failed to load {res_path}: {e}")

    # 2. Try generic spec file
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


def save_spec_config(
    profession: str,
    spec: str,
    data: Dict[str, Any],
    resolution_tag: Optional[str] = None
) -> str:
    """Saves specification configuration to config/specs/{profession}_{spec}_{WxH}.yaml or base file."""
    os.makedirs(SPECS_DIR, exist_ok=True)
    target_path = get_spec_file_path(profession, spec, resolution_tag)
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
