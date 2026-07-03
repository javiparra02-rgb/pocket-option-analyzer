from __future__ import annotations

import ctypes


class RECT(ctypes.Structure):
    """
    Estructura RECT de la API Win32.
    """

    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]