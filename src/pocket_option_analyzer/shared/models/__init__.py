"""
Modelos compartidos del proyecto.

Todos los modelos definidos aquí son inmutables y representan datos
compartidos entre los distintos módulos del sistema.
"""

from .frame import Frame
from .point import Point
from .rectangle import Rectangle

__all__ = [
    "Frame",
    "Point",
    "Rectangle",
]