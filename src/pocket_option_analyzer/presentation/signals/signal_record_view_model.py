from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalRecordViewModel:
    """
    Modelo de presentación para mostrar una señal en la GUI.

    Esta clase no contiene lógica de negocio.
    Solo representa datos ya preparados para pantalla.
    """

    direction_label: str

    strength_label: str

    reason: str

    source: str

    created_at_label: str

    is_actionable: bool

    css_class: str