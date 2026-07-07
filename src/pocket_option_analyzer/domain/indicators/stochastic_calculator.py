from __future__ import annotations

from collections.abc import Sequence


class StochasticCalculator:
    """
    Calcula el oscilador estocástico.

    Devuelve:
    - valores suavizados de %K
    - valores de %D calculados como promedio móvil simple de %K
    """

    def calculate(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        k_period: int,
        d_period: int,
        smooth_period: int,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Calcula las series %K y %D.

        Si no hay suficientes datos, devuelve tuplas vacías.
        """

        self._validate_inputs(
            highs=highs,
            lows=lows,
            closes=closes,
            k_period=k_period,
            d_period=d_period,
            smooth_period=smooth_period,
        )

        if len(closes) < k_period:
            return (), ()

        raw_k_values = self._calculate_raw_k_values(
            highs=highs,
            lows=lows,
            closes=closes,
            k_period=k_period,
        )

        if len(raw_k_values) < smooth_period:
            return (), ()

        smoothed_k_values = self._simple_moving_average(
            values=raw_k_values,
            period=smooth_period,
        )

        if len(smoothed_k_values) < d_period:
            return smoothed_k_values, ()

        d_values = self._simple_moving_average(
            values=smoothed_k_values,
            period=d_period,
        )

        return smoothed_k_values, d_values

    def _validate_inputs(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        k_period: int,
        d_period: int,
        smooth_period: int,
    ) -> None:

        if k_period <= 0:
            raise ValueError("Stochastic K period must be greater than zero.")

        if d_period <= 0:
            raise ValueError("Stochastic D period must be greater than zero.")

        if smooth_period <= 0:
            raise ValueError(
                "Stochastic smooth period must be greater than zero."
            )

        if not (
            len(highs)
            == len(lows)
            == len(closes)
        ):
            raise ValueError(
                "High, low and close sequences must have the same length."
            )

    def _calculate_raw_k_values(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        k_period: int,
    ) -> tuple[float, ...]:

        values: list[float] = []

        for index in range(
            k_period - 1,
            len(closes),
        ):
            start = index - k_period + 1
            end = index + 1

            highest_high = max(
                highs[start:end],
            )
            lowest_low = min(
                lows[start:end],
            )

            price_range = highest_high - lowest_low

            if price_range == 0:
                values.append(50.0)
                continue

            k_value = (
                (closes[index] - lowest_low)
                / price_range
            ) * 100

            values.append(k_value)

        return tuple(values)

    def _simple_moving_average(
        self,
        values: Sequence[float],
        period: int,
    ) -> tuple[float, ...]:

        if len(values) < period:
            return ()

        averages: list[float] = []

        for index in range(
            period - 1,
            len(values),
        ):
            start = index - period + 1
            end = index + 1

            window = values[start:end]

            averages.append(
                sum(window) / period,
            )

        return tuple(averages)