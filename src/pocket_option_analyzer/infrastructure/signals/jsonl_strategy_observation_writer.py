from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparison,
    StrategyObservation,
    StrategyObservationResolution,
    VisualPriceReferenceResult,
    VisualReferenceResolution,
    VisualReferenceValidation,
)
from pocket_option_analyzer.vision.models import CurrentVisualPriceExtraction


class JsonlStrategyObservationWriter:
    """Append-only persistence for passive, structured strategy evidence."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def write(self, observation: StrategyObservation) -> None:
        self._append(self._to_dict(observation))

    def write_resolution(self, resolution: StrategyObservationResolution) -> None:
        self._append(self._resolution_to_dict(resolution))

    def write_reference_validation(
        self,
        validation: VisualReferenceValidation,
    ) -> None:
        self._append(
            {
                "event_type": "reference_validation",
                "snapshot_id": validation.snapshot_id,
                "observed_at": validation.observed_at.isoformat(),
                "resolve_at": validation.resolve_at.isoformat(),
                "entry_reference": self._reference_to_dict(
                    validation.entry_reference,
                ),
                "entry_reference_diagnostic": self._reference_result_to_dict(
                    validation.entry_reference_result,
                ),
                "current_visual_price": self._current_visual_price_to_dict(
                    validation.current_visual_price,
                ),
                "movement": "unresolved",
            }
        )

    def write_reference_resolution(self, resolution: VisualReferenceResolution) -> None:
        self._append(
            {
                "event_type": "reference_resolution",
                "snapshot_id": resolution.snapshot_id,
                "observed_at": resolution.observed_at.isoformat(),
                "resolve_at": resolution.resolve_at.isoformat(),
                "resolved_at": resolution.resolved_at.isoformat(),
                "entry_reference": self._reference_to_dict(resolution.entry_reference),
                "exit_reference": self._reference_to_dict(resolution.exit_reference),
                "exit_current_visual_price": self._current_visual_price_to_dict(
                    resolution.exit_current_visual_price,
                ),
                "movement": resolution.movement.value,
                "diagnostic": resolution.diagnostic,
                "visual_price_comparison": self._visual_price_comparison_to_dict(
                    resolution.visual_price_comparison,
                ),
            }
        )

    def _append(self, payload: dict[str, Any]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_path.open("a", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
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
            "event_type": "observation",
            "observed_at": observation.observed_at.isoformat(),
            "snapshot_id": observation.candle_interval_started_at.isoformat(),
            "candle_interval_started_at": (
                observation.candle_interval_started_at.isoformat()
            ),
            "trend": observation.trend.value,
            "resolve_at": observation.resolve_at.isoformat(),
            "direction": (
                observation.direction.value
                if observation.direction is not None
                else None
            ),
            "entry_reference": JsonlStrategyObservationWriter._reference_to_dict(
                observation.entry_reference,
            ),
            "entry_reference_diagnostic": (
                JsonlStrategyObservationWriter._reference_result_to_dict(
                    observation.entry_reference_result,
                )
            ),
            "current_visual_price": (
                JsonlStrategyObservationWriter._current_visual_price_to_dict(
                    observation.current_visual_price,
                )
            ),
            "exit_reference": None,
            "outcome": observation.outcome.value,
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

    @staticmethod
    def _resolution_to_dict(
        resolution: StrategyObservationResolution,
    ) -> dict[str, Any]:
        return {
            "event_type": "resolution",
            "snapshot_id": resolution.snapshot_id,
            "observed_at": resolution.observed_at.isoformat(),
            "resolve_at": resolution.resolve_at.isoformat(),
            "resolved_at": resolution.resolved_at.isoformat(),
            "direction": resolution.direction.value,
            "entry_reference": JsonlStrategyObservationWriter._reference_to_dict(
                resolution.entry_reference,
            ),
            "exit_reference": JsonlStrategyObservationWriter._reference_to_dict(
                resolution.exit_reference,
            ),
            "exit_current_visual_price": (
                JsonlStrategyObservationWriter._current_visual_price_to_dict(
                    resolution.exit_current_visual_price,
                )
            ),
            "outcome": resolution.outcome.value,
            "visual_price_comparison": (
                JsonlStrategyObservationWriter._visual_price_comparison_to_dict(
                    resolution.visual_price_comparison,
                )
            ),
        }

    @staticmethod
    def _visual_price_comparison_to_dict(
        comparison: CurrentVisualPriceComparison | None,
    ) -> dict[str, Any] | None:
        if comparison is None:
            return None

        return {
            "status": comparison.status.value,
            "diagnostic": comparison.diagnostic.value,
            "entry_anchored_value": comparison.entry_anchored_value,
            "exit_anchored_value": comparison.exit_anchored_value,
            "delta": comparison.delta,
            "entry_price_y_in_chart_roi": (
                comparison.entry_price_y_in_chart_roi
            ),
            "exit_price_y_in_chart_roi": comparison.exit_price_y_in_chart_roi,
        }

    @staticmethod
    def _reference_result_to_dict(
        result: VisualPriceReferenceResult | None,
    ) -> dict[str, Any] | None:
        if result is None:
            return None

        return {
            "status": result.status.value,
            "anchor_count": result.anchor_count,
            "latest_candle_type": result.latest_candle_type,
            "latest_candidate_x": result.latest_candidate_x,
            "latest_candidate_y": result.latest_candidate_y,
            "close_roi_y": result.close_roi_y,
            "anchor_top_roi_y": result.anchor_top_roi_y,
            "anchor_bottom_roi_y": result.anchor_bottom_roi_y,
            "raw_normalized_close": result.raw_normalized_close,
        }

    @staticmethod
    def _current_visual_price_to_dict(
        extraction: CurrentVisualPriceExtraction | None,
    ) -> dict[str, Any] | None:
        if extraction is None:
            return None

        price = extraction.price
        return {
            "status": extraction.status.value,
            "candidate_count": extraction.candidate_count,
            "selected_x": extraction.selected_x,
            "selected_y": extraction.selected_y,
            "confidence": extraction.confidence,
            "diagnostic": extraction.diagnostic,
            "price": (
                {
                    "roi_y": price.roi_y,
                    "normalized_roi_y": price.normalized_roi_y,
                    "roi_width": price.roi_width,
                    "roi_height": price.roi_height,
                    "source": price.source,
                    "confidence": price.confidence,
                }
                if price is not None
                else None
            ),
        }

    @staticmethod
    def _reference_to_dict(reference: Any) -> dict[str, Any] | None:
        if reference is None:
            return None
        return {
            "value": reference.value,
            "normalized_close": reference.normalized_close,
            "anchor_shape": reference.anchor_shape,
            "source": reference.source,
        }
