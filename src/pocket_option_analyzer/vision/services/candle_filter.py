from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleDimensionRejectionReason,
    CandleFilterConfigurationTrace,
    CandleFilterDiagnostics,
    CandleFilterResult,
    CandleMergeTrace,
    CandleWidthDecisionReason,
)


@dataclass(slots=True)
class _CandidateTraceState:
    candidate: CandleCandidate
    decisions: list[CandleCandidateDecision]
    dominant_width: float | None = None
    dimension_rejection_reasons: tuple[CandleDimensionRejectionReason, ...] = ()
    width_decision_reason: CandleWidthDecisionReason | None = None
    merged_from: tuple[str, ...] = ()
    merged_into: str | None = None


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
            raise ValueError("min_area debe ser mayor o igual a 1.")

        if min_width < 1 or min_height < 1:
            raise ValueError("Las dimensiones mínimas deben ser mayores o iguales a 1.")

        if max_width < min_width or max_height < min_height:
            raise ValueError(
                "Las dimensiones máximas no pueden ser menores que las mínimas."
            )

        if min_relative_width <= 0:
            raise ValueError("min_relative_width debe ser mayor que cero.")

        if max_relative_width < min_relative_width:
            raise ValueError(
                "max_relative_width no puede ser menor que min_relative_width."
            )

        if width_bucket_size < 1:
            raise ValueError("width_bucket_size debe ser mayor o igual a 1.")

        if not 0 < anchor_min_height_ratio <= 1:
            raise ValueError("anchor_min_height_ratio debe estar entre 0 y 1.")

        if not 0 < same_column_center_ratio <= 1:
            raise ValueError("same_column_center_ratio debe estar entre 0 y 1.")

        if max_candidates < 1:
            raise ValueError("max_candidates debe ser mayor o igual a 1.")

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
        self._last_diagnostics: CandleFilterDiagnostics | None = None

    @property
    def last_diagnostics(
        self,
    ) -> CandleFilterDiagnostics | None:
        """
        Diagnóstico correspondiente a la última ejecución completada.
        """

        return self._last_diagnostics

    def filter(
        self,
        candidates: Iterable[CandleCandidate],
    ) -> list[CandleCandidate]:
        """
        Filtra, fusiona y ordena los candidatos de izquierda a derecha.

        Conserva un diagnóstico de las cantidades observadas en cada etapa
        para permitir auditar la detección sobre capturas reales.
        """

        return list(self.filter_with_trace(candidates).candidates)

    def filter_with_trace(
        self,
        candidates: Iterable[CandleCandidate],
        candidate_ids: Iterable[str] | None = None,
    ) -> CandleFilterResult:
        """Filtra y registra el lifecycle durante la misma pasada."""

        source_candidates = list(candidates)
        resolved_candidate_ids = (
            tuple(candidate_ids)
            if candidate_ids is not None
            else tuple(
                f"candidate_{index:03d}" for index in range(len(source_candidates))
            )
        )
        if len(resolved_candidate_ids) != len(source_candidates):
            raise ValueError("candidate_ids debe estar alineado con candidates.")
        if any(not candidate_id for candidate_id in resolved_candidate_ids):
            raise ValueError("candidate_ids no puede contener IDs vacíos.")
        if len(set(resolved_candidate_ids)) != len(resolved_candidate_ids):
            raise ValueError("candidate_ids debe contener IDs únicos.")

        states = {
            candidate_id: _CandidateTraceState(
                candidate=candidate,
                decisions=[CandleCandidateDecision.SEGMENTED],
            )
            for candidate_id, candidate in zip(
                resolved_candidate_ids,
                source_candidates,
                strict=True,
            )
        }

        dimension_candidates: list[tuple[str, CandleCandidate]] = []
        for candidate_id, candidate in zip(
            resolved_candidate_ids,
            source_candidates,
            strict=True,
        ):
            rejection_reasons = self._dimension_rejection_reasons(candidate=candidate)
            if not rejection_reasons:
                states[candidate_id].decisions.append(
                    CandleCandidateDecision.DIMENSION_ACCEPTED
                )
                dimension_candidates.append((candidate_id, candidate))
            else:
                states[candidate_id].decisions.append(
                    CandleCandidateDecision.REJECTED_DIMENSION
                )
                states[candidate_id].dimension_rejection_reasons = rejection_reasons

        if not dimension_candidates:
            self._last_diagnostics = CandleFilterDiagnostics(
                input_count=len(
                    source_candidates,
                ),
                dimension_valid_count=0,
                width_valid_count=0,
                merged_count=0,
                returned_count=0,
                dominant_width=None,
            )

            return self._result_with_trace(
                candidates=(),
                candidate_ids=(),
                states=states,
                merges=(),
                dominant_width=None,
            )

        dominant_width = self._estimate_dominant_width(
            candidates=[candidate for _, candidate in dimension_candidates],
        )

        width_candidates: list[tuple[str, CandleCandidate]] = []
        for candidate_id, candidate in dimension_candidates:
            state = states[candidate_id]
            state.dominant_width = dominant_width
            width_decision_reason = self._width_decision_reason(
                candidate=candidate,
                dominant_width=dominant_width,
            )
            state.width_decision_reason = width_decision_reason
            if width_decision_reason is not (
                CandleWidthDecisionReason.OUTSIDE_DOMINANT_RANGE
            ):
                state.decisions.append(CandleCandidateDecision.WIDTH_ACCEPTED)
                width_candidates.append((candidate_id, candidate))
            else:
                state.decisions.append(CandleCandidateDecision.REJECTED_WIDTH)

        groups = self._group_same_candle_columns(
            candidates=width_candidates,
            dominant_width=dominant_width,
        )
        maximum_center_distance = dominant_width * self._same_column_center_ratio
        merged_candidates: list[tuple[str, CandleCandidate]] = []
        merge_traces: list[CandleMergeTrace] = []
        merge_index = 0
        for group in groups:
            source_ids = tuple(candidate_id for candidate_id, _ in group)
            group_candidates = [candidate for _, candidate in group]
            merged_candidate = self._merge_group(candidates=group_candidates)
            if len(group) == 1:
                result_id = source_ids[0]
            else:
                result_id = f"merged_{merge_index:03d}"
                merge_index += 1
                while result_id in states:
                    result_id = f"merged_{merge_index:03d}"
                    merge_index += 1
                for source_id in source_ids:
                    states[source_id].decisions.append(CandleCandidateDecision.MERGED)
                    states[source_id].merged_into = result_id
                states[result_id] = _CandidateTraceState(
                    candidate=merged_candidate,
                    decisions=[CandleCandidateDecision.MERGE_RESULT],
                    dominant_width=dominant_width,
                    merged_from=source_ids,
                )
                merge_traces.append(
                    CandleMergeTrace(
                        result_candidate_id=result_id,
                        source_candidate_ids=source_ids,
                        maximum_center_distance=maximum_center_distance,
                    )
                )
            merged_candidates.append((result_id, merged_candidate))

        merged_candidates.sort(
            key=lambda item: item[1].x,
        )

        returned_candidates = merged_candidates[-self._max_candidates :]
        returned_ids = {candidate_id for candidate_id, _ in returned_candidates}
        for candidate_id, _ in merged_candidates:
            decision = (
                CandleCandidateDecision.RETURNED
                if candidate_id in returned_ids
                else CandleCandidateDecision.TRUNCATED
            )
            states[candidate_id].decisions.append(decision)

        self._last_diagnostics = CandleFilterDiagnostics(
            input_count=len(
                source_candidates,
            ),
            dimension_valid_count=len(
                dimension_candidates,
            ),
            width_valid_count=len(
                width_candidates,
            ),
            merged_count=len(
                merged_candidates,
            ),
            returned_count=len(
                returned_candidates,
            ),
            dominant_width=dominant_width,
        )

        return self._result_with_trace(
            candidates=tuple(candidate for _, candidate in returned_candidates),
            candidate_ids=tuple(
                candidate_id for candidate_id, _ in returned_candidates
            ),
            states=states,
            merges=tuple(merge_traces),
            dominant_width=dominant_width,
        )

    def _result_with_trace(
        self,
        *,
        candidates: tuple[CandleCandidate, ...],
        candidate_ids: tuple[str, ...],
        states: dict[str, _CandidateTraceState],
        merges: tuple[CandleMergeTrace, ...],
        dominant_width: float | None,
    ) -> CandleFilterResult:
        trace = CandleDetectionTrace(
            candidates=tuple(
                CandleCandidateTrace(
                    candidate_id=candidate_id,
                    x=state.candidate.x,
                    y=state.candidate.y,
                    width=state.candidate.width,
                    height=state.candidate.height,
                    area=state.candidate.area,
                    color=state.candidate.color,
                    decisions=tuple(state.decisions),
                    dominant_width=state.dominant_width,
                    dimension_rejection_reasons=(state.dimension_rejection_reasons),
                    width_decision_reason=state.width_decision_reason,
                    merged_from=state.merged_from,
                    merged_into=state.merged_into,
                )
                for candidate_id, state in states.items()
            ),
            merges=merges,
            returned_candidate_ids=candidate_ids,
            dominant_width=dominant_width,
            maximum_returned_candidates=self._max_candidates,
            filter_configuration=CandleFilterConfigurationTrace(
                min_area=self._min_area,
                min_width=self._min_width,
                min_height=self._min_height,
                max_width=self._max_width,
                max_height=self._max_height,
                min_relative_width=self._min_relative_width,
                max_relative_width=self._max_relative_width,
                width_bucket_size=self._width_bucket_size,
                anchor_min_height_ratio=self._anchor_min_height_ratio,
                same_column_center_ratio=self._same_column_center_ratio,
                max_candidates=self._max_candidates,
            ),
        )
        return CandleFilterResult(
            candidates=candidates,
            candidate_ids=candidate_ids,
            trace=trace,
        )

    def _has_valid_dimensions(
        self,
        candidate: CandleCandidate,
    ) -> bool:
        return not self._dimension_rejection_reasons(candidate=candidate)

    def _dimension_rejection_reasons(
        self,
        candidate: CandleCandidate,
    ) -> tuple[CandleDimensionRejectionReason, ...]:
        checks = (
            (
                candidate.area < self._min_area,
                CandleDimensionRejectionReason.AREA_BELOW_MINIMUM,
            ),
            (
                candidate.width < self._min_width,
                CandleDimensionRejectionReason.WIDTH_BELOW_MINIMUM,
            ),
            (
                candidate.height < self._min_height,
                CandleDimensionRejectionReason.HEIGHT_BELOW_MINIMUM,
            ),
            (
                candidate.width > self._max_width,
                CandleDimensionRejectionReason.WIDTH_ABOVE_MAXIMUM,
            ),
            (
                candidate.height > self._max_height,
                CandleDimensionRejectionReason.HEIGHT_ABOVE_MAXIMUM,
            ),
        )
        return tuple(reason for failed, reason in checks if failed)

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
                round(candidate.width * self._anchor_min_height_ratio),
            )
        ]

        estimation_candidates = anchor_candidates if anchor_candidates else candidates

        width_groups: dict[int, list[int]] = defaultdict(
            list,
        )

        half_bucket = self._width_bucket_size // 2

        for candidate in estimation_candidates:
            bucket = (
                (candidate.width + half_bucket)
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
        return (
            self._width_decision_reason(
                candidate=candidate,
                dominant_width=dominant_width,
            )
            is not CandleWidthDecisionReason.OUTSIDE_DOMINANT_RANGE
        )

    def _width_decision_reason(
        self,
        candidate: CandleCandidate,
        dominant_width: float,
    ) -> CandleWidthDecisionReason:
        minimum_width = dominant_width * self._min_relative_width
        maximum_width = dominant_width * self._max_relative_width

        if minimum_width <= candidate.width <= maximum_width:
            return CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE

        # La vela ubicada en el borde izquierdo puede estar recortada.
        if (
            candidate.x <= 2
            and candidate.width >= dominant_width * 0.45
            and candidate.width <= maximum_width
        ):
            return CandleWidthDecisionReason.LEFT_EDGE_EXCEPTION

        return CandleWidthDecisionReason.OUTSIDE_DOMINANT_RANGE

    def _merge_same_candle_columns(
        self,
        candidates: list[CandleCandidate],
        dominant_width: float,
    ) -> list[CandleCandidate]:
        """
        Fusiona fragmentos cuyos centros horizontales pertenecen
        prácticamente a la misma columna temporal.
        """

        groups = self._group_same_candle_columns(
            candidates=[
                (str(index), candidate) for index, candidate in enumerate(candidates)
            ],
            dominant_width=dominant_width,
        )
        return [
            self._merge_group(candidates=[candidate for _, candidate in group])
            for group in groups
        ]

    def _group_same_candle_columns(
        self,
        candidates: list[tuple[str, CandleCandidate]],
        dominant_width: float,
    ) -> list[list[tuple[str, CandleCandidate]]]:
        if not candidates:
            return []

        ordered = sorted(
            candidates,
            key=lambda item: (
                self._center_x(
                    candidate=item[1],
                ),
                item[1].y,
            ),
        )

        groups: list[list[tuple[str, CandleCandidate]]] = []

        maximum_center_distance = dominant_width * self._same_column_center_ratio

        for identified_candidate in ordered:
            candidate = identified_candidate[1]
            if not groups:
                groups.append([identified_candidate])
                continue

            previous_group = groups[-1]
            group_center = self._group_center_x(
                candidates=[item[1] for item in previous_group],
            )
            candidate_center = self._center_x(
                candidate=candidate,
            )

            if abs(candidate_center - group_center) <= maximum_center_distance:
                previous_group.append(identified_candidate)
                continue

            groups.append([identified_candidate])

        return groups

    @staticmethod
    def _center_x(
        candidate: CandleCandidate,
    ) -> float:
        return candidate.x + candidate.width / 2

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

        left = min(candidate.x for candidate in candidates)
        top = min(candidate.y for candidate in candidates)
        right = max(candidate.x + candidate.width for candidate in candidates)
        bottom = max(candidate.y + candidate.height for candidate in candidates)

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
