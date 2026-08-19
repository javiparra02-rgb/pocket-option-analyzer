from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import ClassVar

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    ClassifiedCandle,
)


@dataclass(frozen=True, slots=True)
class _VerticalLineObservation:
    support_ratio: float
    contact_gap_ratio: float
    horizontal_alignment_ratio: float


class PocketOptionExpiryOverlayEvidenceResolver:
    """Detecta caps de expiry unidos a líneas verticales extensas.

    La búsqueda es local a cada candidato y utiliza bordes por columna. No
    decide pertenencia a la serie ni elimina píxeles de la evidencia original.
    """

    EDGE_LOW_THRESHOLD: ClassVar[int] = 50
    EDGE_HIGH_THRESHOLD: ClassVar[int] = 150

    # Un cap es más ancho que alto. La forma nunca basta por sí sola: solo
    # habilita la evaluación conjunta con una línea extensa y en contacto.
    MAX_CAP_HEIGHT_TO_WIDTH_RATIO: ClassVar[float] = 0.80
    HORIZONTAL_SEARCH_MARGIN_RATIO: ClassVar[float] = 0.25

    # La línea de expiry ocupa una fracción material del ROI. El umbral es
    # relativo para conservar invariancia de escala y no codifica un frame.
    MIN_VERTICAL_LINE_SUPPORT_RATIO: ClassVar[float] = 0.50
    MAX_LINE_CONTACT_GAP_RATIO: ClassVar[float] = 0.15
    MAX_HORIZONTAL_ALIGNMENT_RATIO: ClassVar[float] = 0.25
    MAX_VERTICAL_EDGE_INTERRUPTION_RATIO: ClassVar[float] = 0.15

    def resolve(
        self,
        image: np.ndarray,
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
    ) -> CandleOverlayEvidenceTrace:
        """Genera evidencia alineada usando el chart ROI ya capturado."""

        self._validate_inputs(image, candles, candidate_ids)
        gray = self._to_grayscale(image)
        edges = cv2.Canny(
            gray,
            self.EDGE_LOW_THRESHOLD,
            self.EDGE_HIGH_THRESHOLD,
        )
        evidence = tuple(
            self._evaluate_candidate(
                edges=edges,
                candle=candle,
                candidate_id=candidate_id,
            )
            for candle, candidate_id in zip(
                candles,
                candidate_ids,
                strict=True,
            )
        )
        return CandleOverlayEvidenceTrace(
            evaluated_candidate_ids=candidate_ids,
            evidence=evidence,
        )

    @staticmethod
    def _validate_inputs(
        image: np.ndarray,
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
    ) -> None:
        if image.ndim not in (2, 3):
            raise ValueError("image debe ser grayscale, BGR o BGRA.")
        if image.ndim == 3 and image.shape[2] not in (3, 4):
            raise ValueError("image debe tener tres o cuatro canales.")
        if image.shape[0] < 1 or image.shape[1] < 1:
            raise ValueError("image no puede estar vacía.")
        if len(candles) != len(candidate_ids):
            raise ValueError("candles y candidate_ids deben estar alineados.")
        if any(not candidate_id for candidate_id in candidate_ids):
            raise ValueError("candidate_ids no puede contener valores vacíos.")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_ids no puede contener duplicados.")
        if any(
            candle.candidate.width <= 0 or candle.candidate.height <= 0
            for candle in candles
        ):
            raise ValueError("Los candidatos deben tener dimensiones positivas.")

    @staticmethod
    def _to_grayscale(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return image
        conversion = (
            cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        )
        return cv2.cvtColor(image, conversion)

    def _evaluate_candidate(
        self,
        *,
        edges: np.ndarray,
        candle: ClassifiedCandle,
        candidate_id: str,
    ) -> CandleOverlayEvidence:
        candidate = candle.candidate
        cap_ratio = candidate.height / candidate.width
        geometry = candidate.geometry
        wickless = (
            None
            if geometry is None
            else (
                geometry.upper_wick_height == 0
                and geometry.lower_wick_height == 0
            )
        )
        observation = self._find_vertical_line(
            edges=edges,
            x=candidate.x,
            y=candidate.y,
            width=candidate.width,
            height=candidate.height,
        )
        if observation is None:
            return CandleOverlayEvidence(
                candidate_id=candidate_id,
                status=CandleOverlayEvidenceStatus.NOT_EVALUABLE,
                vertical_line_support_ratio=None,
                contact_gap_ratio=None,
                horizontal_alignment_ratio=None,
                cap_height_to_width_ratio=cap_ratio,
                wickless=wickless,
                diagnostic="candidate_has_no_evaluable_space_below",
            )

        is_cap_like = (
            cap_ratio <= self.MAX_CAP_HEIGHT_TO_WIDTH_RATIO
            and wickless is True
        )
        is_long_line = (
            observation.support_ratio
            >= self.MIN_VERTICAL_LINE_SUPPORT_RATIO
        )
        is_in_contact = (
            observation.contact_gap_ratio
            <= self.MAX_LINE_CONTACT_GAP_RATIO
        )
        is_aligned = (
            observation.horizontal_alignment_ratio
            <= self.MAX_HORIZONTAL_ALIGNMENT_RATIO
        )
        is_overlay = is_cap_like and is_long_line and is_in_contact and is_aligned
        diagnostic = (
            "cap_attached_to_long_vertical_line"
            if is_overlay
            else "expiry_overlay_structure_not_detected"
        )
        return CandleOverlayEvidence(
            candidate_id=candidate_id,
            status=(
                CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
                if is_overlay
                else CandleOverlayEvidenceStatus.NO_EVIDENCE
            ),
            vertical_line_support_ratio=observation.support_ratio,
            contact_gap_ratio=observation.contact_gap_ratio,
            horizontal_alignment_ratio=(
                observation.horizontal_alignment_ratio
            ),
            cap_height_to_width_ratio=cap_ratio,
            wickless=wickless,
            diagnostic=diagnostic,
        )

    def _find_vertical_line(
        self,
        *,
        edges: np.ndarray,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> _VerticalLineObservation | None:
        image_height, image_width = edges.shape
        candidate_bottom = y + height
        if candidate_bottom < 0 or candidate_bottom >= image_height:
            return None

        margin = max(1, ceil(width * self.HORIZONTAL_SEARCH_MARGIN_RATIO))
        search_left = max(0, x - margin)
        search_right = min(image_width, x + width + margin)
        if search_left >= search_right:
            return None

        maximum_interruption = max(
            1,
            round(width * self.MAX_VERTICAL_EDGE_INTERRUPTION_RATIO),
        )
        best: tuple[int, int, int] | None = None
        for column_x in range(search_left, search_right):
            active_rows = np.flatnonzero(edges[candidate_bottom:, column_x] > 0)
            run = self._longest_run(
                active_rows=active_rows,
                maximum_interruption=maximum_interruption,
            )
            if run is None:
                continue
            start_y = candidate_bottom + run[0]
            end_y = candidate_bottom + run[1]
            observation = (column_x, start_y, end_y)
            if best is None or self._line_rank(
                observation,
                candidate_bottom=candidate_bottom,
                candidate_left=x,
            ) > self._line_rank(
                best,
                candidate_bottom=candidate_bottom,
                candidate_left=x,
            ):
                best = observation

        if best is None:
            return _VerticalLineObservation(
                support_ratio=0.0,
                contact_gap_ratio=0.0,
                horizontal_alignment_ratio=0.0,
            )
        column_x, start_y, end_y = best
        return _VerticalLineObservation(
            support_ratio=(end_y - start_y + 1) / image_height,
            contact_gap_ratio=(start_y - candidate_bottom) / width,
            horizontal_alignment_ratio=(
                self._horizontal_alignment_distance(
                    column_x=column_x,
                    candidate_left=x,
                )
                / width
            ),
        )

    @staticmethod
    def _longest_run(
        *,
        active_rows: np.ndarray,
        maximum_interruption: int,
    ) -> tuple[int, int] | None:
        if active_rows.size == 0:
            return None
        best_start = current_start = int(active_rows[0])
        best_end = previous = int(active_rows[0])
        for raw_row in active_rows[1:]:
            row = int(raw_row)
            if row - previous - 1 <= maximum_interruption:
                previous = row
            else:
                if previous - current_start > best_end - best_start:
                    best_start, best_end = current_start, previous
                current_start = previous = row
        if previous - current_start > best_end - best_start:
            best_start, best_end = current_start, previous
        return best_start, best_end

    @staticmethod
    def _horizontal_alignment_distance(
        *,
        column_x: int,
        candidate_left: int,
    ) -> int:
        # El icono de expiry se prolonga hacia la derecha desde el stem. Una
        # línea en el borde derecho puede ser simplemente la línea situada
        # después de una candle real y no constituye la misma estructura.
        return abs(column_x - candidate_left)

    @staticmethod
    def _line_rank(
        line: tuple[int, int, int],
        *,
        candidate_bottom: int,
        candidate_left: int,
    ) -> tuple[int, int, int]:
        column_x, start_y, end_y = line
        return (
            end_y - start_y + 1,
            -(start_y - candidate_bottom),
            -PocketOptionExpiryOverlayEvidenceResolver._horizontal_alignment_distance(
                column_x=column_x,
                candidate_left=candidate_left,
            ),
        )
