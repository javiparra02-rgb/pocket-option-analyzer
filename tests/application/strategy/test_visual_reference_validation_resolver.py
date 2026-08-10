from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceMovement,
    VisualReferenceValidationResolver,
)
from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _reference(value: float, anchors=_ANCHORS) -> VisualPriceReference:
    return VisualPriceReference(value, anchor_shape=anchors)


def _observation(
    instant: datetime,
    entry: VisualPriceReference | None = None,
    *,
    missing_entry: bool = False,
    entry_reference_result: VisualPriceReferenceResult | None = None,
    current_visual_price: CurrentVisualPriceExtraction | None = None,
) -> SimpleNamespace:
    if entry is None and not missing_entry:
        entry = _reference(0.5)

    return SimpleNamespace(
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        candle_interval_started_at=instant,
        direction=None,
        entry_reference=entry,
        entry_reference_result=entry_reference_result,
        current_visual_price=current_visual_price,
    )


@pytest.mark.parametrize(
    ("exit_value", "movement"),
    (
        (0.6, VisualReferenceMovement.UP),
        (0.4, VisualReferenceMovement.DOWN),
        (0.5, VisualReferenceMovement.FLAT),
    ),
)
def test_resolves_typed_movement_without_direction(exit_value, movement) -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    resolver = VisualReferenceValidationResolver()
    assert resolver.add(_observation(instant)) is not None
    assert (
        resolver.resolve_due(instant + timedelta(seconds=9), _reference(exit_value))
        == ()
    )

    resolution = resolver.resolve_due(
        instant + timedelta(seconds=10),
        _reference(exit_value),
    )[0]

    assert resolution.movement is movement
    assert resolver.resolve_due(instant + timedelta(seconds=11), _reference(0.7)) == ()


def test_missing_entry_and_incompatible_anchors_are_unresolved() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    missing = VisualReferenceValidationResolver()
    missing.add(_observation(instant, missing_entry=True))
    missing_resolution = missing.resolve_due(
        instant + timedelta(seconds=10), _reference(0.6)
    )[0]
    assert missing_resolution.movement is VisualReferenceMovement.UNRESOLVED
    assert missing_resolution.diagnostic == "missing_entry_reference"

    incompatible = VisualReferenceValidationResolver()
    incompatible.add(_observation(instant))
    changed = _reference(0.6, (("bullish", 1.0, 0.7, 0.5, 0.1),))
    changed_resolution = incompatible.resolve_due(
        instant + timedelta(seconds=10), changed
    )[0]
    assert changed_resolution.movement is VisualReferenceMovement.UNRESOLVED
    assert changed_resolution.diagnostic == "incompatible_anchor_signatures"


def test_deduplicates_snapshot() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    resolver = VisualReferenceValidationResolver()
    observation = _observation(instant)

    assert resolver.add(observation) is not None
    assert resolver.add(observation) is None


def test_add_preserves_entry_reference_diagnostic() -> None:
    instant = datetime(
        2026,
        8,
        9,
        tzinfo=UTC,
    )

    diagnostic = VisualPriceReferenceResult(
        reference=None,
        status=VisualPriceReferenceStatus.CLOSE_OUTSIDE_ANCHOR_RANGE,
        anchor_count=27,
        latest_candle_type="bullish",
        latest_candidate_x=620,
        latest_candidate_y=480,
        close_roi_y=514,
        anchor_top_roi_y=526,
        anchor_bottom_roi_y=782,
        raw_normalized_close=1.046875,
    )

    resolver = VisualReferenceValidationResolver()

    validation = resolver.add(
        _observation(
            instant,
            missing_entry=True,
            entry_reference_result=diagnostic,
        )
    )

    assert validation is not None
    assert validation.entry_reference is None
    assert validation.entry_reference_result is diagnostic

    assert (
        validation.entry_reference_result.status
        is VisualPriceReferenceStatus.CLOSE_OUTSIDE_ANCHOR_RANGE
    )
    assert validation.entry_reference_result.anchor_count == 27
    assert validation.entry_reference_result.close_roi_y == 514
    assert validation.entry_reference_result.anchor_top_roi_y == 526
    assert validation.entry_reference_result.anchor_bottom_roi_y == 782
    assert validation.entry_reference_result.raw_normalized_close == 1.046875


def test_add_preserves_current_visual_price_by_identity() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(514.0, 0.73125, 1320, 800, "test", 0.92),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )

    validation = VisualReferenceValidationResolver().add(
        _observation(instant, current_visual_price=extraction)
    )

    assert validation is not None
    assert validation.current_visual_price is extraction
