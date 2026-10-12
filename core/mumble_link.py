"""
MumbleLink reader: the shared-memory block GW2 publishes for overlays
(TacO, Blish HUD, ArcDPS). Read-only, no injection.

Gives the player's continent position, facing, map id and combat/mount state,
which the navigator uses as closed-loop feedback.
Layout: https://wiki.guildwars2.com/wiki/API:MumbleLink
"""

import ctypes
import json
import math
import mmap
import time
from dataclasses import dataclass
from typing import Optional, Tuple


class LinkedMem(ctypes.Structure):
    _fields_ = [
        ("uiVersion", ctypes.c_uint32),
        ("uiTick", ctypes.c_uint32),
        ("fAvatarPosition", ctypes.c_float * 3),
        ("fAvatarFront", ctypes.c_float * 3),
        ("fAvatarTop", ctypes.c_float * 3),
        ("name", ctypes.c_wchar * 256),
        ("fCameraPosition", ctypes.c_float * 3),
        ("fCameraFront", ctypes.c_float * 3),
        ("fCameraTop", ctypes.c_float * 3),
        ("identity", ctypes.c_wchar * 256),
        ("context_len", ctypes.c_uint32),
        ("context", ctypes.c_ubyte * 256),
        ("description", ctypes.c_wchar * 2048),
    ]


class GW2Context(ctypes.Structure):
    _fields_ = [
        ("serverAddress", ctypes.c_ubyte * 28),
        ("mapId", ctypes.c_uint32),
        ("mapType", ctypes.c_uint32),
        ("shardId", ctypes.c_uint32),
        ("instance", ctypes.c_uint32),
        ("buildId", ctypes.c_uint32),
        ("uiState", ctypes.c_uint32),
        ("compassWidth", ctypes.c_uint16),
        ("compassHeight", ctypes.c_uint16),
        ("compassRotation", ctypes.c_float),
        ("playerX", ctypes.c_float),
        ("playerY", ctypes.c_float),
        ("mapCenterX", ctypes.c_float),
        ("mapCenterY", ctypes.c_float),
        ("mapScale", ctypes.c_float),
        ("processId", ctypes.c_uint32),
        ("mountIndex", ctypes.c_uint8),
    ]


LINK_SIZE = ctypes.sizeof(LinkedMem)  # 5460

UI_MAP_OPEN = 0x01
UI_GAME_FOCUS = 0x08
UI_TEXTBOX_FOCUS = 0x20
UI_IN_COMBAT = 0x40


@dataclass
class NavState:
    tick: int
    map_id: int
    pos: Tuple[float, float]        # continent coordinates (same units as API POI coords)
    heading_rad: float              # facing in continent space: atan2(dy, dx), y grows south
    in_combat: bool
    mounted: bool
    map_open: bool
    textbox_focused: bool
    game_focused: bool
    character: str = ""


def heading_from_front(front_x: float, front_z: float) -> float:
    """Avatar front is in map space (x east, z north); continent y grows south, so flip z."""
    return math.atan2(-front_z, front_x)


def parse(buf: bytes) -> Optional[NavState]:
    """Decodes a raw LinkedMem block. Returns None if GW2 hasn't written to it."""
    if len(buf) < LINK_SIZE:
        return None
    mem = LinkedMem.from_buffer_copy(buf[:LINK_SIZE])
    if mem.name != "Guild Wars 2" or mem.uiTick == 0:
        return None
    ctx = GW2Context.from_buffer_copy(bytes(mem.context)[:ctypes.sizeof(GW2Context)])

    character = ""
    try:
        character = json.loads(mem.identity).get("name", "")
    except (ValueError, AttributeError):
        pass

    ui = ctx.uiState
    return NavState(
        tick=mem.uiTick,
        map_id=ctx.mapId,
        pos=(ctx.playerX, ctx.playerY),
        heading_rad=heading_from_front(mem.fAvatarFront[0], mem.fAvatarFront[2]),
        in_combat=bool(ui & UI_IN_COMBAT),
        mounted=ctx.mountIndex != 0,
        map_open=bool(ui & UI_MAP_OPEN),
        textbox_focused=bool(ui & UI_TEXTBOX_FOCUS),
        game_focused=bool(ui & UI_GAME_FOCUS),
        character=character,
    )


class MumbleLinkReader:
    """Opens the MumbleLink mapping and returns fresh NavStates.

    read() returns None when the game isn't running or uiTick stopped advancing
    for stale_after_s (loading screen, character select, crash).
    """

    def __init__(self, stale_after_s: float = 1.5, clock=time.monotonic):
        self._mm = mmap.mmap(-1, LINK_SIZE, "MumbleLink")
        self.stale_after_s = stale_after_s
        self._clock = clock
        self._last_tick = None
        self._last_change = 0.0

    def read(self) -> Optional[NavState]:
        self._mm.seek(0)
        state = parse(self._mm.read(LINK_SIZE))
        if state is None:
            return None
        now = self._clock()
        if state.tick != self._last_tick:
            self._last_tick = state.tick
            self._last_change = now
        elif now - self._last_change > self.stale_after_s:
            return None
        return state

    def close(self) -> None:
        self._mm.close()
