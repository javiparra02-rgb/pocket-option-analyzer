from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pocket_option_analyzer.application.strategy import StrategyObservation


class JsonlStrategyObservationWriter:
    """Append-only persistence for passive, structured strategy evidence."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def write(self, observation: StrategyObservation) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_path.open("a", encoding="utf-8") as stream:
            json.dump(self._to_dict(observation), stream, ensure_ascii=False)
            stream.write("\n")

    @staticmethod
    def _to_dict(observation: StrategyObservation) -> dict[str, Any]:
        def direction(audit: Any) -> dict[str, Any]:
            return {
                "passed_count": audit.passed_count,
                "total_count": audit.total_count,
                "conditions": {
                    result.condition.value: {
                        "passed": result.passed,
                        "failure_reason": result.failure_reason,
                    }
                    for result in audit.conditions
                },
                "blockers": list(audit.failures),
            }

        indicators = observation.indicators
        context = observation.visual_context
        diagnostics = observation.detection_diagnostics
        return {
            "observed_at": observation.observed_at.isoformat(),
            "snapshot_id": observation.candle_interval_started_at.isoformat(),
            "candle_interval_started_at": (
                observation.candle_interval_started_at.isoformat()
            ),
            "trend": observation.trend.value,
            "call": direction(observation.audit.call),
            "put": direction(observation.audit.put),
            "indicators": {
                "ema": {
                    "fast": indicators.ema.fast_value,
                    "slow": indicators.ema.slow_value,
                    "separation_candles": indicators.ema.separation_candles,
                },
                "rsi": indicators.rsi.value,
                "stochastic": {
                    "k": indicators.stochastic.k_value,
                    "d": indicators.stochastic.d_value,
                    "previous_k": indicators.stochastic.k_previous,
                    "previous_d": indicators.stochastic.d_previous,
                },
            },
            "visual_context": (
                {
                    "visible_candle_count": context.visible_candle_count,
                    "ohlc_candle_count": context.ohlc_candle_count,
                    "geometry_valid_count": context.geometry_valid_count,
                    "geometry_total_count": context.geometry_total_count,
                }
                if context is not None
                else None
            ),
            "detection_context": (
                {
                    "input_count": diagnostics.input_count,
                    "dimension_valid_count": diagnostics.dimension_valid_count,
                    "width_valid_count": diagnostics.width_valid_count,
                    "merged_count": diagnostics.merged_count,
                    "returned_count": diagnostics.returned_count,
                    "dominant_width": diagnostics.dominant_width,
                }
                if diagnostics is not None
                else None
            ),
        }

