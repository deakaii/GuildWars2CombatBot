"""Map targets from a saved GW2 API response (Queensdale, map 15). No network."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gw2_map_data import get_map_targets, map_name, parse_targets

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "maps", "queensdale_15.json")


class TestMapData(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, "r", encoding="utf-8") as f:
            self.raw = json.load(f)

    def test_parse_counts(self):
        targets = parse_targets(self.raw)
        kinds = Counter(t.kind for t in targets)
        self.assertEqual(kinds, {"landmark": 21, "waypoint": 16, "vista": 9, "heart": 17})

    def test_target_shape(self):
        targets = {t.id: t for t in parse_targets(self.raw)}
        orchard = targets["poi:127"]
        self.assertEqual(orchard.kind, "landmark")
        self.assertEqual(orchard.name, "Eda's Orchard")
        self.assertEqual(orchard.coord, (42830.7, 28406.7))
        self.assertEqual(targets["task:211"].kind, "heart")

    def test_cached_map_needs_no_network(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copy(FIXTURE, os.path.join(tmp, "15.json"))
            self.assertEqual(len(get_map_targets(15, cache_dir=tmp)), 63)
            self.assertEqual(map_name(15, cache_dir=tmp), "Queensdale")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
