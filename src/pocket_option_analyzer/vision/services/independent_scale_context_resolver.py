"""Candidate-independent H1 port, derived from frozen H1-WINOCR-1."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal

import numpy as np
from numpy.typing import NDArray

from pocket_option_analyzer.vision.models.independent_visual_price import (
    GridEvidence,
    ObservationGeometry,
    OcrReading,
    PixelBox,
    ScaleContext,
    ScaleContextState,
    ScaleTick,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator

from .independent_price_config import ScaleContextConfig
from .price_text_recognizer import PriceTextRecognitionError, PriceTextRecognizer

_NUMERIC = re.compile(r"^[0-9]{1,6}[.,][0-9]{3,6}$")


class IndependentScaleContextResolver:
    def __init__(
        self,
        recognizer: PriceTextRecognizer | None,
        config: ScaleContextConfig | None = None,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._recognizer = recognizer
        self._config = config or ScaleContextConfig()
        self._clock = clock

    def resolve(
        self,
        image: NDArray[np.uint8],
        geometry: ObservationGeometry,
    ) -> ScaleContext:
        base = ScaleContext(
            ScaleContextState.INSUFFICIENT,
            (),
            geometry,
            "",
            "not_invoked",
        )
        if not FrameValidator.validate(image) or min(image.shape[:2]) < 32:
            return replace(
                base, state=ScaleContextState.INVALID, reasons=("INVALID_IMAGE",)
            )
        if image.shape[:2] != (geometry.height, geometry.width):
            return replace(
                base,
                state=ScaleContextState.INVALID,
                reasons=("CAPTURE_GEOMETRY_MISMATCH",),
            )
        cfg = self._config
        if geometry.width * geometry.height > cfg.max_pixels:
            return replace(base, reasons=("PIXEL_BUDGET_EXCEEDED",))
        bgr = np.ascontiguousarray(image[:, :, :3])
        base = replace(base, image_sha256=hashlib.sha256(bgr.tobytes()).hexdigest())
        if self._recognizer is None:
            return replace(base, reasons=("OCR_UNAVAILABLE",))
        deadline = self._clock() + cfg.max_seconds
        try:
            reading = self._recognizer.recognize(
                bgr,
                timeout=min(cfg.ocr_timeout_seconds, cfg.max_seconds),
                max_words=cfg.max_words,
            )
        except TimeoutError:
            return replace(base, reasons=("OCR_TIMEOUT",))
        except (PriceTextRecognitionError, OSError):
            return replace(base, reasons=("OCR_BACKEND_UNAVAILABLE",))
        except (ValueError, TypeError):
            return replace(
                base, state=ScaleContextState.INVALID, reasons=("OCR_RESULT_INVALID",)
            )
        if self._clock() > deadline:
            return replace(base, reasons=("CONTEXT_TIME_BUDGET_EXCEEDED",))
        if not isinstance(reading, OcrReading):
            return replace(
                base, state=ScaleContextState.INVALID, reasons=("OCR_RESULT_INVALID",)
            )
        base = replace(base, backend=reading.backend, text_angle=reading.text_angle)
        if len(reading.words) > cfg.max_words:
            return replace(base, reasons=("OCR_WORD_BUDGET_EXCEEDED",))
        return self._from_reading(bgr, reading, base, deadline)

    def _from_reading(
        self,
        image: NDArray[np.uint8],
        reading: OcrReading,
        base: ScaleContext,
        deadline: float,
    ) -> ScaleContext:
        cfg = self._config
        h, w = image.shape[:2]
        bgr = image.astype(np.int16)
        gray = np.mean(bgr, axis=2)
        chroma = np.max(bgr, axis=2) - np.min(bgr, axis=2)
        ticks: list[ScaleTick] = []
        rejected: list[str] = []
        for word in reading.words:
            if self._clock() > deadline:
                return replace(base, reasons=("CONTEXT_TIME_BUDGET_EXCEEDED",))
            if not _NUMERIC.fullmatch(word.text):
                continue
            if len(ticks) + len(rejected) >= cfg.max_numeric_candidates:
                return replace(base, reasons=("NUMERIC_BUDGET_EXCEEDED",))
            box = word.box
            x, y, xx, yy = box.coordinates
            ww, hh = xx - x, yy - y
            if ww < 15 or hh < 6 or min(x, y) < 2 or xx > w - 2 or yy > h - 2:
                rejected.append("CLIPPED_OR_SMALL_TEXT")
                continue
            if float(np.median(chroma[y:yy, x:xx])) > cfg.tick_background_max_chroma:
                rejected.append("NON_PLAIN_BACKGROUND")
                continue
            best: GridEvidence | None = None
            for gy in range(yy, min(h - 2, yy + 2 * hh + 1)):
                stripe = gray[gy] - (gray[gy - 2] + gray[gy + 2]) / 2
                mask = (stripe >= cfg.grid_delta) & (chroma[gy] <= cfg.grid_max_chroma)
                delta = np.diff(np.r_[False, mask, False].astype(np.int8))
                segments = list(
                    zip(
                        np.flatnonzero(delta == 1).tolist(),
                        np.flatnonzero(delta == -1).tolist(),
                        strict=True,
                    )
                )
                long = [
                    (a, b)
                    for a, b in segments
                    if b - a >= w * cfg.grid_min_run_width_ratio
                    and xx <= b <= x + 3 * ww
                ]
                if not long:
                    continue
                short = [
                    (a, b)
                    for a, b in segments
                    if b - a >= w * cfg.grid_short_run_width_ratio
                ]
                right = max(b for _, b in long)
                left = min(a for a, _ in short)
                candidate = GridEvidence(
                    gy, left, right, int(np.count_nonzero(mask[left:right]))
                )
                if best is None or candidate.supported_pixels > best.supported_pixels:
                    best = candidate
            if best is None:
                rejected.append("NO_EXTERNAL_GRID_SUPPORT")
            else:
                ticks.append(
                    ScaleTick(
                        word.text, str(Decimal(word.text.replace(",", "."))), box, best
                    )
                )
        base = replace(base, ticks=tuple(ticks), rejected_ticks=tuple(rejected))
        if len(ticks) < cfg.min_ticks:
            return replace(base, reasons=("FEWER_THAN_THREE_GRID_BOUND_NUMERIC_TICKS",))
        groups: list[ScaleContext] = []
        seen: set[tuple[int, ...]] = set()
        for tick in ticks:
            if self._clock() > deadline:
                return replace(base, reasons=("CONTEXT_TIME_BUDGET_EXCEEDED",))
            ids = tuple(
                i
                for i, t in enumerate(ticks)
                if abs(t.box.x1 - tick.box.x1) <= cfg.alignment_tolerance_px
            )
            if ids in seen or len(ids) < cfg.min_ticks:
                continue
            seen.add(ids)
            if len(seen) > cfg.max_groups:
                return replace(base, reasons=("GROUP_BUDGET_EXCEEDED",))
            group = sorted((ticks[i] for i in ids), key=lambda t: t.box.y0)
            vals = [Decimal(t.value) for t in group]
            rows = [t.grid.row for t in group]
            if any(a <= b for a, b in zip(vals[:-1], vals[1:], strict=True)) or any(
                a >= b for a, b in zip(rows[:-1], rows[1:], strict=True)
            ):
                continue
            spread = max(t.box.x1 for t in group) - min(t.box.x1 for t in group)
            if spread > cfg.alignment_tolerance_px:
                continue
            expected = [
                vals[0]
                + (vals[-1] - vals[0])
                * Decimal(r - rows[0])
                / Decimal(rows[-1] - rows[0])
                for r in rows
            ]
            residual = float(
                max(abs(v - e) for v, e in zip(vals, expected, strict=True))
                / abs(vals[-1] - vals[0])
            )
            if residual > cfg.linear_residual_ratio:
                continue
            boundaries = [t.grid.x1 for t in group]
            if max(boundaries) - min(boundaries) > cfg.group_boundary_tolerance_px:
                continue
            right = int(np.median(boundaries))
            if right < 5 or right > w - 5:
                continue
            seam = np.abs(
                np.mean(bgr[:, right : right + 3], axis=1)
                - np.mean(bgr[:, right - 3 : right], axis=1)
            ).mean(axis=1)
            panel_delta = float(np.median(seam))
            if panel_delta < cfg.panel_min_median_delta:
                continue
            groups.append(
                replace(
                    base,
                    state=ScaleContextState.AVAILABLE,
                    reasons=(),
                    scale_region=PixelBox(
                        min(t.box.x0 for t in group),
                        group[0].box.y0,
                        max(t.box.x1 for t in group),
                        max(t.box.y1 for t in group),
                    ),
                    observed_grid=PixelBox(
                        min(t.grid.x0 for t in group), rows[0], right, rows[-1] + 1
                    ),
                    ticks=tuple(group),
                    alignment_spread=spread,
                    linear_residual=residual,
                    panel_delta=panel_delta,
                )
            )
        if not groups:
            return replace(base, reasons=("NO_UNIQUE_COHERENT_SCALE",))
        if len(groups) > 1:
            return replace(
                base,
                state=ScaleContextState.AMBIGUOUS,
                reasons=("MULTIPLE_COHERENT_SCALES",),
            )
        if self._clock() > deadline:
            return replace(base, reasons=("CONTEXT_TIME_BUDGET_EXCEEDED",))
        return groups[0]
