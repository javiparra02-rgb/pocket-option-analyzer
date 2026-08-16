from __future__ import annotations

from enum import StrEnum


class PriceMovement(StrEnum):
    """Evidence-independent direction of a price change."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNRESOLVED = "unresolved"


# Public compatibility alias for the legacy name.
VisualReferenceMovement = PriceMovement
