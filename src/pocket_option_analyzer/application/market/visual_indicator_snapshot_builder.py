from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pocket_option_analyzer.application.market.candle_interval_indicator_cache import (
    CandleIntervalIndicatorCache,
)
from pocket_option_analyzer.application.market.visual_indicator_snapshot_context import (
    VisualIndicatorSnapshotContext,
)
from pocket_option_analyzer.application.market.visual_price_series_builder import (
    VisualPriceSeriesBuilder,
)
from pocket_option_analyzer.domain.indicators import (
    IndicatorSnapshot,
    IndicatorSnapshotBuilder,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleSeries,
    CandleType,
)

NowProvider = Callable[
    [],
    datetime,
]


class VisualIndicatorSnapshotBuilder:
    """
    Construye indicadores estables desde velas visuales cerradas.

    Flujo:
    - recibe la serie visual completa;
    - excluye la última vela potencialmente abierta;
    - reconstruye la serie OHLC;
    - calcula EMA, RSI y Stochastic;
    - conserva el resultado durante el intervalo actual.

    El snapshot solo cambia al entrar en una nueva vela de 30 segundos,
    después de un breve margen para que aparezca la nueva vela visual.
    """

    def __init__(
        self,
        price_series_builder: VisualPriceSeriesBuilder | None = None,
        indicator_snapshot_builder: IndicatorSnapshotBuilder | None = None,
        indicator_cache: CandleIntervalIndicatorCache | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._price_series_builder = (
            price_series_builder
            or VisualPriceSeriesBuilder()
        )
        self._indicator_snapshot_builder = (
            indicator_snapshot_builder
            or IndicatorSnapshotBuilder()
        )
        self._indicator_cache = (
            indicator_cache
            or CandleIntervalIndicatorCache(
                settling_seconds=2.0,
            )
        )
        self._now_provider = (
            now_provider
            or self._local_now
        )
        self._snapshot_context: (
            VisualIndicatorSnapshotContext
            | None
        ) = None

    @property
    def snapshot_context(
        self,
    ) -> VisualIndicatorSnapshotContext | None:
        """
        Contexto perteneciente al snapshot actualmente almacenado.

        No representa necesariamente la captura visual más reciente.
        """

        return self._snapshot_context

    def build(
        self,
        series: CandleSeries,
        profile: StrategyProfile,
    ) -> IndicatorSnapshot | None:
        """
        Obtiene el snapshot estable del intervalo actual.
        """

        observed_at = self._now_provider()

        return self._indicator_cache.resolve(
            observed_at=observed_at,
            snapshot_factory=lambda: self._build_uncached(
                series=series,
                profile=profile,
            ),
        )

    def reset_cache(
        self,
    ) -> None:
        """
        Elimina el snapshot y su contexto de origen.
        """

        self._indicator_cache.reset()
        self._snapshot_context = None

    def _build_uncached(
        self,
        series: CandleSeries,
        profile: StrategyProfile,
    ) -> IndicatorSnapshot | None:
        """
        Calcula un snapshot nuevo y conserva su contexto visual.

        El contexto solo se reemplaza cuando el cálculo completo termina
        correctamente. Si el cálculo falla, el caché y su contexto anterior
        permanecen intactos.
        """

        closed_series = series.without_latest()

        eligible_closed_candles = tuple(
            candle
            for candle in closed_series.candles
            if candle.candle_type is not CandleType.UNKNOWN
        )

        price_series = self._price_series_builder.build(
            series=closed_series,
        )

        if price_series.is_empty():
            return None

        snapshot = self._indicator_snapshot_builder.build(
            series=price_series,
            profile=profile,
        )

        if snapshot is None:
            return None

        geometry_valid_count = sum(
            1
            for candle in eligible_closed_candles
            if candle.candidate.geometry is not None
        )

        self._snapshot_context = (
            VisualIndicatorSnapshotContext(
                visible_candle_count=len(
                    series,
                ),
                ohlc_candle_count=len(
                    price_series,
                ),
                geometry_valid_count=geometry_valid_count,
                geometry_total_count=len(
                    eligible_closed_candles,
                ),
            )
        )

        return snapshot

    @staticmethod
    def _local_now() -> datetime:
        """
        Devuelve fecha y hora local con zona horaria.
        """

        return datetime.now().astimezone()