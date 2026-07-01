"""
Infrastructure configuration package.

Este paquete contiene la configuración centralizada del proyecto.
"""

from .settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]