from __future__ import annotations

from pocket_option_analyzer.application.market.visual_price_series_builder import (
    VisualPriceSeriesBuilder,
)
from pocket_option_analyzer.domain.indicators import (
    IndicatorSnapshot,
    IndicatorSnapshotBuilder,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import CandleSeries


class VisualIndicatorSnapshotBuilder:
    """
    Construye un IndicatorSnapshot desde velas visuales cerradas.

    Flujo:
    - CandleSeries visual completa;
    - exclusión de la última vela potencialmente abierta;
    - PriceSeries OHLC normalizada;
    - EMA / RSI / Stochastic;
    - IndicatorSnapshot.

    La vela en formación permanece disponible para el diagnóstico
    visual, pero no modifica los indicadores hasta considerarse cerrada.

    No usa precios reales.
    No interactúa con Pocket Option.
    """

    def __init__(
        self,
        price_series_builder: VisualPriceSeriesBuilder | None = None,
        indicator_snapshot_builder: IndicatorSnapshotBuilder | None = None,
    ) -> None:
        self._price_series_builder = (
            price_series_builder
            or VisualPriceSeriesBuilder()
        )
        self._indicator_snapshot_builder = (
            indicator_snapshot_builder
            or IndicatorSnapshotBuilder()
        )

    def build(
        self,
        series: CandleSeries,
        profile: StrategyProfile,
    ) -> IndicatorSnapshot | None:
        """
        Construye indicadores usando únicamente velas cerradas.

        La última vela visual se excluye antes de generar OHLC.
        Si no quedan suficientes velas, devuelve None.
        """

        closed_series = series.without_latest()

        price_series = self._price_series_builder.build(
            series=closed_series,
        )

        if price_series.is_empty():
            return None

        return self._indicator_snapshot_builder.build(
            series=price_series,
            profile=profile,
        )