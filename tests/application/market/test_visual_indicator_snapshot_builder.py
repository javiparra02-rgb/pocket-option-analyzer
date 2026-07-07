from pocket_option_analyzer.application.market import (
    VisualIndicatorSnapshotBuilder,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
)


class FakePriceSeriesBuilder:

    def __init__(
        self,
        result: PriceSeries,
    ) -> None:
        self.result = result
        self.received_series = None

    def build(
        self,
        series,
    ) -> PriceSeries:
        self.received_series = series
        return self.result


class FakeIndicatorSnapshotBuilder:

    def __init__(
        self,
        result: IndicatorSnapshot | None,
    ) -> None:
        self.result = result
        self.received_series = None
        self.received_profile = None
        self.was_called = False

    def build(
        self,
        series,
        profile,
    ) -> IndicatorSnapshot | None:
        self.was_called = True
        self.received_series = series
        self.received_profile = profile
        return self.result


def _visual_series() -> CandleSeries:

    return CandleSeries(
        candles=(
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=40,
                    width=5,
                    height=20,
                    area=100,
                ),
                candle_type=CandleType.BULLISH,
            ),
        ),
    )


def _price_series() -> PriceSeries:

    return PriceSeries(
        candles=(
            PriceCandle(
                open=100.0,
                high=105.0,
                low=95.0,
                close=104.0,
            ),
        ),
    )


def _indicator_snapshot() -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=105.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=57.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=18.0,
            d_previous=20.0,
            k_value=24.0,
            d_value=21.0,
        ),
    )


def test_build_creates_indicator_snapshot_from_visual_series() -> None:

    visual_series = _visual_series()
    price_series = _price_series()
    profile = StrategyProfile.otc_precision_10s()
    indicator_snapshot = _indicator_snapshot()

    price_builder = FakePriceSeriesBuilder(
        result=price_series,
    )
    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=indicator_snapshot,
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=price_builder,
        indicator_snapshot_builder=indicator_builder,
    )

    result = builder.build(
        series=visual_series,
        profile=profile,
    )

    assert result is indicator_snapshot
    assert price_builder.received_series is visual_series
    assert indicator_builder.received_series is price_series
    assert indicator_builder.received_profile is profile


def test_build_returns_none_when_visual_series_produces_empty_price_series() -> None:

    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=_indicator_snapshot(),
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=PriceSeries(
                candles=(),
            ),
        ),
        indicator_snapshot_builder=indicator_builder,
    )

    result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None
    assert indicator_builder.was_called is False


def test_build_returns_none_when_indicators_cannot_be_calculated() -> None:

    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=None,
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=_price_series(),
        ),
        indicator_snapshot_builder=indicator_builder,
    )

    result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None
    assert indicator_builder.was_called is True