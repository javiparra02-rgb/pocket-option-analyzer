"""
Infrastructure capture package.

Contiene los componentes responsables de localizar y capturar
la ventana de Pocket Option.
"""

from .window_locator import WindowLocator

__all__ = [
    "WindowLocator",
]