from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleMetrics,
)


class CandleMetricsCalculator:
    """
    Calcula métricas geométricas de una vela detectada.
    """

    def calculate(
        self,
        candle: CandleCandidate,
    ) -> CandleMetrics:

        return CandleMetrics(
            x=candle.x,
            y=candle.y,
            width=candle.width,
            height=candle.height,
            area=candle.area,
            center_x=candle.x + candle.width / 2,
            center_y=candle.y + candle.height / 2,
            aspect_ratio=candle.height / candle.width,
        )