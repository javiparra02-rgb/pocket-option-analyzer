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
    Construye un IndicatorSnapshot desde una serie de velas visuales.

    Flujo:
    - CandleSeries visual
    - PriceSeries OHLC normalizada
    - EMA / RSI / Stochastic
    - IndicatorSnapshot

    No usa precios reales.
    No interactúa con Pocket Option.
    Solo transforma datos visuales detectados previamente.
    """

    def __init__(
        self,
        price_series_builder: VisualPriceSeriesBuilder | None = None,
        indicator_snapshot_builder: IndicatorSnapshotBuilder | None = None,
    ) -> None:
        self._price_series_builder = (
            price_series_builder or VisualPriceSeriesBuilder()
        )
        self._indicator_snapshot_builder = (
            indicator_snapshot_builder or IndicatorSnapshotBuilder()
        )

    def build(
        self,
        series: CandleSeries,
        profile: StrategyProfile,
    ) -> IndicatorSnapshot | None:
        """
        Construye indicadores desde velas visuales.

        Si no hay suficientes velas o algún indicador no puede calcularse,
        devuelve None.
        """

        price_series = self._price_series_builder.build(
            series=series,
        )

        if price_series.is_empty():
            return None

        return self._indicator_snapshot_builder.build(
            series=price_series,
            profile=profile,
        )