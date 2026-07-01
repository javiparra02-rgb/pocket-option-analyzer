"""
Runtime infrastructure.

Componentes responsables del ciclo de vida de la aplicación.
"""

from .context import ApplicationContext
from .state import RuntimeState, RuntimeStatus

__all__ = [
    "ApplicationContext",
    "RuntimeState",
    "RuntimeStatus",
]