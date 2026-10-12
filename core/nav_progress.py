"""
Local map-completion progress. The GW2 API doesn't expose which POIs a
character has discovered, so the navigator records what it reached (done)
and what it gave up on (skipped), per character and map.

File layout: {character: {map_id: {"done": [target ids], "skipped": [target ids]}}}
"""

import json
import os
import threading
from typing import Dict, List, Set

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(BASE_DIR, "config", "nav_progress.json")


class NavProgress:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f) or {}

    def _entry(self, character: str, map_id: int) -> Dict[str, List[str]]:
        maps = self._data.setdefault(character or "unknown", {})
        return maps.setdefault(str(map_id), {"done": [], "skipped": []})

    def done(self, character: str, map_id: int) -> Set[str]:
        with self._lock:
            return set(self._entry(character, map_id)["done"])

    def excluded(self, character: str, map_id: int) -> Set[str]:
        """Targets the navigator should not visit: done or skipped."""
        with self._lock:
            e = self._entry(character, map_id)
            return set(e["done"]) | set(e["skipped"])

    def mark(self, character: str, map_id: int, target_id: str, status: str) -> None:
        """status: "done" or "skipped"."""
        with self._lock:
            e = self._entry(character, map_id)
            if target_id not in e[status]:
                e[status].append(target_id)
            if status == "done" and target_id in e["skipped"]:
                e["skipped"].remove(target_id)
            self._save()

    def clear_skipped(self, character: str, map_id: int) -> int:
        with self._lock:
            e = self._entry(character, map_id)
            n = len(e["skipped"])
            e["skipped"] = []
            self._save()
            return n

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=1)
        os.replace(tmp, self.path)
