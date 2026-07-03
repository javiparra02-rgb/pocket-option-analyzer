"""
Capa nativa de Windows.

Encapsula el acceso mediante ctypes a las DLL del sistema operativo.
"""

from .callbacks import EnumWindowsProc
from .constants import PW_RENDERFULLCONTENT
from .structures import POINT, RECT
from .user32 import User32

__all__ = [
    "EnumWindowsProc",
    "PW_RENDERFULLCONTENT",
    "POINT",
    "RECT",
    "User32",
]