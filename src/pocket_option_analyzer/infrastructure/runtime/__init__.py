"""
Runtime infrastructure.

Componentes responsables del ciclo de vida de la aplicación.
"""

from .state import RuntimeState, RuntimeStatus

__all__ = [
    "RuntimeState",
    "RuntimeStatus",
]