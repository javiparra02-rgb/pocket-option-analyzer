"""
Infraestructura de captura.
"""

from .contracts import ScreenCapture, WindowLocator
from .frame_provider import PocketOptionFrameProvider
from .models import Frame, WindowInfo

__all__ = [
    "Frame",
    "PocketOptionFrameProvider",
    "ScreenCapture",
    "WindowInfo",
    "WindowLocator",
]