"""
Infraestructura específica de Windows.

Este paquete encapsula todas las llamadas a la API Win32.
El resto del proyecto no debe depender directamente de pywin32,
ctypes u otras bibliotecas específicas del sistema operativo.
"""

from pocket_option_analyzer.infrastructure.windows.recording_safety_guard import (
    NativeWindowSnapshot,
    RecordingSafetyStatus,
    ScreenRectangle,
    WindowsRecordingSafetyGuard,
)
from pocket_option_analyzer.infrastructure.windows.window_capture_excluder import (
    WindowsWindowCaptureExcluder,
)

__all__ = [
    "NativeWindowSnapshot",
    "RecordingSafetyStatus",
    "ScreenRectangle",
    "WindowsRecordingSafetyGuard",
    "WindowsWindowCaptureExcluder",
]
