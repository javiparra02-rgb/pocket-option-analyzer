from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.strategy import (
    PriceMovement,
    VisualPriceReference,
    VisualReferenceMovement,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    compare_visual_references,
    references_are_comparable,
)

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _reference(
    value: float,
    anchors: tuple[tuple[str, float, float, float, float], ...] = _ANCHORS,
) -> VisualPriceReference:
    return VisualPriceReference(value=value, anchor_shape=anchors)


@pytest.mark.parametrize(
    ("movement", "value"),
    (
        (PriceMovement.UP, "up"),
        (PriceMovement.DOWN, "down"),
        (PriceMovement.FLAT, "flat"),
        (PriceMovement.UNRESOLVED, "unresolved"),
    ),
)
def test_price_movement_values_are_stable(
    movement: PriceMovement,
    value: str,
) -> None:
    assert movement.value == value


def test_visual_reference_movement_is_identity_compatible_alias() -> None:
    assert VisualReferenceMovement is PriceMovement
    assert VisualReferenceMovement.UP is PriceMovement.UP


def test_legacy_movement_type_hint_resolves_to_generic_enum() -> None:
    assert get_type_hints(compare_visual_references)["return"] is PriceMovement


@pytest.mark.parametrize(
    ("entry_value", "exit_value", "expected"),
    (
        (1.05, 0.91, PriceMovement.DOWN),
        (1.02, 1.07, PriceMovement.UP),
        (-0.04, 0.10, PriceMovement.UP),
        (0.10, -0.04, PriceMovement.DOWN),
    ),
)
def test_legacy_movement_preserves_unclamped_affine_values(
    entry_value: float,
    exit_value: float,
    expected: PriceMovement,
) -> None:
    entry = _reference(entry_value)
    exit_reference = _reference(exit_value)

    assert references_are_comparable(entry, exit_reference)
    assert compare_visual_references(entry, exit_reference) is expected


def test_snapshot_three_like_anchor_drift_below_tolerance_remains_comparable() -> None:
    shifted = tuple(
        (
            anchor[0],
            *(component + 0.007094 for component in anchor[1:]),
        )
        for anchor in _ANCHORS
    )
    entry = _reference(1.021978021978022)
    exit_reference = _reference(1.0679933665008292, shifted)

    assert references_are_comparable(entry, exit_reference)
    assert compare_visual_references(entry, exit_reference) is PriceMovement.UP


def test_snapshot_one_like_type_mismatch_remains_not_comparable() -> None:
    changed_types = (
        ("bearish", *_ANCHORS[0][1:]),
        _ANCHORS[1],
    )
    entry = _reference(1.0363924050632911)
    exit_reference = _reference(1.0540983606557377, changed_types)

    assert not references_are_comparable(entry, exit_reference)
    assert (
        compare_visual_references(entry, exit_reference)
        is PriceMovement.UNRESOLVED
    )
