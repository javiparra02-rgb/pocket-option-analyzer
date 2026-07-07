from __future__ import annotations

from collections.abc import Sequence


class EmaCalculator:
    """
    Calcula una media móvil exponencial.

    La primera EMA se inicializa usando SMA del primer bloque.
    """

    def calculate(
        self,
        values: Sequence[float],
        period: int,
    ) -> tuple[float, ...]:
        """
        Calcula la serie EMA para los valores entregados.

        Si no hay suficientes datos para el período solicitado,
        devuelve una tupla vacía.
        """

        if period <= 0:
            raise ValueError("EMA period must be greater than zero.")

        if len(values) < period:
            return ()

        alpha = 2 / (period + 1)

        first_ema = sum(values[:period]) / period

        ema_values: list[float] = [
            first_ema,
        ]

        previous_ema = first_ema

        for value in values[period:]:
            current_ema = (value - previous_ema) * alpha + previous_ema

            ema_values.append(current_ema)

            previous_ema = current_ema

        return tuple(ema_values)