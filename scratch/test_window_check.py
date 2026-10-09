import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_active_window_info():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, "", ""
    
    length = user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title_buf, length + 1)
    
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    # Try getting process name
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    proc_name = ""
    if h_proc:
        try:
            exe_buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, exe_buf, ctypes.byref(size)):
                proc_name = exe_buf.value
        finally:
            kernel32.CloseHandle(h_proc)
            
    return hwnd, title_buf.value, proc_name

hwnd, title, proc = get_active_window_info()
print(f"Active Window Title: '{title}'")
print(f"Active Process: '{proc}'")
