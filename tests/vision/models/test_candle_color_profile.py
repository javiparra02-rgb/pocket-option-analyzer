from pocket_option_analyzer.vision.models import (
    CandleColor,
    CandleColorProfile,
)


def test_green_red_profile() -> None:

    profile = CandleColorProfile.green_red()

    assert profile.bullish is CandleColor.GREEN
    assert profile.bearish is CandleColor.RED


def test_white_red_profile() -> None:

    profile = CandleColorProfile.white_red()

    assert profile.bullish is CandleColor.WHITE
    assert profile.bearish is CandleColor.RED