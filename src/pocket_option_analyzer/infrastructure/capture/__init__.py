"""
Infraestructura de captura.
"""

from .contracts import ScreenCapture, WindowLocator
from .errors import CaptureUnavailableError
from .models import Frame, WindowInfo
from .services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)

__all__ = [
    "CaptureService",
    "CaptureUnavailableError",
    "Frame",
    "FrameBuffer",
    "FrameFactory",
    "ScreenCapture",
    "WindowInfo",
    "WindowLocator",
]
