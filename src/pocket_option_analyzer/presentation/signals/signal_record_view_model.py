from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalRecordViewModel:
    """
    Modelo de presentación para mostrar una señal en la GUI.
    """

    direction_label: str

    strength_label: str

    reason: str

    source: str

    created_at_label: str

    is_actionable: bool

    css_class: str

    visual_diagnostics_label: str = "Diagnóstico visual: -"