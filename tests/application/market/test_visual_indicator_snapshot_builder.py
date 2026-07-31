from datetime import datetime

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
    CandleGeometry,
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
        self.build_calls = 0

    def build(
        self,
        series,
        profile,
    ) -> IndicatorSnapshot | None:
        self.build_calls += 1
        self.was_called = True
        self.received_series = series
        self.received_profile = profile
        return self.result


class MutableNowProvider:

    def __init__(
        self,
        current: datetime,
    ) -> None:
        self.current = current

    def __call__(
        self,
    ) -> datetime:
        return self.current


def _visual_series() -> CandleSeries:

    return CandleSeries(
        candles=(
            ClassifiedCandle(
                candidate=CandleCandidate(
                    geometry=CandleGeometry(
                        high_y=40,
                        body_top_y=45,
                        body_bottom_y=54,
                        low_y=59,
                    ),
                    x=10,
                    y=40,
                    width=5,
                    height=20,
                    area=100,
                ),
                candle_type=CandleType.BULLISH,
            ),
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=20,
                    y=35,
                    width=5,
                    height=25,
                    area=125,
                ),
                candle_type=CandleType.BEARISH,
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
    assert price_builder.received_series is not visual_series
    assert price_builder.received_series.candles == (
        visual_series.candles[0],
    )
    assert len(visual_series) == 2
    assert indicator_builder.received_series is price_series
    assert indicator_builder.received_profile is profile
    assert builder.snapshot_context is not None

    assert (
        builder.snapshot_context.visible_candle_count
        == 2
    )
    assert (
        builder.snapshot_context.ohlc_candle_count
        == 1
    )
    assert (
        builder.snapshot_context.geometry_valid_count
        == 1
    )
    assert (
        builder.snapshot_context.geometry_total_count
        == 1
    )


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


def test_build_returns_none_when_only_forming_candle_is_visible() -> None:

    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=_indicator_snapshot(),
    )

    visual_series = _visual_series()

    builder = VisualIndicatorSnapshotBuilder(
        indicator_snapshot_builder=indicator_builder,
    )

    result = builder.build(
        series=CandleSeries(
            candles=(
                visual_series.candles[-1],
            ),
        ),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None
    assert indicator_builder.was_called is False


def test_build_reuses_indicator_snapshot_inside_same_candle() -> None:

    now_provider = MutableNowProvider(
        current=datetime(
            2026,
            7,
            30,
            16,
            44,
            5,
        ),
    )

    indicator_snapshot = _indicator_snapshot()
    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=indicator_snapshot,
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=_price_series(),
        ),
        indicator_snapshot_builder=indicator_builder,
        now_provider=now_provider,
    )

    first_result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    now_provider.current = datetime(
        2026,
        7,
        30,
        16,
        44,
        25,
    )

    second_result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert first_result is indicator_snapshot
    assert second_result is indicator_snapshot
    assert indicator_builder.build_calls == 1


def test_build_recalculates_after_new_candle_settles() -> None:

    now_provider = MutableNowProvider(
        current=datetime(
            2026,
            7,
            30,
            16,
            44,
            20,
        ),
    )

    first_snapshot = _indicator_snapshot()
    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=first_snapshot,
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=_price_series(),
        ),
        indicator_snapshot_builder=indicator_builder,
        now_provider=now_provider,
    )

    assert builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    ) is first_snapshot

    second_snapshot = IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=200.0,
            slow_value=180.0,
            separation_candles=4,
        ),
        rsi=RsiSnapshot(
            value=61.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=40.0,
            d_previous=45.0,
            k_value=55.0,
            d_value=50.0,
        ),
    )

    indicator_builder.result = second_snapshot

    now_provider.current = datetime(
        2026,
        7,
        30,
        16,
        44,
        30,
        500000,
    )

    settling_result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert settling_result is first_snapshot
    assert indicator_builder.build_calls == 1

    now_provider.current = datetime(
        2026,
        7,
        30,
        16,
        44,
        32,
    )

    updated_result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert updated_result is second_snapshot
    assert indicator_builder.build_calls == 2


def test_snapshot_context_remains_bound_to_cached_snapshot() -> None:

    now_provider = MutableNowProvider(
        current=datetime(
            2026,
            7,
            30,
            23,
            53,
            5,
        ),
    )

    indicator_builder = FakeIndicatorSnapshotBuilder(
        result=_indicator_snapshot(),
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=_price_series(),
        ),
        indicator_snapshot_builder=indicator_builder,
        now_provider=now_provider,
    )

    original_series = _visual_series()

    first_result = builder.build(
        series=original_series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    first_context = builder.snapshot_context

    larger_current_series = CandleSeries(
        candles=(
            *original_series.candles,
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=30,
                    y=30,
                    width=5,
                    height=20,
                    area=100,
                    geometry=CandleGeometry(
                        high_y=30,
                        body_top_y=35,
                        body_bottom_y=44,
                        low_y=49,
                    ),
                ),
                candle_type=CandleType.BULLISH,
            ),
        ),
    )

    now_provider.current = datetime(
        2026,
        7,
        30,
        23,
        53,
        20,
    )

    second_result = builder.build(
        series=larger_current_series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert second_result is first_result
    assert builder.snapshot_context is first_context
    assert first_context is not None
    assert first_context.visible_candle_count == 2
    assert first_context.ohlc_candle_count == 1


def test_builder_exposes_current_snapshot_timing_status() -> None:

    now_provider = MutableNowProvider(
        current=datetime(
            2026,
            7,
            31,
            11,
            9,
            35,
        ),
    )

    builder = VisualIndicatorSnapshotBuilder(
        price_series_builder=FakePriceSeriesBuilder(
            result=_price_series(),
        ),
        indicator_snapshot_builder=(
            FakeIndicatorSnapshotBuilder(
                result=_indicator_snapshot(),
            )
        ),
        now_provider=now_provider,
    )

    result = builder.build(
        series=_visual_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    status = builder.snapshot_timing_status

    assert result is not None
    assert status is not None
    assert status.state_label == "ACTUAL"
    assert status.allows_actionable_signals is True
    assert status.requested_key.started_at.second == 30
    assert status.cached_key == status.requested_key