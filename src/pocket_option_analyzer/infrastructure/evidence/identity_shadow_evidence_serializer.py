from __future__ import annotations

import hashlib
import json
from typing import Any

from pocket_option_analyzer.application.evidence import (
    IdentityShadowFrameEvidence,
)
from pocket_option_analyzer.application.market import (
    BootstrapConfirmationEvaluation,
    CurrentCandleIdentityTrace,
    CurrentCandleMissingEvidence,
    CurrentCandleSequenceMatchMetrics,
    TerminalSeedEvaluation,
    TerminalSlotRegion,
    TrackingTerminalEvaluation,
    TrustedRolloverEvaluation,
)
from pocket_option_analyzer.vision.models import (
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    FinalCandleTrace,
)


class IdentityShadowEvidenceSerializer:
    """Explicit stable JSON projection for identity calibration/replay."""

    SCHEMA_VERSION = 1
    DECISION_TELEMETRY_SCHEMA_VERSION = 1

    @staticmethod
    def payload_sha256(payload: dict[str, Any]) -> str:
        """Hash one JSON-native record using its canonical representation."""

        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def frame_to_dict(
        cls,
        evidence: IdentityShadowFrameEvidence,
        *,
        sequence_number: int,
        previous_trace: CurrentCandleIdentityTrace | None,
        previous_frame: dict[str, Any] | None,
    ) -> dict[str, Any]:
        trace = evidence.resolution.trace
        result = evidence.resolution.result
        context = evidence.frame_context
        membership = context.membership
        overlay_by_id = (
            context.overlay_evidence.by_candidate_id()
            if context.overlay_evidence is not None
            else {}
        )
        exclusions = (
            {
                item.candidate_id: item.reason.value
                for item in membership.excluded_candidates
            }
            if membership is not None
            else {}
        )
        member_ids = set(membership.member_candidate_ids) if membership else set()
        candles = context.final_candles
        reference = evidence.visual_price_reference_result
        return {
            "identity_shadow_schema_version": cls.SCHEMA_VERSION,
            "sequence_number": sequence_number,
            "frame_key": cls.identity_frame_key(evidence),
            "visual_frame_key": cls.visual_frame_key(evidence),
            "frame_id": evidence.frame_id,
            "wall_timestamp": evidence.frame_timestamp.isoformat(),
            "monotonic_timestamp": evidence.monotonic_timestamp,
            "session_key": evidence.session_key,
            "source_key": cls.opaque_source_key(evidence.source_key),
            "roi": {
                "previous": (
                    previous_frame.get("roi", {}).get("current")
                    if previous_frame is not None
                    else None
                ),
                "current": {
                    "width": evidence.roi_width,
                    "height": evidence.roi_height,
                    "capture_region": cls._region(evidence.chart_region),
                },
            },
            "continuity_generation": trace.continuity_generation,
            "lifecycle_state": trace.internal_state.value,
            "identity": {
                "status": result.status.value,
                "source": result.source.value,
                "candidate_id": result.candidate_id,
                "diagnostics": list(result.diagnostics),
                "evidence": cls._identity_evidence(result.evidence),
            },
            "legacy_latest_candidate_id": trace.legacy_latest_candidate_id,
            "membership": {
                "status": membership.status.value if membership else None,
                "estimated_pitch_px": (
                    membership.estimated_pitch_px if membership else None
                ),
                "member_candidate_ids": (
                    list(membership.member_candidate_ids) if membership else []
                ),
                "excluded_candidates": (
                    [
                        {
                            "candidate_id": item.candidate_id,
                            "reason": item.reason.value,
                            "diagnostic": item.diagnostic,
                        }
                        for item in membership.excluded_candidates
                    ]
                    if membership
                    else []
                ),
            },
            "terminal_region": {
                "previous": cls._terminal_region(
                    previous_trace.terminal_region if previous_trace else None
                ),
                "current": cls._terminal_region(trace.terminal_region),
            },
            "identity_decision_telemetry_schema_version": (
                cls.DECISION_TELEMETRY_SCHEMA_VERSION
            ),
            "trusted_rollover_evaluation": cls._trusted_rollover_evaluation(
                trace.trusted_rollover_evaluation
            ),
            "terminal_seed_evaluation": cls._terminal_seed_evaluation(
                trace.terminal_seed_evaluation
            ),
            "bootstrap_confirmation_evaluation": (
                cls._bootstrap_confirmation_evaluation(
                    trace.bootstrap_confirmation_evaluation
                )
            ),
            "tracking_terminal_evaluation": cls._tracking_terminal_evaluation(
                trace.tracking_terminal_evaluation
            ),
            "sequence_match": cls._sequence_match(trace),
            "rollover": {
                "suspected": trace.rollover_suspected,
                "confirmed": trace.rollover_confirmed,
            },
            "chosen_candidate_id": trace.chosen_candidate_id,
            "missing_evidence": cls._missing_evidence(trace),
            "reset_reason": (
                trace.reset_reason.value if trace.reset_reason is not None else None
            ),
            "expiry": {
                "evidence_consistent": trace.expiry_evidence_consistent,
                "vertical_line_x": trace.expiry_vertical_line_x,
                "vertical_line_start_y": trace.expiry_vertical_line_start_y,
                "vertical_line_end_y": trace.expiry_vertical_line_end_y,
                "vertical_line_conflict": trace.expiry_vertical_line_conflict,
                "conflicting_lines": cls._conflicting_expiry_lines(
                    tuple(overlay_by_id.values())
                ),
            },
            "candles": [
                cls._candle(
                    candle,
                    included=candle.candidate_id in member_ids,
                    exclusion_reason=exclusions.get(candle.candidate_id),
                    overlay=overlay_by_id.get(candle.candidate_id),
                )
                for candle in candles
            ],
            "visual_price_reference": (
                {
                    "status": reference.status.value,
                    "current_close_not_observable": (
                        reference.status.value == "current_close_not_observable"
                    ),
                }
                if reference is not None
                else None
            ),
        }

    @staticmethod
    def identity_frame_key(evidence: IdentityShadowFrameEvidence) -> str:
        session_digest = hashlib.sha256(
            evidence.session_key.encode("utf-8")
        ).hexdigest()[:12]
        timestamp = evidence.frame_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        return (
            f"identity_{session_digest}_frame_{evidence.frame_id:08d}_"
            f"{timestamp}"
        )

    @staticmethod
    def visual_frame_key(evidence: IdentityShadowFrameEvidence) -> str:
        timestamp = evidence.frame_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        return f"frame_{evidence.frame_id:08d}_{timestamp}"

    @staticmethod
    def opaque_source_key(source_key: str) -> str:
        digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _region(region: Any) -> dict[str, int] | None:
        if region is None:
            return None
        return {
            "left": int(region.x),
            "top": int(region.y),
            "width": int(region.width),
            "height": int(region.height),
        }

    @staticmethod
    def _terminal_region(region: TerminalSlotRegion | None) -> dict[str, Any] | None:
        if region is None:
            return None
        return {
            "center_x_roi": region.center_x_roi,
            "lower_x_roi": region.lower_x_roi,
            "upper_x_roi": region.upper_x_roi,
            "normalized_center_x": region.normalized_center_x,
            "estimated_pitch_px": region.estimated_pitch_px,
            "continuity_generation": region.continuity_generation,
            "learned_from_frame_ids": list(region.learned_from_frame_ids),
        }

    @staticmethod
    def _identity_evidence(value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        return {
            "matched_historical_member_count": (
                value.matched_historical_member_count
            ),
            "type_match_ratio": value.type_match_ratio,
            "terminal_candidate_ids": list(value.terminal_candidate_ids),
            "sufficient": value.sufficient,
        }

    @staticmethod
    def _trusted_rollover_evaluation(
        value: TrustedRolloverEvaluation,
    ) -> dict[str, Any]:
        return {
            "status": value.status.value,
            "rejection_reason": (
                value.rejection_reason.value
                if value.rejection_reason is not None
                else None
            ),
            "match_status": (
                value.match_status.value if value.match_status is not None else None
            ),
            "selected_hypothesis": (
                value.selected_hypothesis.value
                if value.selected_hypothesis is not None
                else None
            ),
            "rollover_qualifies": value.rollover_qualifies,
            "support": {
                "actual": value.support_actual,
                "minimum": value.support_minimum,
                "pass": value.support_pass,
            },
            "type_ratio": {
                "actual": value.type_ratio_actual,
                "minimum": value.type_ratio_minimum,
                "pass": value.type_ratio_pass,
            },
            "residual": {
                "actual_px": value.residual_actual_px,
                "maximum_px": value.residual_maximum_px,
                "pass": value.residual_pass,
            },
            "previous_member_count": value.previous_member_count,
            "current_member_count": value.current_member_count,
            "unmatched_previous_ids": list(value.unmatched_previous_ids),
            "unmatched_current_ids": list(value.unmatched_current_ids),
            "expected_previous_leftmost_id": (
                value.expected_previous_leftmost_id
            ),
            "expected_current_rightmost_id": value.expected_current_rightmost_id,
            "previous_boundary_compatible": value.previous_boundary_compatible,
            "current_boundary_compatible": value.current_boundary_compatible,
            "temporal_rollover_trusted": value.temporal_rollover_trusted,
        }

    @staticmethod
    def _terminal_seed_evaluation(
        value: TerminalSeedEvaluation,
    ) -> dict[str, Any]:
        return {
            "status": value.status.value,
            "candidate_id": value.candidate_id,
            "provenance": value.provenance.value,
            "is_unmatched_current": value.is_unmatched_current,
            "is_current_rightmost": value.is_current_rightmost,
            "membership_included": value.membership_included,
            "geometry_valid": value.geometry_valid,
            "close_observable": value.close_observable,
            "overlay_status": (
                value.overlay_status.value if value.overlay_status is not None else None
            ),
            "diagnostic": value.diagnostic,
        }

    @classmethod
    def _bootstrap_confirmation_evaluation(
        cls,
        value: BootstrapConfirmationEvaluation,
    ) -> dict[str, Any]:
        return {
            "evaluated": value.evaluated,
            "accepted": value.accepted,
            "rejection_reason": (
                value.rejection_reason.value
                if value.rejection_reason is not None
                else None
            ),
            "pending_before": value.pending_before,
            "pending_after": value.pending_after,
            "lifecycle_before": (
                value.lifecycle_before.value
                if value.lifecycle_before is not None
                else None
            ),
            "lifecycle_after": (
                value.lifecycle_after.value
                if value.lifecycle_after is not None
                else None
            ),
            "selected_stable": value.selected_stable,
            "provisional_region": cls._terminal_region(value.provisional_region),
            "candidates_in_region": list(value.candidates_in_region),
            "candidate_count": value.candidate_count,
            "overlay_conflict": value.overlay_conflict,
            "resulting_status": (
                value.resulting_status.value
                if value.resulting_status is not None
                else None
            ),
        }

    @classmethod
    def _tracking_terminal_evaluation(
        cls,
        value: TrackingTerminalEvaluation,
    ) -> dict[str, Any]:
        return {
            "evaluated": value.evaluated,
            "region_before": cls._terminal_region(value.region_before),
            "region_after": cls._terminal_region(value.region_after),
            "selected_hypothesis": (
                value.selected_hypothesis.value
                if value.selected_hypothesis is not None
                else None
            ),
            "candidates_in_region": list(value.candidates_in_region),
            "rollover_terminal_status": value.rollover_terminal_status.value,
            "candidate_provenance": value.candidate_provenance.value,
            "competitor_ids": list(value.competitor_ids),
            "overlay_conflict": value.overlay_conflict,
            "missing_evidence": cls._missing_evidence_value(
                value.missing_evidence
            ),
            "resulting_status": (
                value.resulting_status.value
                if value.resulting_status is not None
                else None
            ),
            "region_moved": value.region_moved,
            "decision_reason": value.decision_reason.value,
        }

    @classmethod
    def _sequence_match(
        cls,
        trace: CurrentCandleIdentityTrace,
    ) -> dict[str, Any] | None:
        value = trace.sequence_match
        if value is None:
            return None
        return {
            "status": value.status.value,
            "selected_hypothesis": (
                value.selected_hypothesis.value
                if value.selected_hypothesis is not None
                else None
            ),
            "stable": cls._match_metrics(value.stable),
            "rollover": cls._match_metrics(value.rollover),
            "diagnostics": list(value.diagnostics),
        }

    @staticmethod
    def _match_metrics(
        value: CurrentCandleSequenceMatchMetrics,
    ) -> dict[str, Any]:
        return {
            "hypothesis": value.hypothesis.value,
            "estimated_translation_px": value.estimated_translation_px,
            "translation_in_pitch_units": value.translation_in_pitch_units,
            "matched_member_count": value.matched_member_count,
            "matched_historical_member_count": (
                value.matched_historical_member_count
            ),
            "matched_type_count": value.matched_type_count,
            "type_match_ratio": value.type_match_ratio,
            "median_residual_px": value.median_residual_px,
            "maximum_residual_px": value.maximum_residual_px,
            "previous_candidate_ids": list(value.previous_candidate_ids),
            "current_candidate_ids": list(value.current_candidate_ids),
            "unmatched_previous_candidate_ids": list(
                value.unmatched_previous_candidate_ids
            ),
            "unmatched_current_candidate_ids": list(
                value.unmatched_current_candidate_ids
            ),
            "qualifies": value.qualifies,
        }

    @staticmethod
    def _missing_evidence(
        trace: CurrentCandleIdentityTrace,
    ) -> dict[str, Any] | None:
        return IdentityShadowEvidenceSerializer._missing_evidence_value(
            trace.missing_evidence
        )

    @staticmethod
    def _missing_evidence_value(
        value: CurrentCandleMissingEvidence | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return {
            "terminal_region_valid": value.terminal_region_valid,
            "terminal_member_absent": value.terminal_member_absent,
            "previous_slot_candidate_id": value.previous_slot_candidate_id,
            "previous_slot_fully_observable": (
                value.previous_slot_fully_observable
            ),
            "previous_slot_distance_in_pitch_units": (
                value.previous_slot_distance_in_pitch_units
            ),
            "candle_like_competitor_ids": list(
                value.candle_like_competitor_ids
            ),
            "sufficient": value.sufficient,
        }

    @staticmethod
    def _candle(
        candle: FinalCandleTrace,
        *,
        included: bool,
        exclusion_reason: str | None,
        overlay: CandleOverlayEvidence | None,
    ) -> dict[str, Any]:
        observability = candle.observability
        return {
            "candidate_id": candle.candidate_id,
            "center_x_roi": candle.x + candle.width / 2,
            "width": candle.width,
            "candle_type": candle.candle_type.value,
            "membership_included": included,
            "membership_exclusion_reason": exclusion_reason,
            "observability": (
                {
                    "roi_height": observability.roi_height,
                    "body_top_y": observability.body_top_y,
                    "body_bottom_y": observability.body_bottom_y,
                    "body_touches_top": observability.body_touches_top,
                    "body_touches_bottom": observability.body_touches_bottom,
                    "close_observable": (
                        observability.fully_observable_close_for(
                            candle.candle_type
                        )
                    ),
                }
                if observability is not None
                else None
            ),
            "expiry_overlay": (
                {
                    "status": overlay.status.value,
                    "vertical_line_x": overlay.vertical_line_x,
                    "vertical_line_start_y": overlay.vertical_line_start_y,
                    "vertical_line_end_y": overlay.vertical_line_end_y,
                }
                if overlay is not None
                else None
            ),
        }

    @staticmethod
    def _conflicting_expiry_lines(
        evidence: tuple[CandleOverlayEvidence, ...],
    ) -> list[dict[str, int | str]]:
        lines: list[dict[str, int | str]] = []
        for item in evidence:
            if (
                item.status is not CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
                or item.vertical_line_x is None
            ):
                continue
            assert item.vertical_line_start_y is not None
            assert item.vertical_line_end_y is not None
            lines.append(
                {
                    "candidate_id": item.candidate_id,
                    "vertical_line_x": item.vertical_line_x,
                    "vertical_line_start_y": item.vertical_line_start_y,
                    "vertical_line_end_y": item.vertical_line_end_y,
                }
            )
        return lines if len(lines) > 1 else []
