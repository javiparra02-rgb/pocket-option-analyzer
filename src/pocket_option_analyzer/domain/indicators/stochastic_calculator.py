from __future__ import annotations

from collections.abc import Sequence

from pocket_option_analyzer.domain.indicators.stochastic_calculation_diagnostics import (
    StochasticCalculationDiagnostics,
)


class StochasticCalculator:
    """
    Calcula el oscilador estocástico.

    Devuelve:
    - valores suavizados de %K;
    - valores de %D calculados como promedio móvil simple de %K.

    También puede devolver el diagnóstico de la última ventana
    utilizada para construir el resultado.
    """

    def calculate(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        k_period: int,
        d_period: int,
        smooth_period: int,
    ) -> tuple[
        tuple[float, ...],
        tuple[float, ...],
    ]:
        """
        Calcula las series %K y %D.

        Mantiene el contrato público anterior para los consumidores
        que no necesitan información de auditoría.
        """

        (
            k_values,
            d_values,
            _,
        ) = self.calculate_with_diagnostics(
            highs=highs,
            lows=lows,
            closes=closes,
            k_period=k_period,
            d_period=d_period,
            smooth_period=smooth_period,
        )

        return (
            k_values,
            d_values,
        )

    def calculate_with_diagnostics(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        k_period: int,
        d_period: int,
        smooth_period: int,
    ) -> tuple[
        tuple[float, ...],
        tuple[float, ...],
        StochasticCalculationDiagnostics | None,
    ]:
        """
        Calcula %K, %D y la auditoría de la última ventana disponible.

        Si todavía no existe un valor de %D completo, el diagnóstico
        se devuelve como None.
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
            return (
                (),
                (),
                None,
            )

        raw_k_values = self._calculate_raw_k_values(
            highs=highs,
            lows=lows,
            closes=closes,
            k_period=k_period,
        )

        if len(raw_k_values) < smooth_period:
            return (
                (),
                (),
                None,
            )

        smoothed_k_values = self._simple_moving_average(
            values=raw_k_values,
            period=smooth_period,
        )

        if len(smoothed_k_values) < d_period:
            return (
                smoothed_k_values,
                (),
                None,
            )

        d_values = self._simple_moving_average(
            values=smoothed_k_values,
            period=d_period,
        )

        diagnostics = self._build_diagnostics(
            highs=highs,
            lows=lows,
            closes=closes,
            raw_k_values=raw_k_values,
            smoothed_k_values=smoothed_k_values,
            d_values=d_values,
            k_period=k_period,
        )

        return (
            smoothed_k_values,
            d_values,
            diagnostics,
        )

    def _build_diagnostics(
        self,
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        raw_k_values: tuple[float, ...],
        smoothed_k_values: tuple[float, ...],
        d_values: tuple[float, ...],
        k_period: int,
    ) -> StochasticCalculationDiagnostics:
        """
        Construye la traza correspondiente al último valor disponible.
        """

        window_start = len(closes) - k_period

        highest_high = max(
            highs[
                window_start:
            ],
        )
        lowest_low = min(
            lows[
                window_start:
            ],
        )

        return StochasticCalculationDiagnostics(
            source_candle_count=len(
                closes,
            ),
            k_period=k_period,
            highest_high=highest_high,
            lowest_low=lowest_low,
            latest_close=closes[-1],
            latest_raw_k=raw_k_values[-1],
            latest_smoothed_k=smoothed_k_values[-1],
            latest_d=d_values[-1],
        )

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
            raise ValueError(
                "Stochastic K period must be greater than zero."
            )

        if d_period <= 0:
            raise ValueError(
                "Stochastic D period must be greater than zero."
            )

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
            start = (
                index
                - k_period
                + 1
            )
            end = index + 1

            highest_high = max(
                highs[
                    start:end
                ],
            )
            lowest_low = min(
                lows[
                    start:end
                ],
            )

            price_range = (
                highest_high
                - lowest_low
            )

            if price_range == 0:
                values.append(
                    50.0,
                )
                continue

            k_value = (
                (
                    closes[index]
                    - lowest_low
                )
                / price_range
            ) * 100

            values.append(
                k_value,
            )

        return tuple(
            values,
        )

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
            start = (
                index
                - period
                + 1
            )
            end = index + 1

            window = values[
                start:end
            ]

            averages.append(
                sum(
                    window,
                )
                / period,
            )

        return tuple(
            averages,
        )