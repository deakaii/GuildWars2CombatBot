"""
Window & Process Utilities for Guild Wars 2 Targeting.
Ensures the automation bot and HUD exclusively interact with and observe Guild Wars 2.
Prevents synthetic inputs and vision scraping when tabbed out to browsers, chat, or other apps.
"""

import ctypes
from ctypes import wintypes
from typing import Tuple, Dict, Any, Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Process Snapshot Constant
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_void_p),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_wchar * 260)
    ]


# Common identifiers for Guild Wars 2
GW2_EXECUTABLES = ("gw2-64.exe", "gw2.exe")
GW2_TITLES = ("guild wars 2", "gw2")
GW2_WINDOW_CLASSES = ("arenanet_dx_window_class", "arenanet_window_class")


def is_gw2_process_running(allowed_exes: Tuple[str, ...] = GW2_EXECUTABLES) -> bool:
    """
    Direct Win32 kernel query checking if a Guild Wars 2 process is currently running.
    Zero subprocess overhead, instantaneous execution (<1ms).
    """
    h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h_snap == -1:
        return False

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found = False
    try:
        success = kernel32.Process32FirstW(h_snap, ctypes.byref(entry))
        while success:
            if entry.szExeFile.lower() in allowed_exes:
                found = True
                break
            success = kernel32.Process32NextW(h_snap, ctypes.byref(entry))
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(h_snap)

    return found


def get_foreground_window_info() -> Dict[str, Any]:
    """
    Returns information about the current active foreground window.
    """
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "", "class": "", "exe": "", "is_gw2": False}

        # Window Title
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        # Window Class
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        cls_name = cls_buf.value

        # Executable Name
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if h_proc:
            try:
                exe_buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(h_proc, 0, exe_buf, ctypes.byref(size)):
                    exe = exe_buf.value.split("\\")[-1]
            finally:
                kernel32.CloseHandle(h_proc)

        title_lower = title.lower()
        cls_lower = cls_name.lower()
        exe_lower = exe.lower()

        is_gw2 = (
            any(t in title_lower for t in GW2_TITLES) or
            any(c in cls_lower for c in GW2_WINDOW_CLASSES) or
            (exe_lower in GW2_EXECUTABLES)
        )

        return {
            "hwnd": hwnd,
            "title": title,
            "class": cls_name,
            "exe": exe,
            "is_gw2": is_gw2
        }
    except Exception:
        return {"hwnd": 0, "title": "", "class": "", "exe": "", "is_gw2": False}


def is_gw2_focused(
    allowed_titles: Tuple[str, ...] = GW2_TITLES,
    allowed_exes: Tuple[str, ...] = GW2_EXECUTABLES
) -> bool:
    """
    Returns True ONLY if Guild Wars 2 is the active foreground window.
    Returns False if tabbed out to browsers, Discord, chat, IDE, desktop, etc.
    """
    info = get_foreground_window_info()
    if info["is_gw2"]:
        return True

    # Extra check against custom allowed_titles/exes if provided
    title_lower = info.get("title", "").lower()
    exe_lower = info.get("exe", "").lower()
    for t in allowed_titles:
        if t in title_lower:
            return True
    for e in allowed_exes:
        if e == exe_lower:
            return True

    return False


def find_gw2_window(
    allowed_titles: Tuple[str, ...] = GW2_TITLES,
    allowed_exes: Tuple[str, ...] = GW2_EXECUTABLES
) -> int:
    """Returns the HWND of the visible top-level Guild Wars 2 window, or 0 if not found."""
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        cls_name = cls_buf.value.lower()
        title = title_buf.value.lower()
        if cls_name.startswith("arenanet") or title in allowed_titles:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found[0] if found else 0


def _wait_for_foreground(hwnd: int, timeout: float) -> bool:
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)
    return user32.GetForegroundWindow() == hwnd


def bring_gw2_to_front(hwnd: Optional[int] = None, user_click_timeout: float = 5.0) -> bool:
    """
    Restores and focuses the Guild Wars 2 window. Returns True if it ended up in the foreground.

    Windows' focus-stealing protection usually refuses a bare SetForegroundWindow from
    another process, so this escalates: plain call -> Alt tap (counts as user input and
    unlocks the foreground lock) -> attach to the foreground thread's input queue.
    If all of that is refused, it waits up to user_click_timeout seconds for the user
    to click into the game themselves.
    """
    hwnd = hwnd or find_gw2_window()
    if not hwnd:
        return False
    SW_RESTORE = 9
    VK_MENU = 0x12
    KEYEVENTF_KEYUP = 0x0002

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    user32.SetForegroundWindow(hwnd)
    if _wait_for_foreground(hwnd, 0.3):
        return True

    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    if _wait_for_foreground(hwnd, 0.3):
        return True

    fg_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    my_thread = kernel32.GetCurrentThreadId()
    if fg_thread and fg_thread != my_thread and user32.AttachThreadInput(my_thread, fg_thread, True):
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            user32.AttachThreadInput(my_thread, fg_thread, False)
        if _wait_for_foreground(hwnd, 0.3):
            return True

    print(f"[Auto-Detect] Windows blocked the focus switch. Click into Guild Wars 2 within {user_click_timeout:.0f}s...")
    return _wait_for_foreground(hwnd, user_click_timeout)


def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """Returns (left, top, right, bottom) of a window in screen coordinates."""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


def get_client_origin(hwnd: int) -> Tuple[int, int]:
    """Returns the screen coordinates of the window's client-area top-left corner."""
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def is_region_unobstructed(hwnd: int, x: int, y: int, w: int, h: int) -> bool:
    """
    True if the given screen rectangle shows the window itself (nothing covering it),
    checked by hit-testing a 3x3 grid of points inside the rectangle.
    """
    GA_ROOT = 2
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    for fx in (0.05, 0.5, 0.95):
        for fy in (0.05, 0.5, 0.95):
            pt = wintypes.POINT(int(x + w * fx), int(y + h * fy))
            hit = user32.WindowFromPoint(pt)
            if not hit or user32.GetAncestor(hit, GA_ROOT) != hwnd:
                return False
    return True


def capture_window_client(hwnd: int):
    """
    Renders the window's client area even when other windows cover it
    (PrintWindow with PW_RENDERFULLCONTENT). Returns a BGR numpy array, or None
    if the window is minimized or the capture came back blank (e.g. exclusive fullscreen).
    """
    import numpy as np

    if not hwnd or user32.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None

    gdi32 = ctypes.windll.gdi32
    PW_CLIENTONLY_RENDERFULLCONTENT = 0x1 | 0x2
    hdc_win = user32.GetDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    old = gdi32.SelectObject(hdc_mem, bmp)
    try:
        ok = user32.PrintWindow(hwnd, hdc_mem, PW_CLIENTONLY_RENDERFULLCONTENT)
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth, bmi.biHeight, bmi.biPlanes, bmi.biBitCount = w, -h, 1, 32  # top-down BGRA
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)

    if not ok:
        return None
    img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    if img.max() < 8:  # all black: the game didn't render into the capture
        return None
    return img
