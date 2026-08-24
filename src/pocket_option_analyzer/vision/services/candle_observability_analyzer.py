from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleGeometry,
    CandleObservability,
)


class CandleObservabilityAnalyzer:
    """Derive constant-time body boundary facts from existing geometry."""

    @staticmethod
    def analyze(
        geometry: CandleGeometry,
        roi_height: int,
    ) -> CandleObservability:
        return CandleObservability(
            roi_height=roi_height,
            body_top_y=geometry.body_top_y,
            body_bottom_y=geometry.body_bottom_y,
            body_touches_top=geometry.body_top_y == 0,
            body_touches_bottom=geometry.body_bottom_y == roi_height - 1,
        )
