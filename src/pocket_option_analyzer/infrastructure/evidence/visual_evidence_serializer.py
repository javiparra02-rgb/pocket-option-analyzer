from __future__ import annotations

from dataclasses import asdict
from math import ceil
from typing import Any

from pocket_option_analyzer.application.evidence import VisualFrameEvidence
from pocket_option_analyzer.application.strategy import VisualPriceReferenceResult
from pocket_option_analyzer.vision.models import (
    CandleCandidateTrace,
    CandleDetectionTrace,
    CandleFilterConfigurationTrace,
    CandleFilterDiagnostics,
    CandleMergeTrace,
    CandleObservability,
    CandleOverlayEvidenceTrace,
    CandleSeriesMembershipTrace,
    CandleType,
    ChartRegion,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceSemanticSearchTrace,
    FinalCandleTrace,
    MarketAnalysis,
)
from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceLabelAssociation,
    CurrentVisualPriceLineLabelPair,
    CurrentVisualPriceLocalGuideTrace,
)


class VisualEvidenceSerializer:
    """Explicit JSON serializer for already-computed visual evidence."""

    @classmethod
    def analysis_to_dict(cls, evidence: VisualFrameEvidence) -> dict[str, Any]:
        return {
            "market_analysis": cls._market_analysis_to_dict(
                evidence.market_analysis,
            ),
            "current_visual_price": cls._current_visual_price_to_dict(
                evidence.current_visual_price,
            ),
            "visual_price_reference_result": cls._reference_result_to_dict(
                evidence.visual_price_reference_result,
            ),
            "candle_detection_trace": cls._candle_trace_to_dict(
                evidence.candle_detection_trace,
            ),
            "current_visual_price_detection_trace": (
                cls._current_visual_price_trace_to_dict(
                    evidence.current_visual_price_detection_trace,
                )
            ),
        }

    @staticmethod
    def region_to_dict(region: ChartRegion | None) -> dict[str, int] | None:
        if region is None:
            return None
        return {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
            "right": region.right,
            "bottom": region.bottom,
        }

    @classmethod
    def _market_analysis_to_dict(
        cls,
        analysis: MarketAnalysis | None,
    ) -> dict[str, Any] | None:
        if analysis is None:
            return None
        return {
            "trend": analysis.trend.value,
            "series_candle_count": len(analysis.series),
            "chart_region": cls.region_to_dict(analysis.chart_region),
            "price_observation_region": cls.region_to_dict(
                analysis.price_observation_region,
            ),
            "detection_diagnostics": cls._filter_diagnostics_to_dict(
                analysis.detection_diagnostics,
            ),
        }

    @staticmethod
    def _filter_diagnostics_to_dict(
        diagnostics: CandleFilterDiagnostics | None,
    ) -> dict[str, Any] | None:
        if diagnostics is None:
            return None
        return {
            "input_count": diagnostics.input_count,
            "dimension_valid_count": diagnostics.dimension_valid_count,
            "width_valid_count": diagnostics.width_valid_count,
            "merged_count": diagnostics.merged_count,
            "returned_count": diagnostics.returned_count,
            "dominant_width": diagnostics.dominant_width,
            "rejected_by_dimensions": diagnostics.rejected_by_dimensions,
            "rejected_by_width": diagnostics.rejected_by_width,
            "merged_fragments": diagnostics.merged_fragments,
            "truncated_count": diagnostics.truncated_count,
        }

    @classmethod
    def _candle_trace_to_dict(
        cls,
        trace: CandleDetectionTrace | None,
    ) -> dict[str, Any] | None:
        if trace is None:
            return None
        final_candles = tuple(
            cls._final_candle_to_dict(candle) for candle in trace.final_candles
        )
        return {
            "candidates": [
                cls._candidate_trace_to_dict(candidate)
                for candidate in trace.candidates
            ],
            "merges": [cls._merge_to_dict(merge) for merge in trace.merges],
            "returned_candidate_ids": list(trace.returned_candidate_ids),
            "dominant_width": trace.dominant_width,
            "maximum_returned_candidates": trace.maximum_returned_candidates,
            "filter_configuration": cls._filter_configuration_to_dict(
                trace.filter_configuration,
            ),
            "series_membership": cls._series_membership_to_dict(
                trace.series_membership,
            ),
            "overlay_evidence": cls._overlay_evidence_to_dict(
                trace.overlay_evidence,
            ),
            "final_candles": list(final_candles),
            "latest": next(
                (candle for candle in final_candles if candle["is_latest"]),
                None,
            ),
            "anchors": sorted(
                (
                    candle
                    for candle in final_candles
                    if candle["is_anchor"]
                ),
                key=lambda candle: candle["anchor_index"],
            ),
        }

    @staticmethod
    def _series_membership_to_dict(
        membership: CandleSeriesMembershipTrace | None,
    ) -> dict[str, Any] | None:
        if membership is None:
            return None
        return {
            "status": membership.status.value,
            "evaluated_candidate_ids": list(
                membership.evaluated_candidate_ids,
            ),
            "member_candidate_ids": list(membership.member_candidate_ids),
            "excluded_candidates": [
                {
                    "candidate_id": exclusion.candidate_id,
                    "reason": exclusion.reason.value,
                    "horizontal_gap_px": exclusion.horizontal_gap_px,
                    "vertical_gap_px": exclusion.vertical_gap_px,
                    "diagnostic": exclusion.diagnostic,
                }
                for exclusion in membership.excluded_candidates
            ],
            "evaluated_gaps": [
                {
                    "left_candidate_id": gap.left_candidate_id,
                    "right_candidate_id": gap.right_candidate_id,
                    "horizontal_gap_px": gap.horizontal_gap_px,
                    "estimated_slot_count": gap.estimated_slot_count,
                    "horizontal_consistent": gap.horizontal_consistent,
                    "vertical_gap_px": gap.vertical_gap_px,
                    "vertical_continuity_limit_px": (
                        gap.vertical_continuity_limit_px
                    ),
                    "vertical_consistent": gap.vertical_consistent,
                }
                for gap in membership.evaluated_gaps
            ],
            "estimated_pitch_px": membership.estimated_pitch_px,
            "candidate_runs": [
                {
                    "run_id": run.run_id,
                    "candidate_ids": list(run.candidate_ids),
                    "support": run.support,
                    "selected": run.selected,
                    "separated_by_vertical_discontinuity": (
                        run.separated_by_vertical_discontinuity
                    ),
                }
                for run in membership.candidate_runs
            ],
            "selected_run_support": membership.selected_run_support,
            "latest_candidate_id": membership.latest_candidate_id,
            "diagnostic": membership.diagnostic,
            "extension_decisions": [
                {
                    "candidate_id": extension.candidate_id,
                    "core_candidate_ids": list(extension.core_candidate_ids),
                    "core_support": len(extension.core_candidate_ids),
                    "frozen_pitch_px": extension.frozen_pitch_px,
                    "frozen_vertical_median_gap_px": (
                        extension.frozen_vertical_median_gap_px
                    ),
                    "frozen_vertical_mad_px": extension.frozen_vertical_mad_px,
                    "frozen_body_height_scale_px": (
                        extension.frozen_body_height_scale_px
                    ),
                    "frozen_robust_allowance_px": (
                        extension.frozen_robust_allowance_px
                    ),
                    "frozen_body_allowance_px": (
                        extension.frozen_body_allowance_px
                    ),
                    "frozen_vertical_continuity_limit_px": (
                        extension.frozen_vertical_continuity_limit_px
                    ),
                    "candidate_vertical_gap_px": (
                        extension.candidate_vertical_gap_px
                    ),
                    "overlay_evidence_status": (
                        extension.overlay_evidence_status.value
                    ),
                    "decision": extension.decision.value,
                    "exclusion_reason": (
                        extension.exclusion_reason.value
                        if extension.exclusion_reason is not None
                        else None
                    ),
                }
                for extension in membership.extension_decisions
            ],
        }

    @staticmethod
    def _overlay_evidence_to_dict(
        trace: CandleOverlayEvidenceTrace | None,
    ) -> dict[str, Any] | None:
        if trace is None:
            return None
        return {
            "evaluated_candidate_ids": list(trace.evaluated_candidate_ids),
            "evidence": [
                {
                    "candidate_id": evidence.candidate_id,
                    "status": evidence.status.value,
                    "vertical_line_support_ratio": (
                        evidence.vertical_line_support_ratio
                    ),
                    "contact_gap_ratio": evidence.contact_gap_ratio,
                    "horizontal_alignment_ratio": (
                        evidence.horizontal_alignment_ratio
                    ),
                    "cap_height_to_width_ratio": (
                        evidence.cap_height_to_width_ratio
                    ),
                    "wickless": evidence.wickless,
                    "diagnostic": evidence.diagnostic,
                }
                for evidence in trace.evidence
            ],
        }

    @staticmethod
    def _candidate_trace_to_dict(
        candidate: CandleCandidateTrace,
    ) -> dict[str, Any]:
        return {
            "candidate_id": candidate.candidate_id,
            "x": candidate.x,
            "y": candidate.y,
            "width": candidate.width,
            "height": candidate.height,
            "area": candidate.area,
            "color": candidate.color.value,
            "decisions": [decision.value for decision in candidate.decisions],
            "dominant_width": candidate.dominant_width,
            "dimension_rejection_reasons": [
                reason.value for reason in candidate.dimension_rejection_reasons
            ],
            "width_decision_reason": (
                candidate.width_decision_reason.value
                if candidate.width_decision_reason is not None
                else None
            ),
            "merged_from": list(candidate.merged_from),
            "merged_into": candidate.merged_into,
        }

    @staticmethod
    def _merge_to_dict(merge: CandleMergeTrace) -> dict[str, Any]:
        return {
            "result_candidate_id": merge.result_candidate_id,
            "source_candidate_ids": list(merge.source_candidate_ids),
            "maximum_center_distance": merge.maximum_center_distance,
        }

    @staticmethod
    def _filter_configuration_to_dict(
        configuration: CandleFilterConfigurationTrace | None,
    ) -> dict[str, Any] | None:
        if configuration is None:
            return None
        return {
            "min_area": configuration.min_area,
            "min_width": configuration.min_width,
            "min_height": configuration.min_height,
            "max_width": configuration.max_width,
            "max_height": configuration.max_height,
            "min_relative_width": configuration.min_relative_width,
            "max_relative_width": configuration.max_relative_width,
            "width_bucket_size": configuration.width_bucket_size,
            "anchor_min_height_ratio": configuration.anchor_min_height_ratio,
            "same_column_center_ratio": configuration.same_column_center_ratio,
            "max_candidates": configuration.max_candidates,
        }

    @staticmethod
    def _final_candle_to_dict(candle: FinalCandleTrace) -> dict[str, Any]:
        return {
            "candidate_id": candle.candidate_id,
            "source_candidate_ids": list(candle.source_candidate_ids),
            "ordinal": candle.ordinal,
            "x": candle.x,
            "y": candle.y,
            "width": candle.width,
            "height": candle.height,
            "area": candle.area,
            "color": candle.color.value,
            "candle_type": candle.candle_type.value,
            "high_y": candle.high_y,
            "body_top_y": candle.body_top_y,
            "body_bottom_y": candle.body_bottom_y,
            "low_y": candle.low_y,
            "observability": VisualEvidenceSerializer._observability_to_dict(
                candle.observability,
                candle.candle_type,
            ),
            "is_latest": candle.is_latest,
            "is_anchor": candle.is_anchor,
            "anchor_index": candle.anchor_index,
            "anchor_exclusion_reason": (
                candle.anchor_exclusion_reason.value
                if candle.anchor_exclusion_reason is not None
                else None
            ),
        }

    @staticmethod
    def _observability_to_dict(
        observability: CandleObservability | None,
        candle_type: CandleType,
    ) -> dict[str, Any] | None:
        if observability is None:
            return None
        close_boundary = observability.close_boundary_for(candle_type)
        return {
            "roi_height": observability.roi_height,
            "body_top_y": observability.body_top_y,
            "body_bottom_y": observability.body_bottom_y,
            "body_touches_top": observability.body_touches_top,
            "body_touches_bottom": observability.body_touches_bottom,
            "close_boundary": (
                close_boundary.value if close_boundary is not None else None
            ),
            "fully_observable_close": observability.fully_observable_close_for(
                candle_type
            ),
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
    def _reference_result_to_dict(
        result: VisualPriceReferenceResult | None,
    ) -> dict[str, Any] | None:
        if result is None:
            return None
        reference = result.reference
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
            "reference": (
                {
                    "value": reference.value,
                    "normalized_close": reference.normalized_close,
                    "source": reference.source,
                    "anchor_shape": [
                        {
                            "candle_type": anchor[0],
                            "normalized_high": anchor[1],
                            "normalized_body_top": anchor[2],
                            "normalized_body_bottom": anchor[3],
                            "normalized_low": anchor[4],
                        }
                        for anchor in reference.anchor_shape
                    ],
                }
                if reference is not None
                else None
            ),
        }

    @staticmethod
    def _current_visual_price_trace_to_dict(
        trace: CurrentVisualPriceDetectionTrace | None,
    ) -> dict[str, Any] | None:
        if trace is None:
            return None
        counts = trace.rejection_counts
        return {
            **(
                {"independent_identity": asdict(trace.independent_identity)}
                if trace.independent_identity is not None
                else {}
            ),
            "status": trace.status.value,
            "image_width": trace.image_width,
            "image_height": trace.image_height,
            "effective_chart_right_x": trace.effective_chart_right_x,
            "effective_chart_right_source": trace.effective_chart_right_source,
            "band_start": trace.band_start,
            "band_end": trace.band_end,
            "band_width": trace.band_width,
            "safe_top": trace.safe_top,
            "safe_bottom": trace.safe_bottom,
            "masked_pixel_count": trace.masked_pixel_count,
            "decision_diagnostic": trace.decision_diagnostic,
            "semantic_search": VisualEvidenceSerializer._semantic_search_to_dict(
                trace.semantic_search
            ),
            "rejection_counts": {
                "rows_without_mask_pixels": counts.rows_without_mask_pixels,
                "rows_with_mask_pixels": counts.rows_with_mask_pixels,
                "rejected_by_coverage": counts.rejected_by_coverage,
                "rejected_by_span": counts.rejected_by_span,
                "rejected_by_right_edge_gap": (counts.rejected_by_right_edge_gap),
                "qualifying_rows": counts.qualifying_rows,
                "candidate_groups": counts.candidate_groups,
                "rejected_by_group_height": counts.rejected_by_group_height,
                "line_evidence_rows": counts.line_evidence_rows,
                "rejected_by_label_support": counts.rejected_by_label_support,
            },
            "row_evaluations": [
                {
                    "row_y": row.row_y,
                    "masked_pixels": row.masked_pixels,
                    "coverage": row.coverage,
                    "span": row.span,
                    "left_x": row.left_x,
                    "right_x": row.right_x,
                    "right_edge_gap": row.right_edge_gap,
                    "longest_run_pixels": row.longest_run_pixels,
                    "longest_run_ratio": row.longest_run_ratio,
                    "longest_run_start_x": row.longest_run_start_x,
                    "longest_run_end_x": row.longest_run_end_x,
                    "component_count": row.component_count,
                    "line_run_pixels": row.line_run_pixels,
                    "line_run_span_pixels": row.line_run_span_pixels,
                    "line_run_span_ratio": row.line_run_span_ratio,
                    "line_run_start_x": row.line_run_start_x,
                    "line_run_end_x": row.line_run_end_x,
                    "line_run_continuity": row.line_run_continuity,
                    "pass_coverage": row.pass_coverage,
                    "pass_span": row.pass_span,
                    "pass_edge": row.pass_edge,
                    "line_evidence": row.line_evidence,
                    "label_support": row.label_support,
                    "qualified": row.qualified,
                    "local_guide": VisualEvidenceSerializer._local_guide_to_dict(
                        row.local_guide
                    ),
                    "rejection_reasons": [
                        reason.value for reason in row.rejection_reasons
                    ],
                    "label_support_trace": (
                        {
                            "window_start_y": label.window_start_y,
                            "window_end_y": label.window_end_y,
                            "zone_start_x": label.zone_start_x,
                            "zone_end_x": label.zone_end_x,
                            "support_pixels": label.support_pixels,
                            "support_row_count": label.support_row_count,
                            "evaluated_row_count": label.evaluated_row_count,
                            "support_row_ratio": label.support_row_ratio,
                            "support_density": label.support_density,
                            "supported": label.supported,
                            "diagnostic": label.diagnostic,
                        }
                        if (label := row.label_support_trace) is not None
                        else None
                    ),
                }
                for row in trace.row_evaluations
            ],
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "x": candidate.x,
                    "y": candidate.y,
                    "row_start": candidate.row_start,
                    "row_end": candidate.row_end,
                    "coverage": candidate.coverage,
                    "span": candidate.span,
                    "right_edge_gap": candidate.right_edge_gap,
                    "score": candidate.score,
                    "selected": candidate.selected,
                }
                for candidate in trace.candidates
            ],
        }

    @staticmethod
    def _semantic_search_to_dict(
        trace: CurrentVisualPriceSemanticSearchTrace | None,
    ) -> dict[str, Any] | None:
        if trace is None:
            return None
        return {
            "mode": trace.mode.value,
            "qualification_contract": trace.qualification_contract,
            "line_label_pairs": [
                VisualEvidenceSerializer._line_label_pair_to_dict(pair)
                for pair in trace.line_label_pairs
            ],
            "label_associations": [
                VisualEvidenceSerializer._label_association_to_dict(association)
                for association in trace.label_associations
            ],
            "plan_status": trace.plan_status.value,
            "plan_reason": trace.plan_reason.value,
            "total_proposed_window_count": trace.total_proposed_window_count,
            "evaluated_window_count": trace.evaluated_window_count,
            "full_window_set_sha256": trace.full_window_set_sha256,
            "resolution_status": trace.resolution_status.value,
            "resolution_reason": trace.resolution_reason.value,
            "selected_group_id": trace.selected_group_id,
            "windows": [
                {
                    "window_id": window.window_id,
                    "start_x": window.start_x,
                    "end_x": window.end_x,
                    "width": window.width,
                    "origin": window.origin.value,
                    "line_hypothesis_ids": list(window.line_hypothesis_ids),
                    "label_component_ids": list(window.label_component_ids),
                }
                for window in trace.windows
            ],
            "window_evaluations": [
                {
                    "window_id": evaluation.window_id,
                    "decision_diagnostic": evaluation.decision_diagnostic,
                    "candidate_count": evaluation.candidate_count,
                    "semantic_candidate_ids": list(evaluation.semantic_candidate_ids),
                    "local_guides": [
                        VisualEvidenceSerializer._local_guide_to_dict(guide)
                        for guide in evaluation.local_guides
                    ],
                }
                for evaluation in trace.window_evaluations
            ],
            "semantic_groups": [
                {
                    "group_id": group.group_id,
                    "semantic_candidate_ids": list(group.semantic_candidate_ids),
                    "line_hypothesis_ids": list(group.line_hypothesis_ids),
                    "window_ids": list(group.window_ids),
                    "representative_window_id": (group.representative_window_id),
                }
                for group in trace.semantic_groups
            ],
        }

    @staticmethod
    def _local_guide_to_dict(
        guide: CurrentVisualPriceLocalGuideTrace | None,
    ) -> dict[str, Any] | None:
        if guide is None:
            return None
        return {
            "contract_version": guide.contract_version,
            "hypothesis_id": guide.hypothesis_id,
            "row_y": guide.row_y,
            "window_width": guide.window_width,
            "minimum_span": guide.minimum_span,
            "maximum_gap": guide.maximum_gap,
            "zone_width": guide.zone_width,
            "zone_start_x": guide.zone_start_x,
            "label_ingress_x": guide.label_ingress_x,
            "selected_run_id": (
                f"{guide.hypothesis_id}:row_{guide.row_y}:"
                f"{guide.selected_start_x}:{guide.selected_end_x}"
                if guide.selected_start_x is not None else None
            ),
            "selected_start_x": guide.selected_start_x,
            "selected_end_x": guide.selected_end_x,
            "supported_pixels": guide.supported_pixels,
            "span_pixels": guide.span_pixels,
            "terminal_gap": guide.terminal_gap,
            "internal_gaps": list(guide.internal_gaps),
            "continuity": guide.continuity,
            "span_score": guide.span_score,
            "qualified": guide.qualified,
            "rejection_reasons": list(guide.rejection_reasons),
        }

    @staticmethod
    def _line_label_pair_to_dict(pair: CurrentVisualPriceLineLabelPair) -> dict[str, Any]:
        component = pair.component
        return {
            "pair_id": pair.pair_id,
            "line_hypothesis_id": pair.hypothesis.hypothesis_id,
            "component_id": component.component_id,
            "window_id": pair.window_id,
            "window_start_x": pair.window_start_x,
            "pair_edge": pair.pair_edge,
            "window_width": pair.window_width,
            "component": {
                "x": component.x, "y": component.y,
                "width": component.width, "height": component.height,
                "area": component.area,
            },
            "runs": [
                {"row_y": r.row_y, "start_x": r.start_x, "end_x": r.end_x}
                for r in pair.hypothesis.runs
            ],
        }

    @staticmethod
    def _label_association_to_dict(a: CurrentVisualPriceLabelAssociation) -> dict[str, Any]:
        pairs = {p.pair_id: p for p in a.pairs}
        return {
            "hypothesis_id": a.hypothesis_id,
            "status": a.status,
            "input_pair_ids": list(pairs),
            "pair_decisions": [
                {
                    "pair_id": p.pair_id,
                    "horizontal_distance": p.component.x - max(r.end_x for r in p.hypothesis.runs),
                    "maximum_gap": ceil(p.window_width * a.max_line_gap_ratio),
                    "eligible": p.pair_id in a.eligible_pair_ids,
                    "reason": "endpoint_reached" if p.pair_id in a.eligible_pair_ids else "component_beyond_endpoint_gap",
                }
                for p in a.pairs
            ],
            "groups": [
                {
                    "group_id": f"{a.hypothesis_id}:label_group_{index:03d}",
                    "pair_ids": list(group),
                    "component_ids": sorted({pairs[i].component.component_id for i in group}),
                    "envelope": {
                        "start_x": min(pairs[i].component.x for i in group),
                        "end_x": max(pairs[i].component.end_x for i in group),
                        "start_y": min(pairs[i].component.y for i in group),
                        "end_y": max(pairs[i].component.end_y for i in group),
                    },
                    "admissible": group in a.admissible_groups,
                    "reason": "covers_line_band" if group in a.admissible_groups else "does_not_cover_line_band",
                }
                for index, group in enumerate(a.component_groups)
            ],
            "label_ingress_x": a.label_ingress_x,
            "canonical_window_id": a.canonical_window.window_id if a.canonical_window else None,
            "canonical_edge": a.canonical_window.end_x if a.canonical_window else None,
            "canonical_window_width": a.canonical_window.width if a.canonical_window else None,
        }
