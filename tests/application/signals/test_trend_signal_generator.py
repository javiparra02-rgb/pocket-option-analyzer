from pocket_option_analyzer.application.signals import (
    TrendSignalGenerator,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.vision.models import (
    CandleSeries,
    MarketAnalysis,
    TrendDirection,
)


def _analysis(
    trend: TrendDirection,
) -> MarketAnalysis:

    return MarketAnalysis(
        series=CandleSeries(
            candles=(),
        ),
        trend=trend,
    )


def test_generate_returns_call_for_bullish_trend() -> None:

    generator = TrendSignalGenerator()

    signal = generator.generate(
        _analysis(
            TrendDirection.BULLISH,
        )
    )

    assert signal.direction is SignalDirection.CALL
    assert signal.strength is SignalStrength.MEDIUM
    assert signal.is_actionable is True


def test_generate_returns_put_for_bearish_trend() -> None:

    generator = TrendSignalGenerator()

    signal = generator.generate(
        _analysis(
            TrendDirection.BEARISH,
        )
    )

    assert signal.direction is SignalDirection.PUT
    assert signal.strength is SignalStrength.MEDIUM
    assert signal.is_actionable is True


def test_generate_returns_none_for_sideways_trend() -> None:

    generator = TrendSignalGenerator()

    signal = generator.generate(
        _analysis(
            TrendDirection.SIDEWAYS,
        )
    )

    assert signal.direction is SignalDirection.NONE
    assert signal.strength is SignalStrength.NONE
    assert signal.is_actionable is False