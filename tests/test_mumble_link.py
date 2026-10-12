"""MumbleLink parsing: map id, continent position, facing and UI/combat/mount flags."""

import ctypes
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mumble_link import (LINK_SIZE, GW2Context, LinkedMem, UI_GAME_FOCUS, UI_IN_COMBAT,
                              UI_MAP_OPEN, parse)


def make_link(front=(1.0, 0.0, 0.0), ui_state=UI_GAME_FOCUS, mount=0, map_id=15,
              player=(43210.5, 29000.25), name="Guild Wars 2", tick=42) -> bytes:
    mem = LinkedMem()
    mem.uiVersion = 2
    mem.uiTick = tick
    mem.name = name
    mem.identity = json.dumps({"name": "Test Thief", "map_id": map_id})
    for i, v in enumerate(front):
        mem.fAvatarFront[i] = v
    ctx = GW2Context()
    ctx.mapId = map_id
    ctx.uiState = ui_state
    ctx.playerX, ctx.playerY = player
    ctx.mountIndex = mount
    raw_ctx = bytes(ctx)
    ctypes.memmove(ctypes.addressof(mem.context), raw_ctx, len(raw_ctx))
    mem.context_len = len(raw_ctx)
    return bytes(mem)


class TestMumbleLink(unittest.TestCase):
    def test_layout_size(self):
        self.assertEqual(LINK_SIZE, 5460)
        self.assertEqual(GW2Context.mountIndex.offset, 84)

    def test_parse_fields(self):
        s = parse(make_link(ui_state=UI_GAME_FOCUS | UI_IN_COMBAT, mount=5))
        self.assertEqual(s.map_id, 15)
        self.assertEqual(s.tick, 42)
        self.assertAlmostEqual(s.pos[0], 43210.5, places=2)
        self.assertAlmostEqual(s.pos[1], 29000.25, places=2)
        self.assertTrue(s.in_combat)
        self.assertTrue(s.mounted)
        self.assertTrue(s.game_focused)
        self.assertFalse(s.map_open)
        self.assertEqual(s.character, "Test Thief")

    def test_flags_off(self):
        s = parse(make_link(ui_state=UI_MAP_OPEN))
        self.assertTrue(s.map_open)
        self.assertFalse(s.game_focused)
        self.assertFalse(s.in_combat)
        self.assertFalse(s.mounted)

    def test_heading_convention(self):
        # East in the game = +x on the continent map
        self.assertAlmostEqual(parse(make_link(front=(1, 0, 0))).heading_rad, 0.0)
        # North in the game (+z) = up on the continent map, where y grows south
        self.assertAlmostEqual(parse(make_link(front=(0, 0, 1))).heading_rad, -math.pi / 2)
        self.assertAlmostEqual(parse(make_link(front=(0, 0, -1))).heading_rad, math.pi / 2)

    def test_not_running(self):
        self.assertIsNone(parse(bytes(LINK_SIZE)))
        self.assertIsNone(parse(make_link(name="Some Other Game")))
        self.assertIsNone(parse(make_link(tick=0)))


if __name__ == "__main__":
    unittest.main()
