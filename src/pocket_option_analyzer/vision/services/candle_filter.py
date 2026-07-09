from __future__ import annotations

from collections.abc import Iterable

from pocket_option_analyzer.vision.models import CandleCandidate


class CandleFilter:
    """
    Filtra candidatos visuales para conservar solo objetos que parecen velas.

    Evita que textos, números, etiquetas de precio, marcas de tiempo
    o fragmentos pequeños sean tratados como velas.
    """

    def __init__(
        self,
        min_area: int = 80,
        min_width: int = 3,
        min_height: int = 14,
        max_width: int = 90,
        max_height: int = 700,
        min_aspect_ratio: float = 0.8,
        max_candidates: int = 80,
    ) -> None:
        self._min_area = min_area
        self._min_width = min_width
        self._min_height = min_height
        self._max_width = max_width
        self._max_height = max_height
        self._min_aspect_ratio = min_aspect_ratio
        self._max_candidates = max_candidates

    def filter(
        self,
        candidates: Iterable[CandleCandidate],
    ) -> list[CandleCandidate]:
        """
        Devuelve candidatos filtrados y ordenados de izquierda a derecha.
        """

        filtered = [
            candidate
            for candidate in candidates
            if self._is_candle_like(
                candidate=candidate,
            )
        ]

        filtered.sort(
            key=lambda candidate: candidate.x,
        )

        return filtered[
            -self._max_candidates :
        ]

    def _is_candle_like(
        self,
        candidate: CandleCandidate,
    ) -> bool:

        if candidate.area < self._min_area:
            return False

        if candidate.width < self._min_width:
            return False

        if candidate.height < self._min_height:
            return False

        if candidate.width > self._max_width:
            return False

        if candidate.height > self._max_height:
            return False

        aspect_ratio = candidate.height / max(
            candidate.width,
            1,
        )

        if aspect_ratio < self._min_aspect_ratio:
            return False

        return True