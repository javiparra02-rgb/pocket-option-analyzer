from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from pocket_option_analyzer.vision.models.candle_detection_trace import (
    FinalCandleTrace,
)

from .current_candle_identity import (
    CurrentCandleIdentityConfig,
    CurrentCandleMatchStatus,
    CurrentCandleSequenceMatch,
    CurrentCandleSequenceMatchMetrics,
    CurrentCandleTranslationHypothesis,
    candle_center_x,
)


@dataclass(frozen=True, slots=True)
class _MatchedPair:
    previous_index: int
    current_index: int
    translation_px: float
    residual_px: float


class CurrentCandleIdentityMatcher:
    """Pure order-preserving matcher for stable and one-slot rollover motion."""

    def __init__(self, config: CurrentCandleIdentityConfig | None = None) -> None:
        self._config = config or CurrentCandleIdentityConfig()

    @property
    def config(self) -> CurrentCandleIdentityConfig:
        """Expose the immutable effective provisional configuration."""

        return self._config

    def match(
        self,
        *,
        previous: tuple[FinalCandleTrace, ...],
        current: tuple[FinalCandleTrace, ...],
        estimated_pitch_px: float,
    ) -> CurrentCandleSequenceMatch:
        """Evaluate stable and rollover hypotheses without using frame-local IDs."""

        if estimated_pitch_px <= 0:
            raise ValueError("estimated_pitch_px debe ser positivo.")
        self._validate_sequence(previous, "previous")
        self._validate_sequence(current, "current")

        stable = self._evaluate(
            hypothesis=CurrentCandleTranslationHypothesis.STABLE,
            previous=previous,
            current=current,
            estimated_pitch_px=estimated_pitch_px,
        )
        rollover = self._evaluate(
            hypothesis=CurrentCandleTranslationHypothesis.ROLLOVER,
            previous=previous,
            current=current,
            estimated_pitch_px=estimated_pitch_px,
        )
        qualifying = tuple(item for item in (stable, rollover) if item.qualifies)
        if not qualifying:
            return CurrentCandleSequenceMatch(
                status=CurrentCandleMatchStatus.UNAVAILABLE,
                selected_hypothesis=None,
                stable=stable,
                rollover=rollover,
                diagnostics=("no_translation_hypothesis_qualified",),
            )
        if len(qualifying) == 1:
            selected = qualifying[0]
            return CurrentCandleSequenceMatch(
                status=CurrentCandleMatchStatus.SELECTED,
                selected_hypothesis=selected.hypothesis,
                stable=stable,
                rollover=rollover,
                diagnostics=(f"selected_{selected.hypothesis.value}",),
            )
        distinct_selection = self._select_distinct_hypothesis(
            stable,
            rollover,
            estimated_pitch_px=estimated_pitch_px,
        )
        if distinct_selection is None:
            return CurrentCandleSequenceMatch(
                status=CurrentCandleMatchStatus.AMBIGUOUS,
                selected_hypothesis=None,
                stable=stable,
                rollover=rollover,
                diagnostics=("translation_hypotheses_equivalent",),
            )
        return CurrentCandleSequenceMatch(
            status=CurrentCandleMatchStatus.SELECTED,
            selected_hypothesis=distinct_selection.hypothesis,
            stable=stable,
            rollover=rollover,
            diagnostics=(
                f"selected_{distinct_selection.hypothesis.value}_by_evidence",
            ),
        )

    def _evaluate(
        self,
        *,
        hypothesis: CurrentCandleTranslationHypothesis,
        previous: tuple[FinalCandleTrace, ...],
        current: tuple[FinalCandleTrace, ...],
        estimated_pitch_px: float,
    ) -> CurrentCandleSequenceMatchMetrics:
        expected_translation = (
            0.0
            if hypothesis is CurrentCandleTranslationHypothesis.STABLE
            else -estimated_pitch_px
        )
        maximum_residual = (
            estimated_pitch_px
            * self._config.maximum_match_residual_pitch_ratio
        )
        pairs = self._ordered_pairs(
            previous=previous,
            current=current,
            expected_translation_px=expected_translation,
            maximum_residual_px=maximum_residual,
        )
        matched_previous = {pair.previous_index for pair in pairs}
        matched_current = {pair.current_index for pair in pairs}
        historical_pairs = tuple(
            pair
            for pair in pairs
            if pair.previous_index < len(previous) - 1
            and pair.current_index < len(current) - 1
        )
        matched_type_count = sum(
            previous[pair.previous_index].candle_type
            is current[pair.current_index].candle_type
            for pair in historical_pairs
        )
        historical_count = len(historical_pairs)
        type_ratio = (
            matched_type_count / historical_count if historical_count else 0.0
        )
        translations = tuple(pair.translation_px for pair in pairs)
        residuals = tuple(pair.residual_px for pair in pairs)
        qualifies = (
            historical_count >= self._config.minimum_historical_matches
            and type_ratio >= self._config.minimum_type_match_ratio
            and bool(residuals)
            and max(residuals) <= maximum_residual
        )
        return CurrentCandleSequenceMatchMetrics(
            hypothesis=hypothesis,
            estimated_translation_px=(median(translations) if translations else None),
            translation_in_pitch_units=(
                median(translations) / estimated_pitch_px if translations else None
            ),
            matched_member_count=len(pairs),
            matched_historical_member_count=historical_count,
            matched_type_count=matched_type_count,
            type_match_ratio=type_ratio,
            median_residual_px=median(residuals) if residuals else None,
            maximum_residual_px=max(residuals) if residuals else None,
            previous_candidate_ids=tuple(
                previous[pair.previous_index].candidate_id for pair in pairs
            ),
            current_candidate_ids=tuple(
                current[pair.current_index].candidate_id for pair in pairs
            ),
            unmatched_previous_candidate_ids=tuple(
                candle.candidate_id
                for index, candle in enumerate(previous)
                if index not in matched_previous
            ),
            unmatched_current_candidate_ids=tuple(
                candle.candidate_id
                for index, candle in enumerate(current)
                if index not in matched_current
            ),
            qualifies=qualifies,
        )

    @staticmethod
    def _ordered_pairs(
        *,
        previous: tuple[FinalCandleTrace, ...],
        current: tuple[FinalCandleTrace, ...],
        expected_translation_px: float,
        maximum_residual_px: float,
    ) -> tuple[_MatchedPair, ...]:
        pairs: list[_MatchedPair] = []
        current_start = 0
        for previous_index, previous_candle in enumerate(previous):
            expected_center = candle_center_x(previous_candle) + expected_translation_px
            eligible = tuple(
                (current_index, abs(candle_center_x(current_candle) - expected_center))
                for current_index, current_candle in enumerate(
                    current[current_start:],
                    start=current_start,
                )
                if abs(candle_center_x(current_candle) - expected_center)
                <= maximum_residual_px
            )
            if not eligible:
                continue
            current_index, residual = min(eligible, key=lambda item: (item[1], item[0]))
            translation = (
                candle_center_x(current[current_index])
                - candle_center_x(previous_candle)
            )
            pairs.append(
                _MatchedPair(
                    previous_index=previous_index,
                    current_index=current_index,
                    translation_px=translation,
                    residual_px=residual,
                )
            )
            current_start = current_index + 1
        return tuple(pairs)

    def _select_distinct_hypothesis(
        self,
        stable: CurrentCandleSequenceMatchMetrics,
        rollover: CurrentCandleSequenceMatchMetrics,
        *,
        estimated_pitch_px: float,
    ) -> CurrentCandleSequenceMatchMetrics | None:
        type_difference = abs(stable.type_match_ratio - rollover.type_match_ratio)
        if type_difference > self._config.hypothesis_type_ratio_margin:
            return max((stable, rollover), key=lambda item: item.type_match_ratio)
        stable_residual = stable.median_residual_px
        rollover_residual = rollover.median_residual_px
        if stable_residual is None or rollover_residual is None:
            return None
        residual_margin = (
            self._config.hypothesis_residual_margin_pitch_ratio
            * estimated_pitch_px
        )
        if abs(stable_residual - rollover_residual) <= residual_margin:
            return None
        return min((stable, rollover), key=lambda item: item.median_residual_px or 0.0)

    @staticmethod
    def _validate_sequence(
        candles: tuple[FinalCandleTrace, ...],
        name: str,
    ) -> None:
        ids = tuple(candle.candidate_id for candle in candles)
        if len(ids) != len(set(ids)):
            raise ValueError(f"{name} no puede repetir candidate_id.")
        centers = tuple(candle_center_x(candle) for candle in candles)
        if centers != tuple(sorted(centers)):
            raise ValueError(f"{name} debe estar ordenada horizontalmente.")
