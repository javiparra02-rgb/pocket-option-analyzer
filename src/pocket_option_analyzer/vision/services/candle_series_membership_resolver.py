from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import ClassVar

from pocket_option_analyzer.vision.models.candle_overlay_evidence import (
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
)
from pocket_option_analyzer.vision.models.candle_series_membership import (
    CandleSeriesExtensionDecision,
    CandleSeriesExtensionTrace,
    CandleSeriesMembershipExclusion,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipGapTrace,
    CandleSeriesMembershipResult,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
)
from pocket_option_analyzer.vision.models.candle_type import CandleType
from pocket_option_analyzer.vision.models.classified_candle import ClassifiedCandle


@dataclass(frozen=True, slots=True)
class _OrderedCandidate:
    candle: ClassifiedCandle
    candidate_id: str
    center_x: float


@dataclass(frozen=True, slots=True)
class _CandidateRun:
    indices: tuple[int, ...]
    separated_by_vertical_discontinuity: bool = False
    boundary_vertical_gap_px: float | None = None


@dataclass(frozen=True, slots=True)
class _GapEvaluation:
    left_index: int
    right_index: int
    horizontal_gap_px: float
    estimated_slot_count: int | None
    horizontal_consistent: bool
    vertical_gap_px: float | None = None
    vertical_continuity_limit_px: float | None = None
    vertical_consistent: bool | None = None


@dataclass(frozen=True, slots=True)
class _FrozenVerticalStatistics:
    median_gap_px: float
    mad_px: float
    body_height_scale_px: float
    robust_allowance_px: float
    body_allowance_px: float
    continuity_limit_px: float


