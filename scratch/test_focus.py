import ctypes
from ctypes import wintypes

def is_target_game_focused(allowed_titles=("guild wars 2", "gw2"), allowed_exes=("gw2-64.exe", "gw2.exe")) -> bool:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title_lower = buf.value.lower()
        for t in allowed_titles:
            if t in title_lower:
                return True

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h_proc:
        try:
            exe_buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, exe_buf, ctypes.byref(size)):
                exe_lower = exe_buf.value.lower()
                for exe in allowed_exes:
                    if exe in exe_lower:
                        return True
        finally:
            kernel32.CloseHandle(h_proc)

    return False

# In this python process, GW2 is likely not focused:
print("Is GW2 focused right now?", is_target_game_focused())
