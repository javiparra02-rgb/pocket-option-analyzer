from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from statistics import median

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
)


class CandleFilter:
    """
    Conserva candidatos compatibles con la anchura visual de las velas.

    También fusiona componentes verticalmente separados que pertenecen
    a una misma vela. Esto puede ocurrir cuando una línea horizontal,
    una etiqueta o el suavizado visual corta el cuerpo en varias partes.
    """

    def __init__(
        self,
        min_area: int = 40,
        min_width: int = 3,
        min_height: int = 1,
        max_width: int = 90,
        max_height: int = 700,
        min_relative_width: float = 0.75,
        max_relative_width: float = 1.30,
        width_bucket_size: int = 4,
        anchor_min_height_ratio: float = 0.25,
        same_column_center_ratio: float = 0.20,
        max_candidates: int = 80,
    ) -> None:
        if min_area < 1:
            raise ValueError(
                "min_area debe ser mayor o igual a 1."
            )

        if min_width < 1 or min_height < 1:
            raise ValueError(
                "Las dimensiones mínimas deben ser mayores o iguales a 1."
            )

        if max_width < min_width or max_height < min_height:
            raise ValueError(
                "Las dimensiones máximas no pueden ser menores "
                "que las mínimas."
            )

        if min_relative_width <= 0:
            raise ValueError(
                "min_relative_width debe ser mayor que cero."
            )

        if max_relative_width < min_relative_width:
            raise ValueError(
                "max_relative_width no puede ser menor "
                "que min_relative_width."
            )

        if width_bucket_size < 1:
            raise ValueError(
                "width_bucket_size debe ser mayor o igual a 1."
            )

        if not 0 < anchor_min_height_ratio <= 1:
            raise ValueError(
                "anchor_min_height_ratio debe estar entre 0 y 1."
            )

        if not 0 < same_column_center_ratio <= 1:
            raise ValueError(
                "same_column_center_ratio debe estar entre 0 y 1."
            )

        if max_candidates < 1:
            raise ValueError(
                "max_candidates debe ser mayor o igual a 1."
            )

        self._min_area = min_area
        self._min_width = min_width
        self._min_height = min_height
        self._max_width = max_width
        self._max_height = max_height
        self._min_relative_width = min_relative_width
        self._max_relative_width = max_relative_width
        self._width_bucket_size = width_bucket_size
        self._anchor_min_height_ratio = anchor_min_height_ratio
        self._same_column_center_ratio = same_column_center_ratio
        self._max_candidates = max_candidates

    def filter(
        self,
        candidates: Iterable[CandleCandidate],
    ) -> list[CandleCandidate]:
        """
        Filtra, fusiona y ordena los candidatos de izquierda a derecha.
        """

        dimension_candidates = [
            candidate
            for candidate in candidates
            if self._has_valid_dimensions(
                candidate=candidate,
            )
        ]

        if not dimension_candidates:
            return []

        dominant_width = self._estimate_dominant_width(
            candidates=dimension_candidates,
        )

        width_candidates = [
            candidate
            for candidate in dimension_candidates
            if self._matches_dominant_width(
                candidate=candidate,
                dominant_width=dominant_width,
            )
        ]

        merged_candidates = self._merge_same_candle_columns(
            candidates=width_candidates,
            dominant_width=dominant_width,
        )

        merged_candidates.sort(
            key=lambda candidate: candidate.x,
        )

        return merged_candidates[
            -self._max_candidates:
        ]

    def _has_valid_dimensions(
        self,
        candidate: CandleCandidate,
    ) -> bool:
        return (
            candidate.area >= self._min_area
            and candidate.width >= self._min_width
            and candidate.height >= self._min_height
            and candidate.width <= self._max_width
            and candidate.height <= self._max_height
        )

    def _estimate_dominant_width(
        self,
        candidates: list[CandleCandidate],
    ) -> float:
        """
        Estima la anchura dominante usando candidatos suficientemente altos.

        La puntuación combina frecuencia y anchura. De esta manera, muchos
        caracteres estrechos no desplazan a un grupo menor de cuerpos de vela.
        """

        anchor_candidates = [
            candidate
            for candidate in candidates
            if candidate.height
            >= max(
                3,
                round(
                    candidate.width
                    * self._anchor_min_height_ratio
                ),
            )
        ]

        estimation_candidates = (
            anchor_candidates
            if anchor_candidates
            else candidates
        )

        width_groups: dict[int, list[int]] = defaultdict(
            list,
        )

        half_bucket = self._width_bucket_size // 2

        for candidate in estimation_candidates:
            bucket = (
                (
                    candidate.width
                    + half_bucket
                )
                // self._width_bucket_size
                * self._width_bucket_size
            )

            width_groups[bucket].append(
                candidate.width,
            )

        dominant_group = max(
            width_groups.values(),
            key=lambda widths: (
                len(widths) * median(widths),
                len(widths),
                median(widths),
            ),
        )

        return float(
            median(
                dominant_group,
            )
        )

    def _matches_dominant_width(
        self,
        candidate: CandleCandidate,
        dominant_width: float,
    ) -> bool:
        minimum_width = (
            dominant_width
            * self._min_relative_width
        )
        maximum_width = (
            dominant_width
            * self._max_relative_width
        )

        if (
            minimum_width
            <= candidate.width
            <= maximum_width
        ):
            return True

        # La vela ubicada en el borde izquierdo puede estar recortada.
        return (
            candidate.x <= 2
            and candidate.width
            >= dominant_width * 0.45
            and candidate.width <= maximum_width
        )

    def _merge_same_candle_columns(
        self,
        candidates: list[CandleCandidate],
        dominant_width: float,
    ) -> list[CandleCandidate]:
        """
        Fusiona fragmentos cuyos centros horizontales pertenecen
        prácticamente a la misma columna temporal.
        """

        if not candidates:
            return []

        ordered = sorted(
            candidates,
            key=lambda candidate: (
                self._center_x(
                    candidate=candidate,
                ),
                candidate.y,
            ),
        )

        groups: list[list[CandleCandidate]] = []

        maximum_center_distance = (
            dominant_width
            * self._same_column_center_ratio
        )

        for candidate in ordered:
            if not groups:
                groups.append(
                    [
                        candidate,
                    ]
                )
                continue

            previous_group = groups[-1]
            group_center = self._group_center_x(
                candidates=previous_group,
            )
            candidate_center = self._center_x(
                candidate=candidate,
            )

            if (
                abs(
                    candidate_center
                    - group_center
                )
                <= maximum_center_distance
            ):
                previous_group.append(
                    candidate,
                )
                continue

            groups.append(
                [
                    candidate,
                ]
            )

        return [
            self._merge_group(
                candidates=group,
            )
            for group in groups
        ]

    @staticmethod
    def _center_x(
        candidate: CandleCandidate,
    ) -> float:
        return (
            candidate.x
            + candidate.width / 2
        )

    def _group_center_x(
        self,
        candidates: list[CandleCandidate],
    ) -> float:
        return sum(
            self._center_x(
                candidate=candidate,
            )
            for candidate in candidates
        ) / len(
            candidates,
        )

    @staticmethod
    def _merge_group(
        candidates: list[CandleCandidate],
    ) -> CandleCandidate:
        if len(candidates) == 1:
            return candidates[0]

        left = min(
            candidate.x
            for candidate in candidates
        )
        top = min(
            candidate.y
            for candidate in candidates
        )
        right = max(
            candidate.x + candidate.width
            for candidate in candidates
        )
        bottom = max(
            candidate.y + candidate.height
            for candidate in candidates
        )

        colors = {
            candidate.color
            for candidate in candidates
            if candidate.color is not CandleColor.UNKNOWN
        }

        color = (
            next(
                iter(
                    colors,
                )
            )
            if len(colors) == 1
            else CandleColor.UNKNOWN
        )

        width = right - left
        height = bottom - top

        return CandleCandidate(
            x=left,
            y=top,
            width=width,
            height=height,
            area=width * height,
            color=color,
        )