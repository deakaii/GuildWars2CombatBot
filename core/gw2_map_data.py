"""
Map-completion targets (waypoints, POIs, vistas, hearts) from the GW2 API.

Coordinates are continent coordinates, the same space MumbleLink's playerX/Y uses.
Map data is static, so each map is fetched once and cached under scratch/map_cache.
"""

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "scratch", "map_cache")
API = "https://api.guildwars2.com/v2"

# API point_of_interest types we care about ("unlock" = dungeon entrances etc.)
POI_KINDS = ("waypoint", "landmark", "vista")


@dataclass(frozen=True)
class Target:
    id: str                         # "poi:<id>" or "task:<id>", stable across sessions
    kind: str                       # waypoint | landmark | vista | heart
    name: str
    coord: Tuple[float, float]


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "GuildWars2CombatBot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _values(collection: Any) -> List[dict]:
    """The API returns some collections keyed by id and some as lists."""
    if isinstance(collection, dict):
        return list(collection.values())
    return list(collection or [])


def parse_targets(raw: Dict[str, Any]) -> List[Target]:
    """raw = {"map": /v2/maps/{id}, "region_map": /v2/continents/.../maps/{id}}."""
    region_map = raw.get("region_map", {})
    targets = []
    for poi in _values(region_map.get("points_of_interest")):
        if poi.get("type") in POI_KINDS and poi.get("coord"):
            name = poi.get("name") or poi["type"].title()
            targets.append(Target(f"poi:{poi['id']}", poi["type"], name, tuple(poi["coord"])))
    for task in _values(region_map.get("tasks")):
        if task.get("coord"):
            targets.append(Target(f"task:{task['id']}", "heart", task.get("objective", "Heart"), tuple(task["coord"])))
    return targets


def fetch_raw(map_id: int) -> Dict[str, Any]:
    info = _get_json(f"{API}/maps/{map_id}")
    url = (f"{API}/continents/{info['continent_id']}/floors/{info['default_floor']}"
           f"/regions/{info['region_id']}/maps/{map_id}")
    return {"map": info, "region_map": _get_json(url)}


def load_raw(map_id: int, cache_dir: str = CACHE_DIR, refresh: bool = False) -> Dict[str, Any]:
    path = os.path.join(cache_dir, f"{map_id}.json")
    if not refresh and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raw = fetch_raw(map_id)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f)
    return raw


def get_map_targets(map_id: int, cache_dir: str = CACHE_DIR) -> List[Target]:
    """All completion targets for a map. Raises on network errors when not cached."""
    return parse_targets(load_raw(map_id, cache_dir))


def map_name(map_id: int, cache_dir: str = CACHE_DIR) -> Optional[str]:
    path = os.path.join(cache_dir, f"{map_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("map", {}).get("name")
