from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalStrength,
)


def test_call_signal_is_actionable() -> None:

    signal = MarketSignal(
        direction=SignalDirection.CALL,
        strength=SignalStrength.HIGH,
        reason="Bullish conditions detected.",
    )

    assert signal.is_actionable is True


def test_neutral_signal_is_not_actionable() -> None:

    signal = MarketSignal.neutral(
        reason="Market is sideways.",
    )

    assert signal.direction is SignalDirection.NONE
    assert signal.strength is SignalStrength.NONE
    assert signal.is_actionable is False
