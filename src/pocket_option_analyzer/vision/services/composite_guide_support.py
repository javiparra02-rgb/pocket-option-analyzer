"""Conservative, nonrecursive differential-compositing observations."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from math import ceil

import numpy as np

from pocket_option_analyzer.vision.models.composite_guide import (
    CONTRACT,
    Color,
    CompositeGuideTrace,
    CompositeRegionEvidence,
    CompositeRowEvidence,
    Span,
)

# Versioned experimental limits; no photograph coordinates or expected prices.
LIMITS = {
    "contract": CONTRACT,
    "quantization_tolerance": 2,
    "minimum_background_change": 16,
    "minimum_stroke_contrast": 8,
    "beta_range": [0.1, 0.9],
    "beta_spread": 0.05,
    "maximum_band_height": 7,
    "anchor_aspect": 4,
    "maximum_pixels": 4_000_000,
    "maximum_regions": 4096,
}


def _spans(mask: np.ndarray) -> tuple[Span, ...]:
    result = []
    for y in range(mask.shape[0]):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            for run in np.split(xs, np.flatnonzero(np.diff(xs) > 1) + 1):
                result.append((y, int(run[0]), int(run[-1]) + 1))
    return tuple(result)


def _color(values: np.ndarray) -> Color:
    return int(values[0]), int(values[1]), int(values[2])


class CompositeGuideSupportObserver:
    """Observe pixels; never grow a LABEL, fill a gap or infer object ownership."""

    def observe(
        self, bgr: np.ndarray, direct: np.ndarray, *, roi_origin: tuple[int, int]
    ) -> tuple[np.ndarray, CompositeGuideTrace]:
        height, width = direct.shape
        direct_spans = _spans(direct)
        regions: list[CompositeRegionEvidence] = []
        composite = np.zeros_like(direct)
        seen: set[tuple[int, int, int, int]] = set()
        budget_reasons: tuple[str, ...] = ()
        by_row: dict[int, list[Span]] = {}
        for span in direct_spans:
            by_row.setdefault(span[0], []).append(span)
        for y, runs in by_row.items():
            # Seed provenance uses the existing v1 true-gap rule, not a stricter
            # single raw run and never newly accredited composite pixels.
            seed_bounds: dict[Span, tuple[int, int]] = {}
            clusters: list[list[Span]] = []
            maximum_gap = ceil(width * 0.2 * 0.01)
            for run in runs:
                if clusters and run[1] - clusters[-1][-1][2] <= maximum_gap:
                    clusters[-1].append(run)
                else:
                    clusters.append([run])
            for cluster in clusters:
                a, b = cluster[0][1], cluster[-1][2]
                if b - a >= ceil(b * 0.2 * 0.7):
                    seed_bounds.update({run: (a, b) for run in cluster})
            for left, right in zip(runs, runs[1:], strict=False):
                start, end = left[2], right[1]
                left_length, right_length = start - left[1], right[2] - end
                # Strong seed must already exist in direct evidence alone.
                seeds = [seed_bounds[r] for r in (left, right) if r in seed_bounds]
                if not seeds:
                    continue
                if min(left_length, right_length) < 6:
                    continue
                top, bottom = y, y + 1
                while (
                    top > 0 and direct[top - 1, start - 2] and direct[top - 1, end + 1]
                ):
                    top -= 1
                    if y - top >= 7:
                        break
                while (
                    bottom < height
                    and direct[bottom, start - 2]
                    and direct[bottom, end + 1]
                ):
                    bottom += 1
                    if bottom - top > 7:
                        break
                key = top, bottom, start, end
                if key in seen:
                    continue
                seen.add(key)
                if len(seen) > 4096:
                    budget_reasons = ("composite_region_budget_exceeded",)
                    break
                thickness = bottom - top
                anchor_width = max(4, 4 * thickness)
                geometry_reasons = []
                if thickness > 7:
                    geometry_reasons.append("direct_band_too_thick")
                if min(left_length, right_length) < anchor_width + 2:
                    geometry_reasons.append("insufficient_horizontal_anchor")
                if end - start > min(max(b - a for a, b in seeds), ceil(width * 0.2)):
                    geometry_reasons.append("composite_region_exceeds_direct_seed")
                if geometry_reasons:
                    regions.append(
                        CompositeRegionEvidence(
                            top=top,
                            bottom=bottom,
                            start_x=start,
                            end_x=end,
                            left_anchor=(left[1], left[2]),
                            right_anchor=(right[1], right[2]),
                            rows=(),
                            rejection_reasons=tuple(geometry_reasons),
                            direct_seed_bounds=tuple(sorted(set(seeds))),
                        )
                    )
                    continue
                region = self._region(bgr, direct, key, anchor_width)
                region = replace(region, direct_seed_bounds=tuple(sorted(set(seeds))))
                regions.append(region)
                if region.accepted:
                    composite[top:bottom, start:end] = 255
            if budget_reasons:
                break
        if budget_reasons:
            composite.fill(0)  # Never select from a truncated evidence census.
        trace = CompositeGuideTrace(
            raster_sha256=sha256(np.ascontiguousarray(bgr).tobytes()).hexdigest(),
            config_sha256=sha256(
                json.dumps(LIMITS, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            image_width=width,
            image_height=height,
            roi_origin=roi_origin,
            direct_spans=direct_spans,
            composite_spans=_spans(composite),
            regions=tuple(regions),
            rejection_reasons=budget_reasons,
        )
        return np.maximum(direct, composite), trace

    @staticmethod
    def _region(
        bgr: np.ndarray,
        direct: np.ndarray,
        bounds: tuple[int, int, int, int],
        anchor_width: int,
    ) -> CompositeRegionEvidence:
        top, bottom, start, end = bounds
        la = start - 1 - anchor_width, start - 1
        ra = end + 1, end + 1 + anchor_width
        reasons: list[str] = []
        rows: list[CompositeRowEvidence] = []
        if top < 2 or bottom + 2 > bgr.shape[0]:
            reasons.append("missing_vertical_context")
        elif np.any(direct[top:bottom, start:end]):
            reasons.append("inconsistent_gap_band")
        elif not (
            np.all(direct[top:bottom, la[0] : la[1]])
            and np.all(direct[top:bottom, ra[0] : ra[1]])
        ):
            reasons.append("anchor_not_direct")
        else:
            # Two independent vertical observations, not interpolated background.
            upper = bgr[top - 2 : top].astype(float)
            lower = bgr[bottom : bottom + 2].astype(float)
            anchor_columns = np.r_[np.arange(*la), np.arange(*ra)]
            bg_samples = np.concatenate(
                (upper[:, anchor_columns], lower[:, anchor_columns])
            )
            base = np.median(bg_samples.reshape(-1, 3), axis=0)
            if np.max(np.abs(bg_samples - base)) > 2:
                reasons.append("anchor_background_texture_or_mismatch")
            gap_samples = np.concatenate((upper[:, start:end], lower[:, start:end]))
            occluder = gap_samples[0]
            if np.max(np.abs(gap_samples - occluder)) > 2:
                reasons.append("contradictory_vertical_background")
            delta = occluder - base
            denom = np.sum(delta * delta, axis=1)
            if np.any(np.max(np.abs(delta), axis=1) < 16):
                reasons.append("background_change_not_observable")
            for y in range(top, bottom):
                samples = bgr[y, anchor_columns].astype(float)
                guide = np.median(samples, axis=0)
                observed = bgr[y, start:end].astype(float)
                row_reasons = []
                if np.max(np.abs(samples - guide)) > 2:
                    row_reasons.append("incompatible_direct_anchors")
                if np.max(np.abs(guide - base)) < 8 or np.any(
                    np.max(np.abs(observed - occluder), axis=1) < 8
                ):
                    row_reasons.append("stroke_contrast_insufficient")
                beta = np.sum((observed - guide) * delta, axis=1) / np.maximum(denom, 1)
                residual = float(
                    np.max(np.abs(observed - guide - beta[:, None] * delta))
                )
                low, high = float(beta.min()), float(beta.max())
                if low < 0.1 or high > 0.9:
                    row_reasons.append("no_interior_compositing_coefficient")
                if high - low > 0.05:
                    row_reasons.append("inconsistent_opacity")
                if residual > 2:
                    row_reasons.append("chromatic_compositing_contradiction")
                reasons.extend(row_reasons)
                rows.append(
                    CompositeRowEvidence(
                        row_y=y,
                        direct_bgr=_color(guide),
                        anchor_background_bgr=_color(base),
                        observed_bgr=tuple(_color(c) for c in observed),
                        background_bgr=tuple(_color(c) for c in occluder),
                        beta_min=low,
                        beta_max=high,
                        maximum_residual=residual,
                    )
                )
        return CompositeRegionEvidence(
            top=top,
            bottom=bottom,
            start_x=start,
            end_x=end,
            left_anchor=la,
            right_anchor=ra,
            rows=tuple(rows),
            rejection_reasons=tuple(sorted(set(reasons))),
        )
