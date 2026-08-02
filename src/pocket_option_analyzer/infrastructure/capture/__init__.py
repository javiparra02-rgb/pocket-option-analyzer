"""
Infraestructura de captura.
"""

from .contracts import ScreenCapture, WindowLocator
from .models import Frame, WindowInfo
from .services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)

__all__ = [
    "CaptureService",
    "Frame",
    "FrameBuffer",
    "FrameFactory",
    "ScreenCapture",
    "WindowInfo",
    "WindowLocator",
]
