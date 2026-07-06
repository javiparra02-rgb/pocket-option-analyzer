from pocket_option_analyzer.vision.models import CandleCandidate
from pocket_option_analyzer.vision.services.candle_metrics_calculator import (
    CandleMetricsCalculator,
)


def test_calculate_returns_metrics():

    calculator = CandleMetricsCalculator()

    metrics = calculator.calculate(
        CandleCandidate(
            x=10,
            y=20,
            width=5,
            height=25,
            area=125,
        )
    )

    assert metrics.center_x == 12.5
    assert metrics.center_y == 32.5
    assert metrics.aspect_ratio == 5.0