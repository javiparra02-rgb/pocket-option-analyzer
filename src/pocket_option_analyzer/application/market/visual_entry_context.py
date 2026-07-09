from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisualEntryContext:
    """
    Contexto visual resumido para explicar el estado actual del gráfico.

    No genera señales.
    No ejecuta operaciones.
    Solo ayuda a interpretar qué está leyendo el sistema.
    """

    context_label: str

    entry_state_label: str