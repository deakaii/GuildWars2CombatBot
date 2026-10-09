"""
DPI awareness and resolution scaling utilities for Windows.
Ensures pixel-perfect coordinates across 1080p, 1440p, 4K and varying Windows UI scaling (100%, 125%, 150%, etc.).
"""

import sys
import ctypes
from typing import Tuple, Dict, Any


def attach_to_user_desktop() -> bool:
    """
    Ensures the current thread is attached to the interactive user 'Default' desktop.
    Prevents WinError 5 Access is Denied when executing under background service/terminal contexts.
    """
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        # DESKTOP_ALL_ACCESS = 0x01FF
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            return bool(user32.SetThreadDesktop(hdesk))
    except Exception:
        pass
    return False


def enable_dpi_awareness() -> bool:
    """
    Enables Windows Per-Monitor DPI Awareness so Windows does not virtualize or blur screen coordinates.
    Also ensures attachment to the interactive user desktop.
    Returns True if successfully set.
    """
    attach_to_user_desktop()

    if sys.platform != "win32":
        return False

    # Try Windows 8.1+ Per-Monitor DPI awareness (PROCESS_PER_MONITOR_DPI_AWARE = 2)
    try:
        shcore = ctypes.windll.shcore
        res = shcore.SetProcessDpiAwareness(2)
        if res == 0:  # S_OK
            return True
    except Exception:
        pass

    # Fallback to Vista+ Process DPI awareness
    try:
        user32 = ctypes.windll.user32
        return bool(user32.SetProcessDPIAware())
    except Exception:
        return False


def get_screen_resolution() -> Tuple[int, int]:
    """
    Returns the primary screen physical resolution (width, height) in pixels.
    """
    enable_dpi_awareness()
    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return w, h


def normalized_to_absolute(
    norm_x: float,
    norm_y: float,
    norm_w: float,
    norm_h: float,
    screen_w: int,
    screen_h: int
) -> Tuple[int, int, int, int]:
    """
    Converts normalized ratios (0.0 - 1.0) into physical screen pixel bounds (x, y, w, h).
    """
    abs_x = max(0, int(norm_x * screen_w))
    abs_y = max(0, int(norm_y * screen_h))
    abs_w = max(1, int(norm_w * screen_w))
    abs_h = max(1, int(norm_h * screen_h))

    # Clamp to screen boundary
    if abs_x + abs_w > screen_w:
        abs_w = screen_w - abs_x
    if abs_y + abs_h > screen_h:
        abs_h = screen_h - abs_y

    return abs_x, abs_y, abs_w, abs_h


def absolute_to_normalized(
    abs_x: int,
    abs_y: int,
    abs_w: int,
    abs_h: int,
    screen_w: int,
    screen_h: int
) -> Tuple[float, float, float, float]:
    """
    Converts physical pixel bounds (x, y, w, h) into normalized ratios (0.0 - 1.0)
    for seamless portability to other displays.
    """
    norm_x = round(abs_x / screen_w, 4)
    norm_y = round(abs_y / screen_h, 4)
    norm_w = round(abs_w / screen_w, 4)
    norm_h = round(abs_h / screen_h, 4)
    return norm_x, norm_y, norm_w, norm_h
