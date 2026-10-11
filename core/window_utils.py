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
