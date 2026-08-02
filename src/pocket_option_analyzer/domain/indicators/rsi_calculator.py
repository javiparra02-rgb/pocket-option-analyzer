from __future__ import annotations

from collections.abc import Sequence


class RsiCalculator:
    """
    Calcula el Relative Strength Index (RSI).

    Usa suavizado tipo Wilder:
    - promedio inicial simple de ganancias/pérdidas
    - luego suavizado recursivo
    """

    def calculate(
        self,
        values: Sequence[float],
        period: int,
    ) -> tuple[float, ...]:
        """
        Calcula la serie RSI para los valores entregados.

        Para calcular RSI se necesitan al menos period + 1 valores,
        porque el cálculo usa cambios entre precios consecutivos.
        """

        if period <= 0:
            raise ValueError("RSI period must be greater than zero.")

        if len(values) <= period:
            return ()

        deltas = self._calculate_deltas(values)

        initial_deltas = deltas[:period]

        average_gain = self._average_gain(initial_deltas)
        average_loss = self._average_loss(initial_deltas)

        rsi_values: list[float] = [
            self._calculate_rsi(
                average_gain=average_gain,
                average_loss=average_loss,
            )
        ]

        for delta in deltas[period:]:
            gain = max(
                delta,
                0.0,
            )
            loss = max(
                -delta,
                0.0,
            )

            average_gain = ((average_gain * (period - 1)) + gain) / period
            average_loss = ((average_loss * (period - 1)) + loss) / period

            rsi_values.append(
                self._calculate_rsi(
                    average_gain=average_gain,
                    average_loss=average_loss,
                )
            )

        return tuple(rsi_values)

    def _calculate_deltas(
        self,
        values: Sequence[float],
    ) -> tuple[float, ...]:

        return tuple(
            current - previous
            for previous, current in zip(
                values,
                values[1:],
            )
        )

    def _average_gain(
        self,
        deltas: Sequence[float],
    ) -> float:

        gains = [
            max(
                delta,
                0.0,
            )
            for delta in deltas
        ]

        return sum(gains) / len(gains)

    def _average_loss(
        self,
        deltas: Sequence[float],
    ) -> float:

        losses = [
            max(
                -delta,
                0.0,
            )
            for delta in deltas
        ]

        return sum(losses) / len(losses)

    def _calculate_rsi(
        self,
        average_gain: float,
        average_loss: float,
    ) -> float:

        if average_gain == 0 and average_loss == 0:
            return 50.0

        if average_loss == 0:
            return 100.0

        relative_strength = average_gain / average_loss

        return 100 - (100 / (1 + relative_strength))
