"""
Adaptadores de captura.
"""

from .mss_capture_adapter import MSSCaptureAdapter
from .win32_window_locator import Win32WindowLocator

__all__ = [
    "MSSCaptureAdapter",
    "Win32WindowLocator",
]