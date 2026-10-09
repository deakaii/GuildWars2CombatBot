"""
Utility to populate modular specification YAML files in config/specs/
for every profession and elite specialization in Guild Wars 2.
"""

import os
import yaml

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
specs_dir = os.path.join(base_dir, "config", "specs")
os.makedirs(specs_dir, exist_ok=True)

db_path = os.path.join(base_dir, "config", "professions_database.yaml")
with open(db_path, "r", encoding="utf-8") as f:
    db = yaml.safe_load(f) or {}

profs = db.get("professions", {})

for prof_name, prof_data in profs.items():
    specs = prof_data.get("elite_specs", {})
    for spec_name, spec_data in specs.items():
        fname = f"{prof_name.lower().replace(' ', '_')}_{spec_name.lower().replace(' ', '_')}.yaml"
        fpath = os.path.join(specs_dir, fname)
        if os.path.exists(fpath):
            print(f"Skipping already calibrated spec: {fname}")
            continue

        # Extract mechanic slots or assign archetype defaults
        m_slots = spec_data.get("mechanic_slots", {})
        f_count = spec_data.get("f_slots_count", len(m_slots) if m_slots else 3)
        res = spec_data.get("resource", {})

        if not m_slots:
            if f_count == 5:
                m_slots = {
                    "mech_f1": [0.1500, 0.1562, 0.0580, 0.3438],
                    "mech_f2": [0.2120, 0.1562, 0.0580, 0.3438],
                    "mech_f3": [0.2740, 0.1562, 0.0580, 0.3438],
                    "mech_f4": [0.3360, 0.1562, 0.0580, 0.3438],
                    "mech_f5": [0.3980, 0.1562, 0.0580, 0.3438],
                }
            elif f_count == 4:
                m_slots = {
                    "mech_f1": [0.1800, 0.1562, 0.0580, 0.3438],
                    "mech_f2": [0.2420, 0.1562, 0.0580, 0.3438],
                    "mech_f3": [0.3040, 0.1562, 0.0580, 0.3438],
                    "mech_f4": [0.3660, 0.1562, 0.0580, 0.3438],
                }
            elif f_count == 3:
                m_slots = {
                    "mech_f1": [0.2040, 0.1562, 0.0550, 0.3438],
                    "mech_f2": [0.2610, 0.1562, 0.0550, 0.3438],
                    "mech_f3": [0.3180, 0.1562, 0.0550, 0.3438],
                }
            elif f_count == 2:
                m_slots = {
                    "mech_f1": [0.2300, 0.1562, 0.0550, 0.3438],
                    "mech_f2": [0.2900, 0.1562, 0.0550, 0.3438],
                }
            elif f_count == 1:
                m_slots = {
                    "mech_f1": [0.2600, 0.1562, 0.0550, 0.3438],
                }
            else:
                m_slots = {}

        if not res:
            res = {"type": "none", "name": "none"}

        labels = {k: f"F{k.replace('mech_f', '')}" for k in m_slots.keys()}

        spec_yaml = {
            "profession": prof_name,
            "elite_spec": spec_name,
            "display_name": f"{prof_name} - {spec_name}",
            "description": spec_data.get("mechanic_name", f"{spec_name} Specialization Layout"),
            "mechanic_bar": {
                "f_slots_count": f_count,
                "slots": m_slots,
                "labels": labels
            },
            "resource": res
        }

        with open(fpath, "w", encoding="utf-8") as out:
            yaml.dump(spec_yaml, out, default_flow_style=False, sort_keys=False)
        print(f"Generated {fname}")

print("All spec configuration files generated in config/specs/ successfully!")
