from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.market import (
    CurrentCandleIdentityConfig,
    CurrentCandleIdentityMatcher,
    CurrentCandleMatchStatus,
    CurrentCandleTranslationHypothesis,
)
from pocket_option_analyzer.vision.models import (
    CandleColor,
    CandleGeometry,
    CandleType,
    FinalCandleTrace,
)


def _types(count: int) -> tuple[CandleType, ...]:
    return tuple(
        CandleType.BULLISH if index % 2 == 0 else CandleType.BEARISH
        for index in range(count)
    )


def _candles(
    candle_types: tuple[CandleType, ...],
    *,
    frame: int,
    pitch: int = 12,
    start_x: int = 100,
    vertical_offset: int = 0,
) -> tuple[FinalCandleTrace, ...]:
    return tuple(
        FinalCandleTrace(
            candidate_id=f"frame{frame}_candidate{index}",
            source_candidate_ids=(f"source{frame}_{index}",),
            ordinal=index,
            x=start_x + index * pitch,
            y=100 + vertical_offset + index,
            width=8,
            height=18,
            area=144,
            color=(
                CandleColor.WHITE
                if candle_type is CandleType.BULLISH
                else CandleColor.RED
            ),
            candle_type=candle_type,
            geometry=CandleGeometry(
                high_y=100 + vertical_offset + index,
                body_top_y=103 + vertical_offset + index,
                body_bottom_y=111 + vertical_offset + index,
                low_y=117 + vertical_offset + index,
            ),
            is_latest=index == len(candle_types) - 1,
        )
        for index, candle_type in enumerate(candle_types)
    )


def test_stable_matching_ignores_frame_local_candidate_id_changes() -> None:
    previous = _candles(_types(7), frame=1)
    current = _candles(_types(7), frame=2)

    result = CurrentCandleIdentityMatcher().match(
        previous=previous,
        current=current,
        estimated_pitch_px=12.0,
    )

    assert result.status is CurrentCandleMatchStatus.SELECTED
    assert result.selected_hypothesis is CurrentCandleTranslationHypothesis.STABLE
    assert result.stable.estimated_translation_px == 0.0
    assert result.stable.translation_in_pitch_units == 0.0
    assert result.stable.matched_member_count == 7
    assert result.stable.matched_historical_member_count == 6
    assert result.stable.type_match_ratio == 1.0
    assert result.stable.previous_candidate_ids != result.stable.current_candidate_ids


def test_rollover_matching_preserves_historical_types_and_finds_new_terminal() -> None:
    previous_types = _types(7)
    current_types = (*previous_types[1:], CandleType.BEARISH)
    previous = _candles(previous_types, frame=1)
    current = _candles(current_types, frame=2)

    result = CurrentCandleIdentityMatcher().match(
        previous=previous,
        current=current,
        estimated_pitch_px=12.0,
    )

    assert result.status is CurrentCandleMatchStatus.SELECTED
    assert result.selected_hypothesis is CurrentCandleTranslationHypothesis.ROLLOVER
    assert result.rollover.estimated_translation_px == -12.0
    assert result.rollover.translation_in_pitch_units == -1.0
    assert result.rollover.matched_member_count == 6
    assert result.rollover.matched_historical_member_count == 5
    assert result.rollover.matched_type_count == 5
    assert result.rollover.type_match_ratio == 1.0
    assert result.rollover.unmatched_previous_candidate_ids == (
        previous[0].candidate_id,
    )
    assert result.rollover.unmatched_current_candidate_ids == (
        current[-1].candidate_id,
    )


def test_mutable_current_vertical_geometry_does_not_break_rollover_history() -> None:
    previous_types = _types(7)
    current_types = (*previous_types[1:], CandleType.BEARISH)

    result = CurrentCandleIdentityMatcher().match(
        previous=_candles(previous_types, frame=1),
        current=_candles(current_types, frame=2, vertical_offset=300),
        estimated_pitch_px=12.0,
    )

    assert result.selected_hypothesis is CurrentCandleTranslationHypothesis.ROLLOVER
    assert result.rollover.type_match_ratio == 1.0


def test_bad_historical_type_alignment_rejects_rollover() -> None:
    result = CurrentCandleIdentityMatcher().match(
        previous=_candles(_types(7), frame=1),
        current=_candles((CandleType.DOJI,) * 7, frame=2),
        estimated_pitch_px=12.0,
    )

    assert result.rollover.qualifies is False
    assert result.rollover.type_match_ratio == 0.0


def test_equivalent_stable_and_rollover_hypotheses_are_ambiguous() -> None:
    all_bullish = (CandleType.BULLISH,) * 7

    result = CurrentCandleIdentityMatcher().match(
        previous=_candles(all_bullish, frame=1),
        current=_candles(all_bullish, frame=2),
        estimated_pitch_px=12.0,
    )

    assert result.status is CurrentCandleMatchStatus.AMBIGUOUS
    assert result.selected_hypothesis is None
    assert result.stable.qualifies is True
    assert result.rollover.qualifies is True


def test_insufficient_historical_support_is_unavailable() -> None:
    result = CurrentCandleIdentityMatcher().match(
        previous=_candles(_types(3), frame=1),
        current=_candles(_types(3), frame=2),
        estimated_pitch_px=12.0,
    )

    assert result.status is CurrentCandleMatchStatus.UNAVAILABLE
    assert result.stable.matched_historical_member_count == 2


def test_matcher_rejects_sequences_not_ordered_by_horizontal_position() -> None:
    previous = _candles(_types(7), frame=1)

    with pytest.raises(ValueError, match="ordenada horizontalmente"):
        CurrentCandleIdentityMatcher().match(
            previous=(previous[1], previous[0], *previous[2:]),
            current=_candles(_types(7), frame=2),
            estimated_pitch_px=12.0,
        )


def test_match_metrics_are_immutable_and_deterministic() -> None:
    matcher = CurrentCandleIdentityMatcher()
    previous = _candles(_types(7), frame=1)
    current = _candles(_types(7), frame=2)

    first = matcher.match(
        previous=previous,
        current=current,
        estimated_pitch_px=12.0,
    )
    second = matcher.match(
        previous=previous,
        current=current,
        estimated_pitch_px=12.0,
    )

    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.stable.qualifies = False  # type: ignore[misc]


def test_matcher_uses_injected_central_config() -> None:
    config = CurrentCandleIdentityConfig(minimum_historical_matches=6)
    matcher = CurrentCandleIdentityMatcher(config)

    result = matcher.match(
        previous=_candles(_types(7), frame=1),
        current=_candles(_types(7), frame=2),
        estimated_pitch_px=12.0,
    )

    assert matcher.config is config
    assert result.stable.qualifies is True


def test_matcher_public_type_hints_resolve() -> None:
    hints = get_type_hints(CurrentCandleIdentityMatcher.match)

    assert hints["previous"] == tuple[FinalCandleTrace, ...]
    assert hints["current"] == tuple[FinalCandleTrace, ...]
