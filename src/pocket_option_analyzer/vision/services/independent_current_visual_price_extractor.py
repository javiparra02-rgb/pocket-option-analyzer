"""Explicit offline H1/H2 path; the regular extractor interface remains legacy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from statistics import median
from time import perf_counter
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from pocket_option_analyzer.vision.models.current_visual_price import CurrentVisualPrice
from pocket_option_analyzer.vision.models.current_visual_price_detection_trace import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceCandidateTrace,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceRejectionCounts,
)
from pocket_option_analyzer.vision.models.current_visual_price_extraction import (
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.models.independent_visual_price import (
    IndependentPriceTrace,
    LabelRoleCandidate,
    LabelRoleState,
    ObservationGeometry,
    ScaleContext,
    ScaleContextState,
)

from .independent_label_role_resolver import IndependentLabelRoleResolver
from .independent_price_config import IndependentPriceConfig
from .independent_scale_context_resolver import IndependentScaleContextResolver
from .pocket_option_current_visual_price_extractor import (
    PocketOptionCurrentVisualPriceExtractor,
)
from .price_text_recognizer import PriceTextRecognizer


class TracedPriceExtractor(Protocol):
    def extract_with_trace(
        self, image: NDArray[np.uint8]
    ) -> CurrentVisualPriceAnalysis: ...


@dataclass(frozen=True, slots=True)
class OfflinePriceEvaluation:
    """Timing is intentionally outside the persistable detection trace."""

    analysis: CurrentVisualPriceAnalysis
    h1_seconds: float
    h2_seconds: float


class IndependentCurrentVisualPriceExtractor:
    def __init__(
        self,
        *,
        recognizer: PriceTextRecognizer | None = None,
        config: IndependentPriceConfig | None = None,
        legacy: TracedPriceExtractor | None = None,
    ) -> None:
        self.config = config or IndependentPriceConfig()
        self._legacy = legacy or PocketOptionCurrentVisualPriceExtractor()
        self._context = IndependentScaleContextResolver(recognizer, self.config.scale)
        self._role = IndependentLabelRoleResolver(self.config.role)

    def extract(self, image: NDArray[np.uint8]) -> CurrentVisualPriceExtraction:
        return self.extract_with_trace(image).extraction

    def extract_with_trace(
        self, image: NDArray[np.uint8]
    ) -> CurrentVisualPriceAnalysis:
        # Even an offline-enabled instance cannot opt the ordinary/live pipeline in.
        return self._legacy.extract_with_trace(image)

    def evaluate_offline(
        self,
        image: NDArray[np.uint8],
        geometry: ObservationGeometry,
    ) -> OfflinePriceEvaluation:
        if not self.config.enabled:
            return OfflinePriceEvaluation(
                self._legacy.extract_with_trace(image), 0.0, 0.0
            )
        start = perf_counter()
        context = self._context.resolve(image, geometry)
        after_h1 = perf_counter()
        role = self._role.resolve(image, context)
        after_h2 = perf_counter()
        eligible = tuple(
            c for c in role.candidates if c.state is LabelRoleState.VERIFIED
        )
        # An unresolved competitor forbids even a diagnostic "selected" candidate.
        if role.state not in (LabelRoleState.VERIFIED, LabelRoleState.AMBIGUOUS):
            eligible = ()
        candidates = tuple(
            self._candidate(c, i, context, role.state is LabelRoleState.VERIFIED)
            for i, c in enumerate(eligible)
        )
        selected = next((c for c in candidates if c.selected), None)
        quality = selected.score if selected else None
        status = CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
        if (
            context.state is ScaleContextState.INVALID
            or role.state is LabelRoleState.INVALID
        ):
            status = CurrentVisualPriceStatus.INVALID_IMAGE
        elif role.state is LabelRoleState.AMBIGUOUS:
            status = CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
        elif selected is not None:
            status = (
                CurrentVisualPriceStatus.OK
                if selected.score >= self.config.min_quality
                else CurrentVisualPriceStatus.LOW_CONFIDENCE
            )
        diagnostic = (
            f"H1={context.state};H2={role.state};{role.reason};ABSENCE_NOT_CERTIFIED"
        )
        price = None
        if status is CurrentVisualPriceStatus.OK and selected is not None:
            price = CurrentVisualPrice(
                selected.y,
                1 - selected.y / (geometry.height - 1),
                geometry.width,
                geometry.height,
                "independent_h1_h2_offline_v1",
                selected.score,
            )
        extraction = CurrentVisualPriceExtraction(
            price,
            status,
            len(candidates),
            selected.x if selected else None,
            selected.y if selected else None,
            quality,
            diagnostic,
        )
        config_digest = hashlib.sha256(
            json.dumps(
                asdict(self.config),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        independent = IndependentPriceTrace(
            context, role, quality, self.config.min_quality, config_digest
        )
        # Legacy row-mask metrics are not fabricated for H2. Detailed evidence is
        # carried by the versioned independent_identity member, not semantic_search.
        trace = CurrentVisualPriceDetectionTrace(
            status=status,
            image_width=geometry.width,
            image_height=geometry.height,
            effective_chart_right_x=None,
            effective_chart_right_source=None,
            band_start=None,
            band_end=None,
            band_width=None,
            safe_top=None,
            safe_bottom=None,
            masked_pixel_count=0,
            candidates=candidates,
            rejection_counts=CurrentVisualPriceRejectionCounts(
                candidate_groups=len(candidates),
            ),
            decision_diagnostic=diagnostic,
            independent_identity=independent,
        )
        return OfflinePriceEvaluation(
            CurrentVisualPriceAnalysis(extraction, trace),
            after_h1 - start,
            after_h2 - after_h1,
        )

    @staticmethod
    def _candidate(
        candidate: LabelRoleCandidate, index: int, context: ScaleContext, selected: bool
    ) -> CurrentVisualPriceCandidateTrace:
        box = candidate.proposal.box
        rows = [g.row for g in candidate.guides if g.accepted]
        if not rows:
            raise ValueError("Verified role lacks external guide")
        return CurrentVisualPriceCandidateTrace(
            candidate_id=f"h2_{index:03d}",
            x=(box.x0 + box.x1 - 1) / 2,
            y=float(median(rows)),
            row_start=box.y0,
            row_end=box.y1 - 1,
            coverage=candidate.proposal.fill_pixels / box.area,
            span=(box.x1 - box.x0) / context.geometry.width,
            right_edge_gap=context.geometry.width - box.x1,
            score=candidate.proposal.fill_pixels / box.area,
            selected=selected,
        )
