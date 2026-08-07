"""
Infraestructura de captura.
"""

from .contracts import CaptureRegion, ScreenCapture
from .errors import CaptureUnavailableError
from .models import Frame
from .services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)

__all__ = [
    "CaptureRegion",
    "CaptureService",
    "CaptureUnavailableError",
    "Frame",
    "FrameBuffer",
    "FrameFactory",
    "ScreenCapture",
]
