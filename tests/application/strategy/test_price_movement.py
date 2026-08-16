from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.strategy import (
    PriceMovement,
    VisualReferenceMovement,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    compare_visual_references,
)


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
