from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pocket_option_analyzer.vision.models import CurrentVisualPriceExtraction

from .strategy_observation_outcome import VisualPriceReference
from .visual_price_reference_result import VisualPriceReferenceResult


class VisualReferenceMovement(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNRESOLVED = "unresolved"


def references_are_comparable(
    entry: VisualPriceReference,
    exit: VisualPriceReference,
    tolerance: float = 0.02,
) -> bool:
    if not entry.anchor_shape or len(entry.anchor_shape) != len(exit.anchor_shape):
        return False
    for entry_anchor, exit_anchor in zip(
        entry.anchor_shape,
        exit.anchor_shape,
        strict=True,
    ):
        if entry_anchor[0] != exit_anchor[0]:
            return False
        if any(
            abs(entry_value - exit_value) > tolerance
            for entry_value, exit_value in zip(
                entry_anchor[1:],
                exit_anchor[1:],
                strict=True,
            )
        ):
            return False
    return True


def compare_visual_references(
    entry: VisualPriceReference | None,
    exit: VisualPriceReference | None,
) -> VisualReferenceMovement:
    if entry is None or exit is None or not references_are_comparable(entry, exit):
        return VisualReferenceMovement.UNRESOLVED
    if exit.value > entry.value:
        return VisualReferenceMovement.UP
    if exit.value < entry.value:
        return VisualReferenceMovement.DOWN
    return VisualReferenceMovement.FLAT


@dataclass(frozen=True, slots=True)
class VisualReferenceValidation:
    snapshot_id: str
    observed_at: datetime
    resolve_at: datetime
    entry_reference: VisualPriceReference | None
    entry_reference_result: VisualPriceReferenceResult | None = None
    current_visual_price: CurrentVisualPriceExtraction | None = None

    def __post_init__(self) -> None:
        _normalize_utc(self, "observed_at", "resolve_at")


@dataclass(frozen=True, slots=True)
class VisualReferenceResolution:
    snapshot_id: str
    observed_at: datetime
    resolve_at: datetime
    resolved_at: datetime
    entry_reference: VisualPriceReference | None
    exit_reference: VisualPriceReference | None
    movement: VisualReferenceMovement
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        _normalize_utc(self, "observed_at", "resolve_at", "resolved_at")


def _normalize_utc(instance: object, *field_names: str) -> None:
    for field_name in field_names:
        value = getattr(instance, field_name)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} debe incluir zona horaria.")
        object.__setattr__(instance, field_name, value.astimezone(UTC))


def unresolved_diagnostic(
    entry: VisualPriceReference | None,
    exit: VisualPriceReference | None,
) -> str | None:
    if entry is None:
        return "missing_entry_reference"
    if exit is None:
        return "missing_exit_reference"
    if not references_are_comparable(entry, exit):
        return "incompatible_anchor_signatures"
    return None
