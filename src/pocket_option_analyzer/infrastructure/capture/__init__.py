"""
Infraestructura de captura.
"""

from .contracts import ScreenCapture, WindowLocator
from .models import Frame, WindowInfo
from .services import FrameFactory

__all__ = [
    "Frame",
    "FrameFactory",
    "ScreenCapture",
    "WindowInfo",
    "WindowLocator",
]