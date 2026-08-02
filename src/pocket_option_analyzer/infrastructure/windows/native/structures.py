from __future__ import annotations

import ctypes


class POINT(ctypes.Structure):
    """
    Estructura POINT de Win32.
    """

    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class RECT(ctypes.Structure):
    """
    Estructura RECT de Win32.
    """

    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]
