from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.domain.indicators.stochastic_calculation_diagnostics import (
    StochasticCalculationDiagnostics,
)


@dataclass(
    frozen=True,
    slots=True,
)
class StochasticSnapshot:
    """
    Estado actual del oscilador estocástico.

    k_previous/d_previous permiten saber si ocurrió un cruce real
    entre la vela anterior y la vela actual.
    """

    k_value: float
    d_value: float
    k_previous: float
    d_previous: float
    diagnostics: StochasticCalculationDiagnostics | None = None

    @property
    def crossed_up(self) -> bool:
        """
        %K cruzó hacia arriba sobre %D.
        """

        return self.k_previous <= self.d_previous and self.k_value > self.d_value

    @property
    def crossed_down(self) -> bool:
        """
        %K cruzó hacia abajo bajo %D.
        """

        return self.k_previous >= self.d_previous and self.k_value < self.d_value
