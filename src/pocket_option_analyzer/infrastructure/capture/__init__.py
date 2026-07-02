"""
Infraestructura de captura.

Expone los contratos, modelos y adaptadores
del sistema de captura.
"""

from .contracts.window_locator import WindowLocator
from .models import WindowInfo

__all__ = [
    "WindowLocator",
    "WindowInfo",
]