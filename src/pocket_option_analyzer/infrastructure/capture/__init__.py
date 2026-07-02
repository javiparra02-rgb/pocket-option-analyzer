"""
Infraestructura de captura.
"""

from .contracts import ScreenCapture, WindowLocator
from .models import Frame, WindowInfo

__all__ = [
    "Frame",
    "ScreenCapture",
    "WindowInfo",
    "WindowLocator",
]