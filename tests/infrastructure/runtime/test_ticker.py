from pocket_option_analyzer.infrastructure.runtime import Ticker


def test_ticker_creation() -> None:
    ticker = Ticker(target_fps=10)

    assert ticker.target_fps == 10
    assert ticker.frame_duration == 0.1


def test_ticker_reset() -> None:
    ticker = Ticker(target_fps=30)

    ticker.reset()

    assert ticker.target_fps == 30
