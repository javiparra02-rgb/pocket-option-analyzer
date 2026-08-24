from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.market import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityConfig,
    CurrentCandleIdentityEvidence,
    CurrentCandleIdentityResolution,
    CurrentCandleIdentityResolver,
    CurrentCandleIdentityResult,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
    CurrentCandleIdentityTrace,
    CurrentCandleMissingEvidence,
    CurrentCandleSequenceMatch,
    CurrentCandleSequenceMatchMetrics,
    TerminalSlotRegion,
)


def _region() -> TerminalSlotRegion:
    return TerminalSlotRegion(
        center_x_roi=700.0,
        lower_x_roi=696.0,
        upper_x_roi=704.0,
        normalized_center_x=0.7,
        estimated_pitch_px=12.0,
        continuity_generation=1,
        learned_from_frame_ids=(1, 2),
    )


def _evidence(*, candidate_ids: tuple[str, ...]) -> CurrentCandleIdentityEvidence:
    return CurrentCandleIdentityEvidence(
        matched_historical_member_count=5,
        type_match_ratio=1.0,
        terminal_candidate_ids=candidate_ids,
        sufficient=True,
    )


def test_terminal_slot_region_is_frozen_and_slotted() -> None:
    region = _region()

    with pytest.raises(FrozenInstanceError):
        region.center_x_roi = 701.0  # type: ignore[misc]

    assert not hasattr(region, "__dict__")
    assert region.contains(700.0)
    assert not region.contains(705.0)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"center_x_roi": float("nan")}, "finitos"),
        ({"lower_x_roi": 701.0}, "ordenada"),
        ({"normalized_center_x": 1.1}, "entre cero y uno"),
        ({"estimated_pitch_px": 0.0}, "positivo"),
        ({"continuity_generation": 0}, "positivo"),
        ({"learned_from_frame_ids": (1,)}, "al menos dos"),
    ],
)
def test_terminal_slot_region_rejects_invalid_states(
    updates: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "center_x_roi": 700.0,
        "lower_x_roi": 696.0,
        "upper_x_roi": 704.0,
        "normalized_center_x": 0.7,
        "estimated_pitch_px": 12.0,
        "continuity_generation": 1,
        "learned_from_frame_ids": (1, 2),
    }
    values.update(updates)

    with pytest.raises(ValueError, match=message):
        TerminalSlotRegion(**values)  # type: ignore[arg-type]


def test_confirmed_result_requires_candidate_region_pitch_and_evidence() -> None:
    result = CurrentCandleIdentityResult(
        status=CurrentCandleIdentityStatus.CONFIRMED,
        candidate_id="frame3_candidate7",
        source=CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION,
        terminal_region=_region(),
        estimated_pitch_px=12.0,
        continuity_generation=1,
        evidence=_evidence(candidate_ids=("frame3_candidate7",)),
        diagnostics=("confirmed",),
    )

    assert result.candidate_id == "frame3_candidate7"


@pytest.mark.parametrize(
    "status",
    [
        CurrentCandleIdentityStatus.MISSING_FROM_VIEW,
        CurrentCandleIdentityStatus.UNAVAILABLE,
        CurrentCandleIdentityStatus.AMBIGUOUS,
    ],
)
def test_nonconfirmed_results_cannot_assert_candidate_id(
    status: CurrentCandleIdentityStatus,
) -> None:
    with pytest.raises(ValueError, match="Solo CONFIRMED"):
        CurrentCandleIdentityResult(
            status=status,
            candidate_id="silently_chosen",
            source=CurrentCandleIdentitySource.NONE,
            terminal_region=_region(),
            estimated_pitch_px=12.0,
            continuity_generation=1,
            evidence=None,
            diagnostics=("invalid",),
        )


def test_missing_result_requires_structured_sufficient_evidence() -> None:
    result = CurrentCandleIdentityResult(
        status=CurrentCandleIdentityStatus.MISSING_FROM_VIEW,
        candidate_id=None,
        source=CurrentCandleIdentitySource.TERMINAL_SLOT_EMPTY,
        terminal_region=_region(),
        estimated_pitch_px=12.0,
        continuity_generation=1,
        evidence=_evidence(candidate_ids=()),
        diagnostics=("missing",),
    )

    assert result.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW


def test_missing_evidence_requires_every_conservative_fact() -> None:
    complete = CurrentCandleMissingEvidence(
        terminal_region_valid=True,
        terminal_member_absent=True,
        previous_slot_candidate_id="previous",
        previous_slot_fully_observable=True,
        previous_slot_distance_in_pitch_units=1.0,
        candle_like_competitor_ids=(),
    )
    ambiguous = CurrentCandleMissingEvidence(
        terminal_region_valid=True,
        terminal_member_absent=True,
        previous_slot_candidate_id="previous",
        previous_slot_fully_observable=True,
        previous_slot_distance_in_pitch_units=1.0,
        candle_like_competitor_ids=("excluded_near_terminal",),
    )

    assert complete.sufficient is True
    assert ambiguous.sufficient is False


def test_config_centralizes_and_validates_provisional_thresholds() -> None:
    config = CurrentCandleIdentityConfig()

    assert config.minimum_historical_matches == 3
    assert config.maximum_match_residual_pitch_ratio == 0.20
    assert config.maximum_pitch_drift_ratio == 0.12
    assert config.maximum_roi_dimension_drift_ratio == 0.02
    assert config.maximum_frame_id_step == 1

    with pytest.raises(ValueError):
        CurrentCandleIdentityConfig(minimum_type_match_ratio=1.1)


def test_frame_context_rejects_invalid_temporal_and_owner_values() -> None:
    with pytest.raises(ValueError, match="source_key"):
        CurrentCandleFrameContext(
            frame_id=1,
            wall_timestamp=datetime.now(UTC),
            monotonic_timestamp=1.0,
            roi_width=1000,
            roi_height=788,
            source_key="",
            session_key="session",
            membership=None,
            final_candles=(),
        )


def test_public_type_hints_resolve_for_new_contracts_and_lifecycle_api() -> None:
    contracts = (
        CurrentCandleFrameContext,
        CurrentCandleIdentityConfig,
        CurrentCandleIdentityEvidence,
        CurrentCandleIdentityResolution,
        CurrentCandleIdentityResult,
        CurrentCandleIdentityTrace,
        CurrentCandleMissingEvidence,
        CurrentCandleSequenceMatch,
        CurrentCandleSequenceMatchMetrics,
        TerminalSlotRegion,
    )

    for contract in contracts:
        assert get_type_hints(contract)

    assert get_type_hints(CurrentCandleIdentityResolver.resolve)["return"] is (
        CurrentCandleIdentityResult
    )
    assert get_type_hints(CurrentCandleIdentityResolver.resolve_with_trace)[
        "return"
    ] is CurrentCandleIdentityResolution
    assert get_type_hints(CurrentCandleIdentityResolver.start_session)[
        "return"
    ] is type(None)
    assert get_type_hints(CurrentCandleIdentityResolver.stop_session)[
        "return"
    ] is type(None)
    assert get_type_hints(CurrentCandleIdentityResolver.reset)["return"] is type(None)
