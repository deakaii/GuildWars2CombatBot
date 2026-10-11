"""
F-Skill Icon Fetcher.
Pulls every profession mechanic skill (F1 - F5) from the official GW2 API, sorts
them by elite specialization, and downloads their icons for each spec file in
config/specs/. Corrections the API can't make on its own live in
config/spec_f_skills.yaml.

Output:
    config/templates/f_skills/<profession>_<spec>/mech_f1__rolling_smash__63334.png
    config/templates/f_skills/manifest.yaml   (spec -> slot -> skills with icon paths)

Icons are saved as the API serves them (128x128). The game draws only the centre
of each icon, so before template matching trim 16px from every edge (keep
[16:112, 16:112]) and match against the top half only, since keybind labels
cover the bottom. Matched that way, the correct icon scores 0.94-0.99 and the
best wrong one about 0.70.

The full API skill list is cached in scratch/gw2_api_cache.json; pass --refresh
after a game patch to re-download it. Icons already on disk are not re-downloaded.
"""

import os
import re
import sys
import json
import glob
import argparse
import urllib.request
from collections import defaultdict
from typing import Dict, List, Any

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_DIR = os.path.join(BASE_DIR, "config", "specs")
SEED_PATH = os.path.join(BASE_DIR, "config", "spec_f_skills.yaml")
OUT_DIR = os.path.join(BASE_DIR, "config", "templates", "f_skills")
CACHE_PATH = os.path.join(BASE_DIR, "scratch", "gw2_api_cache.json")

API = "https://api.guildwars2.com/v2"
SLOT_RE = re.compile(r"^Profession_(\d)$")
RESOLUTION_RE = re.compile(r"_\d+x\d+$")


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "GuildWars2CombatBot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_api_data(refresh: bool) -> Dict[str, Any]:
    """Returns {'skills': [...], 'specializations': [...]}, cached on disk."""
    if not refresh and os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    print("  - Downloading skill list from the GW2 API...")
    ids = _get_json(f"{API}/skills")
    skills = []
    for i in range(0, len(ids), 200):
        chunk = ",".join(str(x) for x in ids[i:i + 200])
        skills.extend(_get_json(f"{API}/skills?ids={chunk}"))
        print(f"    {len(skills)}/{len(ids)}", end="\r")
    print()
    data = {
        "skills": skills,
        "specializations": _get_json(f"{API}/specializations?ids=all"),
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def build_candidates(data: Dict[str, Any]) -> Dict[tuple, Dict[str, List[dict]]]:
    """Groups API profession skills as {(profession, spec): {mech_fN: [skill, ...]}}.
    Spec is 'core' for skills with no specialization."""
    spec_names = {s["id"]: s["name"].lower() for s in data["specializations"]}
    groups: Dict[tuple, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for skill in data["skills"]:
        m = SLOT_RE.match(skill.get("slot", ""))
        # Skills with no profession are environmental/bundle skills (Eat Egg, etc.)
        if not m or not skill.get("professions") or not skill.get("icon"):
            continue
        spec = spec_names.get(skill.get("specialization"), "core")
        for prof in skill["professions"]:
            groups[(prof.lower(), spec)][f"mech_f{m.group(1)}"].append(skill)
    return groups


def resolve_refs(refs: List[Any], by_id: Dict[int, dict], by_name: Dict[str, List[dict]]) -> List[dict]:
    """Turns a list of skill names / ids from the seed file into API skill entries."""
    found = []
    for ref in refs:
        if isinstance(ref, int):
            matches = [by_id[ref]] if ref in by_id else []
        else:
            matches = by_name.get(str(ref).lower(), [])
        matches = [s for s in matches if s.get("icon")]
        if not matches:
            print(f"    [WARN] No skill with an icon matches '{ref}'")
        found.extend(matches)
    return found


def list_spec_keys() -> List[tuple]:
    """(profession, spec) for every base spec file (resolution-specific copies skipped)."""
    keys = []
    for path in sorted(glob.glob(os.path.join(SPECS_DIR, "*.yaml"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        if RESOLUTION_RE.search(stem):
            continue
        prof, _, spec = stem.partition("_")
        keys.append((prof, spec))
    return keys


def download_icon(url: str, path: str) -> None:
    if os.path.exists(path):
        return
    req = urllib.request.Request(url, headers={"User-Agent": "GuildWars2CombatBot"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as f:
        f.write(resp.read())


def main():
    parser = argparse.ArgumentParser(description="Download F-skill icons for every spec from the GW2 API")
    parser.add_argument("--refresh", action="store_true", help="Re-download the API skill list")
    parser.add_argument("--only", type=str, default=None,
                        help="Process one spec, e.g. 'engineer_mechanist'")
    args = parser.parse_args()

    data = load_api_data(args.refresh)
    by_id = {s["id"]: s for s in data["skills"]}
    by_name: Dict[str, List[dict]] = defaultdict(list)
    for s in data["skills"]:
        by_name[s["name"].lower()].append(s)

    seed = {}
    if os.path.exists(SEED_PATH):
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            seed = yaml.safe_load(f) or {}

    candidates = build_candidates(data)
    manifest: Dict[str, Any] = {}

    for prof, spec in list_spec_keys():
        key = f"{prof}_{spec}"
        if args.only and key != args.only:
            continue
        fix = seed.get(key, {}) or {}
        excluded = {str(x).lower() for x in fix.get("exclude", [])}

        slots: Dict[str, List[dict]] = defaultdict(list)
        for slot, skills in candidates.get((prof, spec), {}).items():
            slots[slot].extend(skills)
        for slot, refs in (fix.get("add") or {}).items():
            slots[slot].extend(resolve_refs(refs, by_id, by_name))
        # Fall back to core for any slot the elite spec doesn't fill
        for slot, skills in candidates.get((prof, "core"), {}).items():
            if not slots.get(slot):
                slots[slot].extend(skills)

        spec_dir = os.path.join(OUT_DIR, key)
        os.makedirs(spec_dir, exist_ok=True)
        entry: Dict[str, List[dict]] = {}
        for slot in sorted(slots):
            seen_icons = set()
            rows = []
            for s in slots[slot]:
                if str(s["id"]) in excluded or s["name"].lower() in excluded:
                    continue
                # Many skills are per-attunement/per-weapon copies sharing one icon
                if s["icon"] in seen_icons:
                    continue
                seen_icons.add(s["icon"])
                fname = f"{slot}__{slugify(s['name'])}__{s['id']}.png"
                download_icon(s["icon"], os.path.join(spec_dir, fname))
                rows.append({"id": s["id"], "name": s["name"],
                             "icon": f"config/templates/f_skills/{key}/{fname}"})
            if rows:
                entry[slot] = rows
        manifest[key] = entry
        counts = ", ".join(f"{k[-2:].upper()}:{len(v)}" for k, v in entry.items()) or "nothing found"
        print(f"  {key:<28} {counts}")

    manifest_path = os.path.join(OUT_DIR, "manifest.yaml")
    if args.only and os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = {**(yaml.safe_load(f) or {}), **manifest}
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("# Generated by tools/fetch_spec_icons.py - edit config/spec_f_skills.yaml instead.\n")
        yaml.safe_dump(manifest, f, sort_keys=True, allow_unicode=True)
    print(f"\n  Manifest written to {os.path.relpath(manifest_path, BASE_DIR)}")


if __name__ == "__main__":
    main()
