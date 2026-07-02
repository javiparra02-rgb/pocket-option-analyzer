"""
Adaptadores de captura.
"""

from .mss_capture_adapter import MSSCaptureAdapter
from .win32_window_locator import Win32WindowLocator
from .window_enumerator import WindowEnumerator

__all__ = [
    "MSSCaptureAdapter",
    "Win32WindowLocator",
    "WindowEnumerator",
]