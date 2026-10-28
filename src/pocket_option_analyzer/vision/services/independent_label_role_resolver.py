"""Modular H2-R3D-CONTAINMENT-V2 port; identity never comes from a score."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import replace

import cv2
import numpy as np
from numpy.typing import NDArray

from pocket_option_analyzer.vision.models.independent_visual_price import (
    ExternalGuide,
    LabelProposal,
    LabelRoleCandidate,
    LabelRoleResult,
    LabelRoleState,
    PixelBox,
    ScaleContext,
    ScaleContextState,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator

from .independent_price_config import LabelRoleConfig


class RoleBudgetError(RuntimeError):
    pass


class LabelProposalGenerator:
    """Morphology proposes envelopes; all support is read from original pixels."""

    def generate(
        self,
        image: NDArray[np.uint8],
        cfg: LabelRoleConfig,
        check_budget: Callable[[], None],
    ) -> tuple[tuple[LabelProposal, ...], tuple[tuple[str, int], ...]]:
        q = image.astype(np.int32) // cfg.quantization
        radix = 256 // cfg.quantization
        keys = q[:, :, 0] * radix * radix + q[:, :, 1] * radix + q[:, :, 2]
        colors, counts = np.unique(keys, return_counts=True)
        eligible = colors[counts >= cfg.min_color_pixels]
        if len(eligible) > cfg.max_colors:
            raise RoleBudgetError("COLOR_BIN_LIMIT")
        proposals: list[LabelProposal] = []
        rejected = {"geometry": 0, "fill": 0, "glyph_contrast": 0}
        for color in eligible:
            check_budget()
            original = (keys == color).astype(np.uint8)
            body = cv2.morphologyEx(
                original, cv2.MORPH_CLOSE, np.ones((3, 7), np.uint8)
            )
            body = cv2.morphologyEx(body, cv2.MORPH_OPEN, np.ones((9, 3), np.uint8))
            n, _, stats, _ = cv2.connectedComponentsWithStats(body, connectivity=8)
            for index in range(1, n):
                check_budget()
                x, y, w, h, _ = (int(v) for v in stats[index])
                if not (
                    cfg.min_width <= w <= cfg.max_width
                    and cfg.min_height <= h <= cfg.max_height
                    and cfg.min_ratio <= w / h <= cfg.max_ratio
                ):
                    rejected["geometry"] += 1
                    continue
                mask = original[y : y + h, x : x + w].astype(bool)
                filled = int(mask.sum())
                if filled < cfg.min_fill * w * h:
                    rejected["fill"] += 1
                    continue
                crop = image[y : y + h, x : x + w]
                color_value = np.median(crop[mask], axis=0)
                glyph = (crop.min(axis=2) > 60) & (
                    crop.mean(axis=2) > float(color_value.mean()) + 25
                )
                if int(glyph.sum()) < cfg.min_glyph_pixels:
                    rejected["glyph_contrast"] += 1
                    continue
                proposals.append(
                    LabelProposal(
                        PixelBox(x, y, x + w, y + h),
                        filled,
                        (
                            float(color_value[0]),
                            float(color_value[1]),
                            float(color_value[2]),
                        ),
                        int(glyph.sum()),
                        int(
                            cv2.connectedComponents(
                                mask.astype(np.uint8), connectivity=8
                            )[0]
                            - 1
                        ),
                        ((int(color), index),),
                    )
                )
                if len(proposals) > 256:
                    raise RoleBudgetError("RAW_PROPOSAL_LIMIT")
        result = self.deduplicate(proposals, cfg.dedup_iou)
        if len(result) > cfg.max_proposals:
            raise RoleBudgetError("PROPOSAL_LIMIT")
        return result, tuple(rejected.items())

    @staticmethod
    def deduplicate(
        proposals: list[LabelProposal], threshold: float
    ) -> tuple[LabelProposal, ...]:
        result: list[LabelProposal] = []
        for p in sorted(proposals, key=lambda p: (-p.fill_pixels, p.box.coordinates)):
            for i, q in enumerate(result):
                a, b = p.box, q.box
                intersection = max(0, min(a.x1, b.x1) - max(a.x0, b.x0)) * max(
                    0, min(a.y1, b.y1) - max(a.y0, b.y0)
                )
                if intersection / (a.area + b.area - intersection) >= threshold:
                    result[i] = replace(q, sources=q.sources + p.sources)
                    break
            else:
                result.append(p)
        return tuple(
            sorted(result, key=lambda p: (p.box.y0, p.box.x0, p.box.y1, p.box.x1))
        )


class ExternalGuideObserver:
    def observe(
        self,
        image: NDArray[np.uint8],
        proposal: LabelProposal,
        chart: PixelBox,
        cfg: LabelRoleConfig,
    ) -> tuple[ExternalGuide, ...]:
        box = proposal.box
        middle = (box.y0 + box.y1 - 1) // 2
        fill = np.array(proposal.fill_color_bgr)
        guides: list[ExternalGuide] = []
        if box.x0 <= chart.x0:
            return ()
        for y in range(
            middle - cfg.guide_center_tolerance, middle + cfg.guide_center_tolerance + 1
        ):
            if y - 2 < chart.y0 or y + 2 >= chart.y1:
                continue
            strip = image[y, chart.x0 : box.x0].astype(float)
            neighbors = (
                image[y - 2, chart.x0 : box.x0].astype(float)
                + image[y + 2, chart.x0 : box.x0].astype(float)
            ) / 2
            supported = (
                np.max(abs(strip - fill), axis=1) <= cfg.guide_color_distance
            ) & (np.max(abs(strip - neighbors), axis=1) >= cfg.guide_neighbor_contrast)
            edges = np.diff(np.r_[False, supported, False].astype(np.int8))
            for start, end in zip(
                np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True
            ):
                run_start, run_end = chart.x0 + int(start), chart.x0 + int(end)
                if run_end - run_start < 3:
                    continue
                attached = run_end == box.x0
                above = np.max(
                    abs(image[y - 2, run_start:run_end].astype(float) - fill), axis=1
                )
                below = np.max(
                    abs(image[y + 2, run_start:run_end].astype(float) - fill), axis=1
                )
                thin = bool(
                    np.all(
                        (above > cfg.guide_color_distance)
                        & (below > cfg.guide_color_distance)
                    )
                )
                ingress = (
                    np.max(abs(image[y, box.x0].astype(float) - fill))
                    <= cfg.guide_color_distance
                )
                enough = run_end - run_start >= cfg.min_guide_run
                accepted = bool(attached and thin and ingress and enough)
                reason = (
                    "OBSERVED_EXTERNAL_INGRESS"
                    if accepted
                    else (
                        "DISCONNECTED_RUN_GAP_NOT_FILLED"
                        if not attached
                        else (
                            "SHORT_OBSERVED_INGRESS"
                            if not enough
                            else "BROAD_OR_DISCONNECTED_SUPPORT"
                        )
                    )
                )
                guides.append(
                    ExternalGuide(
                        y, run_start, run_end, accepted, reason, box.x0 - run_end
                    )
                )
                if len(guides) > 64:
                    raise RoleBudgetError("GUIDE_TRACE_LIMIT")
        return tuple(guides)


class LabelRoleAssociator:
    def __init__(self, observer: ExternalGuideObserver | None = None) -> None:
        self._observer = observer or ExternalGuideObserver()

    def associate(
        self,
        image: NDArray[np.uint8],
        proposal: LabelProposal,
        context: ScaleContext,
        cfg: LabelRoleConfig,
    ) -> LabelRoleCandidate:
        chart, scale, box = context.observed_grid, context.scale_region, proposal.box
        if (
            context.state is not ScaleContextState.AVAILABLE
            or chart is None
            or scale is None
        ):
            return LabelRoleCandidate(
                proposal, LabelRoleState.INSUFFICIENT, "H1_NOT_AVAILABLE", True
            )
        overlap = max(0, min(box.x1, scale.x1) - max(box.x0, scale.x0)) / (
            scale.x1 - scale.x0
        )
        if (
            overlap < cfg.min_scale_overlap
            or abs(box.x1 - chart.x1) > cfg.dock_tolerance
        ):
            return LabelRoleCandidate(
                proposal,
                LabelRoleState.REJECTED,
                "NOT_DOCKED_TO_OBSERVED_SCALE",
                False,
                contradictions=("SCALE_GEOMETRY_INCOMPATIBLE",),
            )
        h, w = image.shape[:2]
        if box.x0 <= 0 or box.x1 >= w or box.y0 <= 0 or box.y1 >= h:
            return LabelRoleCandidate(
                proposal, LabelRoleState.INSUFFICIENT, "IMAGE_EDGE_CLIPPING", True
            )
        # R3C-01: docking tolerance NEVER expands the independently observed H1 grid.
        if not chart.contains(box):
            return LabelRoleCandidate(
                proposal,
                LabelRoleState.INSUFFICIENT,
                "OUTSIDE_OBSERVED_H1_FOOTPRINT",
                True,
            )
        favorable = ("SCALE_DOCKING", "GLYPH_CONTRAST", "BODY_IN_OBSERVED_FOOTPRINT")
        guides = self._observer.observe(image, proposal, chart, cfg)
        if any(g.accepted for g in guides):
            return LabelRoleCandidate(
                proposal,
                LabelRoleState.VERIFIED,
                "JOINT_SCALE_BODY_GUIDE_EVIDENCE",
                True,
                guides,
                favorable + ("PHYSICAL_EXTERNAL_GUIDE_INGRESS",),
            )
        return LabelRoleCandidate(
            proposal,
            LabelRoleState.INSUFFICIENT,
            "EXTERNAL_GUIDE_INGRESS_NOT_ACCREDITED",
            True,
            guides,
            favorable,
        )


class ConservativeRoleSelector:
    @staticmethod
    def select(
        candidates: tuple[LabelRoleCandidate, ...],
    ) -> tuple[LabelRoleState, PixelBox | None, str]:
        verified = [c for c in candidates if c.state is LabelRoleState.VERIFIED]
        if len(verified) > 1:
            return LabelRoleState.AMBIGUOUS, None, "MULTIPLE_DISTINCT_VERIFIED_OBJECTS"
        if any(
            c.relevant and c.state is LabelRoleState.INSUFFICIENT for c in candidates
        ):
            return (
                LabelRoleState.INSUFFICIENT,
                None,
                "PLAUSIBLE_COMPETITOR_OR_ASSOCIATION_UNRESOLVED",
            )
        if len(verified) == 1:
            return (
                LabelRoleState.VERIFIED,
                verified[0].proposal.box,
                "UNIQUE_SUPPORTED_ROLE",
            )
        if not candidates:
            return LabelRoleState.NO_PROPOSAL, None, "NO_BODY_PROPOSAL_FOUND"
        return LabelRoleState.REJECTED, None, "ALL_PROPOSALS_GEOMETRICALLY_INCOMPATIBLE"


class IndependentLabelRoleResolver:
    def __init__(
        self,
        config: LabelRoleConfig | None = None,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._cfg = config or LabelRoleConfig()
        self._clock = clock
        self._generator = LabelProposalGenerator()
        self._associator = LabelRoleAssociator()

    def resolve(
        self, image: NDArray[np.uint8], context: ScaleContext
    ) -> LabelRoleResult:
        result = LabelRoleResult(LabelRoleState.INVALID, "INVALID_IMAGE")
        if not FrameValidator.validate(image):
            return result
        image = np.ascontiguousarray(image[:, :, :3])
        h, w = image.shape[:2]
        if h * w > self._cfg.max_pixels:
            return replace(result, state=LabelRoleState.BUDGET, reason="PIXEL_LIMIT")
        if (w, h) != (context.geometry.width, context.geometry.height):
            return replace(result, reason="H1_GEOMETRY_MISMATCH")
        if (
            context.image_sha256
            and hashlib.sha256(image.tobytes()).hexdigest() != context.image_sha256
        ):
            return replace(result, reason="H1_IMAGE_MISMATCH")
        deadline = self._clock() + self._cfg.max_seconds

        def check_budget() -> None:
            if self._clock() > deadline:
                raise RoleBudgetError("TIME_LIMIT")

        try:
            proposals, rejected = self._generator.generate(
                image, self._cfg, check_budget
            )
            result = replace(result, proposals=proposals, proposal_rejections=rejected)
            if context.state is ScaleContextState.INVALID:
                return replace(result, reason="H1_INVALID")
            if context.state is not ScaleContextState.AVAILABLE:
                return replace(
                    result,
                    state=LabelRoleState.INSUFFICIENT,
                    reason="H1_NOT_AVAILABLE_PROPOSALS_RETAINED",
                )
            if len(proposals) > self._cfg.max_associations:
                raise RoleBudgetError("ASSOCIATION_LIMIT")
            candidates: list[LabelRoleCandidate] = []
            for p in proposals:
                check_budget()
                candidates.append(
                    self._associator.associate(image, p, context, self._cfg)
                )
            check_budget()
            state, box, reason = ConservativeRoleSelector.select(tuple(candidates))
            return replace(
                result,
                state=state,
                selected_box=box,
                reason=reason,
                candidates=tuple(candidates),
            )
        except RoleBudgetError as exc:
            return replace(result, state=LabelRoleState.BUDGET, reason=str(exc))
