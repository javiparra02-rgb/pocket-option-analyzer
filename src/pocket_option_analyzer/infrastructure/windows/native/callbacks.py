from __future__ import annotations

import ctypes

# BOOL CALLBACK EnumWindowsProc(HWND hwnd, LPARAM lParam)
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    ctypes.c_void_p,
    ctypes.c_void_p,
)