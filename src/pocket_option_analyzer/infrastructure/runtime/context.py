from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.infrastructure.config import Settings
from pocket_option_analyzer.infrastructure.container import ServiceContainer
from pocket_option_analyzer.infrastructure.logging import LoggingManager

from .state import RuntimeState


@dataclass(slots=True)
class ApplicationContext:
    """
    Contexto principal de la aplicación.

    Agrupa todas las dependencias compartidas utilizadas por
    el Runtime Engine y los distintos sistemas.
    """

    settings: Settings
    logger: LoggingManager
    runtime_state: RuntimeState
    services: ServiceContainer