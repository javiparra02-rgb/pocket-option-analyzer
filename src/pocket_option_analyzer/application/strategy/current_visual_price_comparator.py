from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .current_visual_price_comparison import (
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
)
from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .strategy_observation_outcome import VisualPriceReference
from .visual_reference_validation import references_are_comparable

_Side = Literal["entry", "exit"]
_Failure = Literal[
    "extraction_unavailable",
    "geometry_missing",
    "geometry_incoherent",
    "reference_unavailable",
    "anchors_missing",
    "anchors_degenerate",
    "anchors_incoherent",
]


@dataclass(frozen=True, slots=True)
class _CanonicalVisualPrice:
    anchored_value: float
    price_y_in_chart_roi: float
    anchor_span_px: float
    source: str
    reference: VisualPriceReference


class CurrentVisualPriceComparator:
    """Maps two frame-local visual prices into their comparable anchor spaces."""

    def compare(
        self,
        entry_context: CurrentVisualPriceComparisonContext | None,
        exit_context: CurrentVisualPriceComparisonContext | None,
    ) -> CurrentVisualPriceComparison:
        if entry_context is None:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.ENTRY_CONTEXT_MISSING,
            )
        if exit_context is None:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.EXIT_CONTEXT_MISSING,
            )

        entry, diagnostic = self._canonical_value(entry_context, side="entry")
        if entry is None:
            assert diagnostic is not None
            return self._unavailable(diagnostic)

        exit, diagnostic = self._canonical_value(exit_context, side="exit")
        if exit is None:
            assert diagnostic is not None
            return self._unavailable(diagnostic, entry=entry)

        if entry.source != exit.source:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.SOURCES_NOT_COMPARABLE,
                entry=entry,
                exit=exit,
            )
        if not references_are_comparable(entry.reference, exit.reference):
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.REFERENCES_NOT_COMPARABLE,
                entry=entry,
                exit=exit,
            )

        return CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.AVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ),
            entry_anchored_value=entry.anchored_value,
            exit_anchored_value=exit.anchored_value,
            delta=exit.anchored_value - entry.anchored_value,
            entry_price_y_in_chart_roi=entry.price_y_in_chart_roi,
            exit_price_y_in_chart_roi=exit.price_y_in_chart_roi,
            entry_anchor_span_px=entry.anchor_span_px,
            exit_anchor_span_px=exit.anchor_span_px,
        )

    @staticmethod
    def _canonical_value(
        context: CurrentVisualPriceComparisonContext,
        *,
        side: _Side,
    ) -> tuple[
        _CanonicalVisualPrice | None,
        CurrentVisualPriceComparisonDiagnostic | None,
    ]:
        extraction = context.current_visual_price
        if extraction is None or not extraction.is_available:
            return None, _diagnostic(side, "extraction_unavailable")
        price = extraction.price
        if price is None:
            return None, _diagnostic(side, "extraction_unavailable")

        chart_region = context.chart_region
        price_region = context.price_observation_region
        if chart_region is None or price_region is None:
            return None, _diagnostic(side, "geometry_missing")
        if (
            chart_region.x < 0
            or chart_region.y < 0
            or price_region.x < 0
            or price_region.y < 0
            or not chart_region.has_positive_area
            or not price_region.has_positive_area
            or price.roi_width != price_region.width
            or price.roi_height != price_region.height
        ):
            return None, _diagnostic(side, "geometry_incoherent")

        price_y_in_chart_roi = price_region.y + price.roi_y - chart_region.y
        if not 0.0 <= price_y_in_chart_roi <= chart_region.height - 1:
            return None, _diagnostic(side, "geometry_incoherent")

        reference_result = context.reference_result
        if not reference_result.is_available:
            return None, _diagnostic(side, "reference_unavailable")
        reference = reference_result.reference
        if reference is None:
            return None, _diagnostic(side, "reference_unavailable")

        anchor_top = reference_result.anchor_top_roi_y
        anchor_bottom = reference_result.anchor_bottom_roi_y
        if anchor_top is None or anchor_bottom is None:
            return None, _diagnostic(side, "anchors_missing")
        if anchor_top == anchor_bottom:
            return None, _diagnostic(side, "anchors_degenerate")
        if (
            anchor_top < 0
            or anchor_bottom < 0
            or anchor_top > chart_region.height - 1
            or anchor_bottom > chart_region.height - 1
            or anchor_top > anchor_bottom
        ):
            return None, _diagnostic(side, "anchors_incoherent")

        anchored_value = (anchor_bottom - price_y_in_chart_roi) / (
            anchor_bottom - anchor_top
        )
        anchor_span_px = float(anchor_bottom - anchor_top)
        return (
            _CanonicalVisualPrice(
                anchored_value=anchored_value,
                price_y_in_chart_roi=price_y_in_chart_roi,
                anchor_span_px=anchor_span_px,
                source=price.source,
                reference=reference,
            ),
            None,
        )

    @staticmethod
    def _unavailable(
        diagnostic: CurrentVisualPriceComparisonDiagnostic,
        *,
        entry: _CanonicalVisualPrice | None = None,
        exit: _CanonicalVisualPrice | None = None,
    ) -> CurrentVisualPriceComparison:
        return CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=diagnostic,
            entry_anchored_value=(
                entry.anchored_value if entry is not None else None
            ),
            exit_anchored_value=(
                exit.anchored_value if exit is not None else None
            ),
            delta=None,
            entry_price_y_in_chart_roi=(
                entry.price_y_in_chart_roi if entry is not None else None
            ),
            exit_price_y_in_chart_roi=(
                exit.price_y_in_chart_roi if exit is not None else None
            ),
            entry_anchor_span_px=(
                entry.anchor_span_px if entry is not None else None
            ),
            exit_anchor_span_px=(
                exit.anchor_span_px if exit is not None else None
            ),
        )


def _diagnostic(
    side: _Side,
    failure: _Failure,
) -> CurrentVisualPriceComparisonDiagnostic:
    return CurrentVisualPriceComparisonDiagnostic(f"{side}_{failure}")
