from pocket_option_analyzer.vision.config import HSVConfig


def test_green_range():

    assert HSVConfig.GREEN_CANDLE.lower == (
        35,
        80,
        80,
    )


def test_red_range():

    assert HSVConfig.RED_CANDLE.upper == (
        15,
        255,
        255,
    )
