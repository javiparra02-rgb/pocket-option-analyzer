"""
Runtime infrastructure.

Componentes responsables del ciclo de vida de la aplicación.
"""

from .context import ApplicationContext
from .state import RuntimeState, RuntimeStatus
from .ticker import Ticker

__all__ = [
    "ApplicationContext",
    "RuntimeState",
    "RuntimeStatus",
    "Ticker",
]