class CandleSeriesMembershipResolver:
    """Resuelve una hipótesis de serie sin modificar el pipeline productivo.

    Todos los umbrales expresan relaciones estructurales. No hay coordenadas ni
    distancias absolutas dependientes de una captura concreta.
    """

    # Cuatro miembros aportan tres intervalos: soporte mínimo para distinguir un
    # run temporal de fragmentos aislados sin depender del tamaño del frame.
    MINIMUM_RUN_SUPPORT: ClassVar[int] = 4
    MINIMUM_PITCH_SAMPLE_COUNT: ClassVar[int] = 2

    # Un gap de una vela se busca alrededor del ancho dominante. El intervalo es
    # deliberadamente amplio para admitir cuerpos algo más estrechos que el pitch.
    MIN_SINGLE_SLOT_WIDTH_RATIO: ClassVar[float] = 0.75
    MAX_SINGLE_SLOT_WIDTH_RATIO: ClassVar[float] = 1.75

    # Un cuarto de slot admite jitter sin unir posiciones intermedias arbitrarias.
    MAX_SLOT_RESIDUAL_RATIO: ClassVar[float] = 0.25
    MAX_SUPPORTED_SLOT_COUNT: ClassVar[int] = 2

    # El run mayor debe superar en 50 % al siguiente para considerarse inequívoco.
    MINIMUM_DOMINANT_SUPPORT_RATIO: ClassVar[float] = 1.5

    # La continuidad vertical usa mediana/MAD del propio run. La envolvente de
    # seis MAD evita reaccionar a gaps ordinarios; dos cuerpos medianos ofrecen
    # una escala estable cuando la dispersión observada es cero.
    VERTICAL_MAD_MULTIPLIER: ClassVar[float] = 6.0
    VERTICAL_BODY_ALLOWANCE_RATIO: ClassVar[float] = 2.0
    MINIMUM_VERTICAL_SAMPLE_COUNT: ClassVar[int] = 3

    def resolve(
        self,
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
        dominant_width: float | None,
        overlay_evidence: CandleOverlayEvidenceTrace | None = None,
    ) -> CandleSeriesMembershipResult:
        """Selecciona un run dominante y conserva evidencia de cada exclusión."""

        self._validate_inputs(
            candles,
            candidate_ids,
            dominant_width,
            overlay_evidence,
        )
        ordered = self._order_candidates(candles, candidate_ids)
        overlay_evidence_by_id = (
            overlay_evidence.by_candidate_id()
            if overlay_evidence is not None
            else {}
        )
        estimated_pitch = self._estimate_pitch(ordered, dominant_width)

        if estimated_pitch is None:
            runs = tuple(_CandidateRun((index,)) for index in range(len(ordered)))
            return self._build_result(
                ordered=ordered,
                gap_evaluations=self._unevaluated_gaps(ordered),
                estimated_pitch=None,
                runs=runs,
                status=CandleSeriesMembershipStatus.INSUFFICIENT_SUPPORT,
                selected_run_index=None,
                diagnostic="insufficient_pitch_support",
                extension_decisions=(),
                overlay_evidence_by_id=overlay_evidence_by_id,
            )

        horizontal_runs, gap_evaluations = self._build_horizontal_runs(
            ordered,
            estimated_pitch,
        )
        runs, gap_evaluations, extension_decisions = self._apply_vertical_cohesion(
            ordered,
            horizontal_runs,
            gap_evaluations,
            estimated_pitch,
            overlay_evidence_by_id,
        )
        status, selected_run_index, diagnostic = self._select_dominant_run(runs)
        return self._build_result(
            ordered=ordered,
            gap_evaluations=gap_evaluations,
            estimated_pitch=estimated_pitch,
            runs=runs,
            status=status,
            selected_run_index=selected_run_index,
            diagnostic=diagnostic,
            extension_decisions=extension_decisions,
            overlay_evidence_by_id=overlay_evidence_by_id,
        )

    @staticmethod
    def _validate_inputs(
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
        dominant_width: float | None,
        overlay_evidence: CandleOverlayEvidenceTrace | None,
    ) -> None:
        if len(candles) != len(candidate_ids):
            raise ValueError("candles y candidate_ids deben estar alineados.")
        if any(not candidate_id for candidate_id in candidate_ids):
            raise ValueError("candidate_ids no puede contener valores vacíos.")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_ids no puede contener duplicados.")
        if dominant_width is not None and (
            not isfinite(dominant_width) or dominant_width <= 0
        ):
            raise ValueError("dominant_width debe ser finito y positivo.")
        if any(candle.candidate.width <= 0 for candle in candles):
            raise ValueError("Todos los candidatos deben tener ancho positivo.")
        if overlay_evidence is not None and (
            overlay_evidence.evaluated_candidate_ids != candidate_ids
        ):
            raise ValueError(
                "overlay_evidence debe estar alineada con candidate_ids."
            )

    @staticmethod
    def _order_candidates(
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
    ) -> tuple[_OrderedCandidate, ...]:
        paired = (
            _OrderedCandidate(
                candle=candle,
                candidate_id=candidate_id,
                center_x=candle.candidate.x + candle.candidate.width / 2.0,
            )
            for candle, candidate_id in zip(candles, candidate_ids, strict=True)
        )
        return tuple(
            sorted(paired, key=lambda item: (item.center_x, item.candidate_id))
        )

    def _estimate_pitch(
        self,
        ordered: tuple[_OrderedCandidate, ...],
        dominant_width: float | None,
    ) -> float | None:
        if len(ordered) < self.MINIMUM_RUN_SUPPORT:
            return None
        reference_width = dominant_width
        if reference_width is None:
            reference_width = float(
                median(item.candle.candidate.width for item in ordered)
            )
        gaps = tuple(
            right.center_x - left.center_x
            for left, right in zip(ordered, ordered[1:], strict=False)
        )
        pitch_samples = tuple(
            gap
            for gap in gaps
            if self.MIN_SINGLE_SLOT_WIDTH_RATIO
            <= gap / reference_width
            <= self.MAX_SINGLE_SLOT_WIDTH_RATIO
        )
        if len(pitch_samples) < self.MINIMUM_PITCH_SAMPLE_COUNT:
            return None
        return float(median(pitch_samples))

    def _build_horizontal_runs(
        self,
        ordered: tuple[_OrderedCandidate, ...],
        estimated_pitch: float,
    ) -> tuple[tuple[_CandidateRun, ...], tuple[_GapEvaluation, ...]]:
        if not ordered:
            return (), ()

        runs: list[_CandidateRun] = []
        current_indices = [0]
        gaps: list[_GapEvaluation] = []
        for left_index in range(len(ordered) - 1):
            right_index = left_index + 1
            horizontal_gap = (
                ordered[right_index].center_x - ordered[left_index].center_x
            )
            slot_count = max(1, round(horizontal_gap / estimated_pitch))
            residual_ratio = abs(
                horizontal_gap - slot_count * estimated_pitch
            ) / estimated_pitch
            is_consistent = (
                slot_count <= self.MAX_SUPPORTED_SLOT_COUNT
                and residual_ratio <= self.MAX_SLOT_RESIDUAL_RATIO
            )
            gaps.append(
                _GapEvaluation(
                    left_index=left_index,
                    right_index=right_index,
                    horizontal_gap_px=horizontal_gap,
                    estimated_slot_count=slot_count,
                    horizontal_consistent=is_consistent,
                )
            )
            if is_consistent:
                current_indices.append(right_index)
            else:
                runs.append(_CandidateRun(tuple(current_indices)))
                current_indices = [right_index]
        runs.append(_CandidateRun(tuple(current_indices)))
        return tuple(runs), tuple(gaps)

    def _apply_vertical_cohesion(
        self,
        ordered: tuple[_OrderedCandidate, ...],
        horizontal_runs: tuple[_CandidateRun, ...],
        gap_evaluations: tuple[_GapEvaluation, ...],
        estimated_pitch: float,
        overlay_evidence_by_id: dict[str, CandleOverlayEvidence],
    ) -> tuple[
        tuple[_CandidateRun, ...],
        tuple[_GapEvaluation, ...],
        tuple[CandleSeriesExtensionTrace, ...],
    ]:
        updated_gaps = list(gap_evaluations)
        refined_runs: list[_CandidateRun] = []
        extension_decisions: list[CandleSeriesExtensionTrace] = []
        for horizontal_run in horizontal_runs:
            current_indices: list[int] = []
            detached_overlay_runs: list[_CandidateRun] = []
            current_separated = horizontal_run.separated_by_vertical_discontinuity
            current_boundary_gap = horizontal_run.boundary_vertical_gap_px
            for candidate_index in horizontal_run.indices:
                evidence = overlay_evidence_by_id.get(
                    ordered[candidate_index].candidate_id
                )
                is_expiry_overlay = (
                    evidence is not None
                    and evidence.status
                    is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
                )
                if not current_indices:
                    if is_expiry_overlay:
                        detached_overlay_runs.append(
                            _CandidateRun((candidate_index,))
                        )
                    else:
                        current_indices = [candidate_index]
                    continue

                left_index = current_indices[-1]
                vertical_gap = self._vertical_gap(
                    ordered[left_index].candle,
                    ordered[candidate_index].candle,
                )
                statistics = self._frozen_vertical_statistics(
                    ordered,
                    tuple(current_indices),
                )
                if is_expiry_overlay:
                    if statistics is not None:
                        self._update_gap_evaluation(
                            updated_gaps,
                            left_index=left_index,
                            right_index=candidate_index,
                            vertical_gap=vertical_gap,
                            continuity_limit=statistics.continuity_limit_px,
                        )
                        extension_decisions.append(
                            self._extension_trace(
                                ordered=ordered,
                                candidate_index=candidate_index,
                                core_indices=tuple(current_indices),
                                estimated_pitch=estimated_pitch,
                                statistics=statistics,
                                vertical_gap=vertical_gap,
                                overlay_status=evidence.status,
                                decision=(
                                    CandleSeriesExtensionDecision.EXCLUDED_EXPIRY_OVERLAY
                                ),
                                exclusion_reason=(
                                    CandleSeriesMembershipExclusionReason.EXPIRY_OVERLAY
                                ),
                            )
                        )
                    detached_overlay_runs.append(
                        _CandidateRun((candidate_index,))
                    )
                    continue

                if statistics is None:
                    # El seed confiable mínimo coincide con el soporte mínimo
                    # ya aprobado: cuatro miembros horizontales aportan tres
                    # gaps observables. Ninguna extensión posterior participa
                    # en las estadísticas usadas para evaluarse a sí misma.
                    current_indices.append(candidate_index)
                    seed_statistics = self._frozen_vertical_statistics(
                        ordered,
                        tuple(current_indices),
                    )
                    if seed_statistics is not None:
                        self._record_seed_gaps(
                            updated_gaps,
                            ordered=ordered,
                            indices=tuple(current_indices),
                            statistics=seed_statistics,
                        )
                    continue

                is_consistent = (
                    vertical_gap is None
                    or vertical_gap <= statistics.continuity_limit_px
                )
                self._update_gap_evaluation(
                    updated_gaps,
                    left_index=left_index,
                    right_index=candidate_index,
                    vertical_gap=vertical_gap,
                    continuity_limit=statistics.continuity_limit_px,
                )
                decision = (
                    CandleSeriesExtensionDecision.ACCEPTED
                    if is_consistent
                    else CandleSeriesExtensionDecision.EXCLUDED_VERTICAL_DISCONTINUITY
                )
                exclusion_reason = (
                    None
                    if is_consistent
                    else CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
                )
                extension_decisions.append(
                    self._extension_trace(
                        ordered=ordered,
                        candidate_index=candidate_index,
                        core_indices=tuple(current_indices),
                        estimated_pitch=estimated_pitch,
                        statistics=statistics,
                        vertical_gap=vertical_gap,
                        overlay_status=(
                            evidence.status
                            if evidence is not None
                            else CandleOverlayEvidenceStatus.NOT_EVALUABLE
                        ),
                        decision=decision,
                        exclusion_reason=exclusion_reason,
                    )
                )
                if is_consistent:
                    current_indices.append(candidate_index)
                    continue

                refined_runs.append(
                    _CandidateRun(
                        indices=tuple(current_indices),
                        separated_by_vertical_discontinuity=current_separated,
                        boundary_vertical_gap_px=current_boundary_gap,
                    )
                )
                current_indices = [candidate_index]
                current_separated = True
                current_boundary_gap = vertical_gap

            if current_indices:
                refined_runs.append(
                    _CandidateRun(
                        indices=tuple(current_indices),
                        separated_by_vertical_discontinuity=current_separated,
                        boundary_vertical_gap_px=current_boundary_gap,
                    )
                )
            refined_runs.extend(detached_overlay_runs)
        return (
            tuple(refined_runs),
            tuple(updated_gaps),
            tuple(extension_decisions),
        )

    def _frozen_vertical_statistics(
        self,
        ordered: tuple[_OrderedCandidate, ...],
        indices: tuple[int, ...],
    ) -> _FrozenVerticalStatistics | None:
        observable_gaps = tuple(
            gap
            for left_index, right_index in zip(
                indices,
                indices[1:],
                strict=False,
            )
            if (
                gap := self._vertical_gap(
                    ordered[left_index].candle,
                    ordered[right_index].candle,
                )
            )
            is not None
        )
        if len(observable_gaps) < self.MINIMUM_VERTICAL_SAMPLE_COUNT:
            return None
        median_gap = float(median(observable_gaps))
        median_absolute_deviation = float(
            median(abs(gap - median_gap) for gap in observable_gaps)
        )
        body_heights = tuple(
            ordered[index].candle.candidate.geometry.body_height
            for index in indices
            if ordered[index].candle.candidate.geometry is not None
            and ordered[index].candle.candle_type
            in (CandleType.BULLISH, CandleType.BEARISH)
        )
        body_height_scale = (
            float(median(body_heights)) if body_heights else 0.0
        )
        body_allowance = (
            body_height_scale * self.VERTICAL_BODY_ALLOWANCE_RATIO
        )
        robust_allowance = (
            median_gap
            + self.VERTICAL_MAD_MULTIPLIER * median_absolute_deviation
        )
        # Se conserva la protección histórica de cuerpos grandes porque el
        # replay de autoescala contiene aperturas legítimas por encima de la
        # envolvente MAD. La diferencia es que ahora también procede solo del
        # core congelado; el cuerpo de la extensión no puede inflarla.
        return _FrozenVerticalStatistics(
            median_gap_px=median_gap,
            mad_px=median_absolute_deviation,
            body_height_scale_px=body_height_scale,
            robust_allowance_px=robust_allowance,
            body_allowance_px=body_allowance,
            continuity_limit_px=max(body_allowance, robust_allowance),
        )

    def _record_seed_gaps(
        self,
        updated_gaps: list[_GapEvaluation],
        *,
        ordered: tuple[_OrderedCandidate, ...],
        indices: tuple[int, ...],
        statistics: _FrozenVerticalStatistics,
    ) -> None:
        for left_index, right_index in zip(
            indices,
            indices[1:],
            strict=False,
        ):
            self._update_gap_evaluation(
                updated_gaps,
                left_index=left_index,
                right_index=right_index,
                vertical_gap=self._vertical_gap(
                    ordered[left_index].candle,
                    ordered[right_index].candle,
                ),
                continuity_limit=statistics.continuity_limit_px,
            )

    @staticmethod
    def _update_gap_evaluation(
        updated_gaps: list[_GapEvaluation],
        *,
        left_index: int,
        right_index: int,
        vertical_gap: float | None,
        continuity_limit: float,
    ) -> None:
        if vertical_gap is None:
            return
        gap_position = next(
            (
                index
                for index, gap in enumerate(updated_gaps)
                if gap.left_index == left_index and gap.right_index == right_index
            ),
            None,
        )
        if gap_position is None:
            return
        existing = updated_gaps[gap_position]
        updated_gaps[gap_position] = _GapEvaluation(
            left_index=existing.left_index,
            right_index=existing.right_index,
            horizontal_gap_px=existing.horizontal_gap_px,
            estimated_slot_count=existing.estimated_slot_count,
            horizontal_consistent=existing.horizontal_consistent,
            vertical_gap_px=vertical_gap,
            vertical_continuity_limit_px=continuity_limit,
            vertical_consistent=vertical_gap <= continuity_limit,
        )

    @staticmethod
    def _extension_trace(
        *,
        ordered: tuple[_OrderedCandidate, ...],
        candidate_index: int,
        core_indices: tuple[int, ...],
        estimated_pitch: float,
        statistics: _FrozenVerticalStatistics,
        vertical_gap: float | None,
        overlay_status: CandleOverlayEvidenceStatus,
        decision: CandleSeriesExtensionDecision,
        exclusion_reason: CandleSeriesMembershipExclusionReason | None,
    ) -> CandleSeriesExtensionTrace:
        return CandleSeriesExtensionTrace(
            candidate_id=ordered[candidate_index].candidate_id,
            core_candidate_ids=tuple(
                ordered[index].candidate_id for index in core_indices
            ),
            frozen_pitch_px=estimated_pitch,
            frozen_vertical_median_gap_px=statistics.median_gap_px,
            frozen_vertical_mad_px=statistics.mad_px,
            frozen_body_height_scale_px=statistics.body_height_scale_px,
            frozen_robust_allowance_px=statistics.robust_allowance_px,
            frozen_body_allowance_px=statistics.body_allowance_px,
            frozen_vertical_continuity_limit_px=(
                statistics.continuity_limit_px
            ),
            candidate_vertical_gap_px=vertical_gap,
            overlay_evidence_status=overlay_status,
            decision=decision,
            exclusion_reason=exclusion_reason,
        )

    @staticmethod
    def _vertical_gap(
        left: ClassifiedCandle,
        right: ClassifiedCandle,
    ) -> float | None:
        left_prices = CandleSeriesMembershipResolver._open_close_y(left)
        right_prices = CandleSeriesMembershipResolver._open_close_y(right)
        if left_prices is None or right_prices is None:
            return None
        _, left_close = left_prices
        right_open, _ = right_prices
        return float(abs(right_open - left_close))

    @staticmethod
    def _open_close_y(candle: ClassifiedCandle) -> tuple[int, int] | None:
        geometry = candle.candidate.geometry
        if geometry is None:
            return None
        if candle.candle_type is CandleType.BULLISH:
            return geometry.body_bottom_y, geometry.body_top_y
        if candle.candle_type is CandleType.BEARISH:
            return geometry.body_top_y, geometry.body_bottom_y
        return None

    def _select_dominant_run(
        self,
        runs: tuple[_CandidateRun, ...],
    ) -> tuple[CandleSeriesMembershipStatus, int | None, str]:
        ranked = sorted(
            enumerate(runs),
            key=lambda item: (-len(item[1].indices), item[1].indices[0]),
        )
        if not ranked or len(ranked[0][1].indices) < self.MINIMUM_RUN_SUPPORT:
            return (
                CandleSeriesMembershipStatus.INSUFFICIENT_SUPPORT,
                None,
                "no_run_reaches_minimum_support",
            )
        selected_index, selected_run = ranked[0]
        if len(ranked) > 1:
            next_support = len(ranked[1][1].indices)
            if (
                len(selected_run.indices)
                < next_support * self.MINIMUM_DOMINANT_SUPPORT_RATIO
            ):
                return (
                    CandleSeriesMembershipStatus.AMBIGUOUS,
                    None,
                    "multiple_runs_have_similar_support",
                )
        return (
            CandleSeriesMembershipStatus.AVAILABLE,
            selected_index,
            "dominant_supported_run_selected",
        )

    def _build_result(
        self,
        *,
        ordered: tuple[_OrderedCandidate, ...],
        gap_evaluations: tuple[_GapEvaluation, ...],
        estimated_pitch: float | None,
        runs: tuple[_CandidateRun, ...],
        status: CandleSeriesMembershipStatus,
        selected_run_index: int | None,
        diagnostic: str,
        extension_decisions: tuple[CandleSeriesExtensionTrace, ...],
        overlay_evidence_by_id: dict[str, CandleOverlayEvidence],
    ) -> CandleSeriesMembershipResult:
        selected_indices = (
            runs[selected_run_index].indices if selected_run_index is not None else ()
        )
        run_traces = tuple(
            CandleSeriesMembershipRunTrace(
                run_id=f"run_{run_index:03d}",
                candidate_ids=tuple(
                    ordered[index].candidate_id for index in run.indices
                ),
                selected=run_index == selected_run_index,
                separated_by_vertical_discontinuity=(
                    run.separated_by_vertical_discontinuity
                ),
            )
            for run_index, run in enumerate(runs)
        )
        member_ids = tuple(ordered[index].candidate_id for index in selected_indices)
        excluded = self._build_exclusions(
            ordered,
            runs,
            selected_run_index,
            overlay_evidence_by_id,
        )
        gap_traces = tuple(
            CandleSeriesMembershipGapTrace(
                left_candidate_id=ordered[gap.left_index].candidate_id,
                right_candidate_id=ordered[gap.right_index].candidate_id,
                horizontal_gap_px=gap.horizontal_gap_px,
                estimated_slot_count=gap.estimated_slot_count,
                horizontal_consistent=gap.horizontal_consistent,
                vertical_gap_px=gap.vertical_gap_px,
                vertical_continuity_limit_px=gap.vertical_continuity_limit_px,
                vertical_consistent=gap.vertical_consistent,
            )
            for gap in gap_evaluations
        )
        trace = CandleSeriesMembershipTrace(
            status=status,
            evaluated_candidate_ids=tuple(item.candidate_id for item in ordered),
            member_candidate_ids=member_ids,
            excluded_candidates=excluded,
            evaluated_gaps=gap_traces,
            estimated_pitch_px=estimated_pitch,
            candidate_runs=run_traces,
            selected_run_support=len(selected_indices),
            latest_candidate_id=member_ids[-1] if member_ids else None,
            diagnostic=diagnostic,
            extension_decisions=extension_decisions,
        )
        return CandleSeriesMembershipResult(
            candles=tuple(ordered[index].candle for index in selected_indices),
            candidate_ids=member_ids,
            trace=trace,
        )

    @staticmethod
    def _build_exclusions(
        ordered: tuple[_OrderedCandidate, ...],
        runs: tuple[_CandidateRun, ...],
        selected_run_index: int | None,
        overlay_evidence_by_id: dict[str, CandleOverlayEvidence],
    ) -> tuple[CandleSeriesMembershipExclusion, ...]:
        selected_indices = (
            runs[selected_run_index].indices if selected_run_index is not None else ()
        )
        selected_centers = tuple(ordered[index].center_x for index in selected_indices)
        exclusions: list[CandleSeriesMembershipExclusion] = []
        for run_index, run in enumerate(runs):
            if run_index == selected_run_index:
                continue
            if any(
                overlay_evidence_by_id.get(ordered[index].candidate_id)
                is not None
                and overlay_evidence_by_id[
                    ordered[index].candidate_id
                ].status
                is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
                for index in run.indices
            ):
                reason = CandleSeriesMembershipExclusionReason.EXPIRY_OVERLAY
                reason_diagnostic = "candidate_matches_expiry_cap_on_line"
            elif run.separated_by_vertical_discontinuity:
                reason = CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
                reason_diagnostic = "run_split_by_open_close_discontinuity"
            elif len(run.indices) == 1:
                reason = CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
                reason_diagnostic = "candidate_isolated_from_supported_lattice"
            else:
                reason = CandleSeriesMembershipExclusionReason.NOT_SELECTED_CLUSTER
                reason_diagnostic = "run_not_selected_by_support_consensus"
            for index in run.indices:
                horizontal_gap = (
                    min(
                        abs(ordered[index].center_x - center)
                        for center in selected_centers
                    )
                    if selected_centers
                    else None
                )
                exclusions.append(
                    CandleSeriesMembershipExclusion(
                        candidate_id=ordered[index].candidate_id,
                        reason=reason,
                        horizontal_gap_px=horizontal_gap,
                        vertical_gap_px=run.boundary_vertical_gap_px,
                        diagnostic=reason_diagnostic,
                    )
                )
        return tuple(exclusions)

    @staticmethod
    def _unevaluated_gaps(
        ordered: tuple[_OrderedCandidate, ...],
    ) -> tuple[_GapEvaluation, ...]:
        return tuple(
            _GapEvaluation(
                left_index=index,
                right_index=index + 1,
                horizontal_gap_px=(
                    ordered[index + 1].center_x - ordered[index].center_x
                ),
                estimated_slot_count=None,
                horizontal_consistent=False,
            )
            for index in range(len(ordered) - 1)
        )
