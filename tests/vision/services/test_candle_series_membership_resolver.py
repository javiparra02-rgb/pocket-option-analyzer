from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace
from typing import get_type_hints

import pytest

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleGeometry,
    CandleSeriesMembershipExclusion,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipGapTrace,
    CandleSeriesMembershipResult,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services import CandleSeriesMembershipResolver


@dataclass(frozen=True, slots=True)
class _DerivedFixture:
    source: str
    frame_key: str
    derived_fields: tuple[str, ...]
    candles: tuple[ClassifiedCandle, ...]
    candidate_ids: tuple[str, ...]
    real_latest_candidate_id: str
    flag_candidate_id: str
    text_candidate_id: str | None = None


def _candle(
    *,
    x: int,
    open_y: int,
    close_y: int,
    width: int = 8,
    upper_wick: int = 2,
    lower_wick: int = 2,
    candle_type: CandleType | None = None,
) -> ClassifiedCandle:
    resolved_type = candle_type
    if resolved_type is None:
        resolved_type = (
            CandleType.BULLISH if close_y < open_y else CandleType.BEARISH
        )
    body_top_y = min(open_y, close_y)
    body_bottom_y = max(open_y, close_y)
    high_y = body_top_y - upper_wick
    low_y = body_bottom_y + lower_wick
    height = low_y - high_y + 1
    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=high_y,
            width=width,
            height=height,
            area=width * height,
            color=(
                CandleColor.WHITE
                if resolved_type is CandleType.BULLISH
                else CandleColor.RED
            ),
            geometry=CandleGeometry(
                high_y=high_y,
                body_top_y=body_top_y,
                body_bottom_y=body_bottom_y,
                low_y=low_y,
            ),
        ),
        candle_type=resolved_type,
    )


def _series(
    count: int = 6,
    *,
    start_x: int = 10,
    pitch: int = 12,
    width: int = 8,
    start_y: int = 100,
) -> tuple[tuple[ClassifiedCandle, ...], tuple[str, ...]]:
    prices = [start_y]
    for index in range(count):
        movement = -8 if index % 2 == 0 else 8
        prices.append(prices[-1] + movement)
    candles = tuple(
        _candle(
            x=start_x + index * pitch,
            open_y=prices[index],
            close_y=prices[index + 1],
            width=width,
        )
        for index in range(count)
    )
    return candles, tuple(f"candle_{index:02d}" for index in range(count))


def _trace_candle(
    *,
    x: int,
    width: int,
    high_y: int,
    body_top_y: int,
    body_bottom_y: int,
    low_y: int,
    candle_type: CandleType,
) -> ClassifiedCandle:
    color = (
        CandleColor.WHITE
        if candle_type is CandleType.BULLISH
        else CandleColor.RED
    )
    height = low_y - high_y + 1
    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=high_y,
            width=width,
            height=height,
            area=width * height,
            color=color,
            geometry=CandleGeometry(
                high_y=high_y,
                body_top_y=body_top_y,
                body_bottom_y=body_bottom_y,
                low_y=low_y,
            ),
        ),
        candle_type=candle_type,
    )


def _session_02_flag_fixture() -> _DerivedFixture:
    # P0.4b session 02, frame_00000001_20260817T231512716023Z.
    # Reducción exacta de x/width y OHLC-y de las últimas seis candles reales y
    # candidate_080 (bandera) conservados en analysis.candle_detection_trace.
    rows = (
        (566, 21, 177, 177, 270, 270, CandleType.BULLISH),
        (591, 22, 177, 177, 213, 251, CandleType.BEARISH),
        (617, 22, 197, 209, 219, 273, CandleType.BEARISH),
        (642, 22, 159, 197, 226, 270, CandleType.BULLISH),
        (668, 22, 123, 187, 200, 203, CandleType.BEARISH),
        (694, 21, 159, 192, 197, 199, CandleType.BULLISH),
        (722, 19, 11, 11, 22, 22, CandleType.BULLISH),
    )
    candidate_ids = (
        "candidate_032",
        "candidate_031",
        "candidate_026",
        "candidate_034",
        "candidate_038",
        "candidate_033",
        "candidate_080",
    )
    return _DerivedFixture(
        source="P0.4b session 02",
        frame_key="frame_00000001_20260817T231512716023Z",
        derived_fields=(
            "candidate_id",
            "x",
            "width",
            "high_y",
            "body_top_y",
            "body_bottom_y",
            "low_y",
            "candle_type",
        ),
        candles=tuple(
            _trace_candle(
                x=row[0],
                width=row[1],
                high_y=row[2],
                body_top_y=row[3],
                body_bottom_y=row[4],
                low_y=row[5],
                candle_type=row[6],
            )
            for row in rows
        ),
        candidate_ids=candidate_ids,
        real_latest_candidate_id="candidate_033",
        flag_candidate_id="candidate_080",
    )


def _session_02_flag_and_text_fixture() -> _DerivedFixture:
    # P0.4b session 02, frame_00000011_20260817T231523395322Z.
    # Reducción exacta de x/width y OHLC-y de las últimas seis candles reales,
    # candidate_081 (bandera) y candidate_030 (fragmento de texto de precio).
    rows = (
        (566, 21, 177, 177, 270, 270, CandleType.BULLISH),
        (591, 22, 177, 177, 213, 251, CandleType.BEARISH),
        (617, 22, 197, 209, 219, 273, CandleType.BEARISH),
        (642, 22, 159, 197, 226, 270, CandleType.BULLISH),
        (668, 22, 123, 187, 200, 203, CandleType.BEARISH),
        (694, 21, 159, 175, 197, 206, CandleType.BULLISH),
        (732, 19, 11, 11, 22, 22, CandleType.BULLISH),
        (1040, 20, 170, 174, 179, 179, CandleType.BULLISH),
    )
    candidate_ids = (
        "candidate_028",
        "candidate_027",
        "candidate_026",
        "candidate_035",
        "candidate_039",
        "candidate_034",
        "candidate_081",
        "candidate_030",
    )
    return _DerivedFixture(
        source="P0.4b session 02",
        frame_key="frame_00000011_20260817T231523395322Z",
        derived_fields=(
            "candidate_id",
            "x",
            "width",
            "high_y",
            "body_top_y",
            "body_bottom_y",
            "low_y",
            "candle_type",
        ),
        candles=tuple(
            _trace_candle(
                x=row[0],
                width=row[1],
                high_y=row[2],
                body_top_y=row[3],
                body_bottom_y=row[4],
                low_y=row[5],
                candle_type=row[6],
            )
            for row in rows
        ),
        candidate_ids=candidate_ids,
        real_latest_candidate_id="candidate_034",
        flag_candidate_id="candidate_081",
        text_candidate_id="candidate_030",
    )


def _resolve(
    candles: tuple[ClassifiedCandle, ...],
    candidate_ids: tuple[str, ...],
    dominant_width: float | None = 8.0,
) -> CandleSeriesMembershipResult:
    return CandleSeriesMembershipResolver().resolve(
        candles,
        candidate_ids,
        dominant_width,
    )


def _exclusion_map(
    result: CandleSeriesMembershipResult,
) -> dict[str, CandleSeriesMembershipExclusion]:
    return {
        exclusion.candidate_id: exclusion
        for exclusion in result.trace.excluded_candidates
    }


def _combine_runs(
    left_count: int,
    right_count: int,
    *,
    cluster_gap: int = 60,
) -> tuple[tuple[ClassifiedCandle, ...], tuple[str, ...]]:
    left, _ = _series(left_count, start_x=0)
    right, _ = _series(right_count, start_x=cluster_gap, start_y=180)
    ids = tuple(f"left_{index}" for index in range(left_count)) + tuple(
        f"right_{index}" for index in range(right_count)
    )
    return left + right, ids


def _transform(
    candles: tuple[ClassifiedCandle, ...],
    *,
    x_scale: int = 1,
    x_shift: int = 0,
    y_scale: int = 1,
    y_shift: int = 0,
) -> tuple[ClassifiedCandle, ...]:
    transformed: list[ClassifiedCandle] = []
    for candle in candles:
        candidate = candle.candidate
        geometry = candidate.geometry
        assert geometry is not None
        transformed_geometry = CandleGeometry(
            high_y=geometry.high_y * y_scale + y_shift,
            body_top_y=geometry.body_top_y * y_scale + y_shift,
            body_bottom_y=geometry.body_bottom_y * y_scale + y_shift,
            low_y=geometry.low_y * y_scale + y_shift,
        )
        width = candidate.width * x_scale
        height = transformed_geometry.total_height
        transformed.append(
            ClassifiedCandle(
                candidate=replace(
                    candidate,
                    x=candidate.x * x_scale + x_shift,
                    y=transformed_geometry.high_y,
                    width=width,
                    height=height,
                    area=width * height,
                    geometry=transformed_geometry,
                ),
                candle_type=candle.candle_type,
            )
        )
    return tuple(transformed)


def test_clean_series_is_available_ordered_and_has_expected_latest() -> None:
    candles, candidate_ids = _series()
    result = _resolve(tuple(reversed(candles)), tuple(reversed(candidate_ids)))

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == candidate_ids
    assert result.candles == candles
    assert result.trace.latest_candidate_id == candidate_ids[-1]
    assert result.trace.selected_run_support == len(candles)


def test_resolve_rejects_misaligned_candidate_ids() -> None:
    candles, candidate_ids = _series()

    with pytest.raises(ValueError, match="alineados"):
        _resolve(candles, candidate_ids[:-1])


def test_resolve_rejects_duplicate_candidate_ids() -> None:
    candles, candidate_ids = _series()

    with pytest.raises(ValueError, match="duplicados"):
        _resolve(candles, candidate_ids[:-1] + (candidate_ids[0],))


def test_session_02_flag_fixture_preserves_real_latest_and_excludes_flag() -> None:
    fixture = _session_02_flag_fixture()
    result = _resolve(fixture.candles, fixture.candidate_ids, dominant_width=22.0)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id
    assert fixture.flag_candidate_id not in result.candidate_ids
    assert _exclusion_map(result)[fixture.flag_candidate_id].reason is (
        CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
    )


def test_session_02_flag_and_text_fixture_excludes_both_contaminants() -> None:
    fixture = _session_02_flag_and_text_fixture()
    result = _resolve(fixture.candles, fixture.candidate_ids, dominant_width=22.0)
    exclusions = _exclusion_map(result)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id
    assert fixture.flag_candidate_id not in result.candidate_ids
    assert fixture.text_candidate_id not in result.candidate_ids
    assert exclusions[fixture.flag_candidate_id].reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )
    assert exclusions[fixture.text_candidate_id].reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


@pytest.mark.parametrize(
    ("count", "expected_type"),
    ((5, CandleType.BULLISH), (6, CandleType.BEARISH)),
)
def test_latest_real_candle_type_is_preserved(
    count: int,
    expected_type: CandleType,
) -> None:
    candles, candidate_ids = _series(count)

    result = _resolve(candles, candidate_ids)

    assert result.candles[-1].candle_type is expected_type
    assert result.trace.latest_candidate_id == candidate_ids[-1]


def test_small_real_candle_is_preserved() -> None:
    prices = (100, 92, 100, 99, 107, 99, 107)
    candles = tuple(
        _candle(x=10 + index * 12, open_y=prices[index], close_y=prices[index + 1])
        for index in range(6)
    )
    ids = tuple(f"candidate_{index}" for index in range(6))

    result = _resolve(candles, ids)

    assert ids[2] in result.candidate_ids
    assert candles[2].candidate.geometry is not None
    assert candles[2].candidate.geometry.body_height == 2


def test_large_wick_real_candle_is_preserved() -> None:
    candles, ids = _series()
    original = candles[3]
    geometry = original.candidate.geometry
    assert geometry is not None
    long_wick_geometry = replace(
        geometry,
        high_y=geometry.high_y - 60,
        low_y=geometry.low_y + 60,
    )
    long_wick = replace(
        original,
        candidate=replace(
            original.candidate,
            y=long_wick_geometry.high_y,
            height=long_wick_geometry.total_height,
            area=original.candidate.width * long_wick_geometry.total_height,
            geometry=long_wick_geometry,
        ),
    )
    changed = candles[:3] + (long_wick,) + candles[4:]

    result = _resolve(changed, ids)

    assert ids[3] in result.candidate_ids


def test_reasonable_breakout_gap_is_not_automatically_discarded() -> None:
    candles = (
        _candle(x=0, open_y=100, close_y=90),
        _candle(x=12, open_y=90, close_y=100),
        _candle(x=24, open_y=100, close_y=90),
        _candle(x=36, open_y=105, close_y=90),
        _candle(x=48, open_y=90, close_y=100),
    )
    ids = tuple(f"candidate_{index}" for index in range(len(candles)))

    result = _resolve(candles, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids


def test_pitch_estimation_tolerates_small_jitter() -> None:
    candles, ids = _series(5, start_x=0, pitch=10)
    jittered_x = (0, 10, 21, 30, 40)
    jittered = tuple(
        replace(candle, candidate=replace(candle.candidate, x=x))
        for candle, x in zip(candles, jittered_x, strict=True)
    )

    result = _resolve(jittered, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids


def test_one_missing_slot_keeps_a_single_run() -> None:
    candles, ids = _series(5, start_x=0, pitch=10)
    x_positions = (0, 10, 30, 40, 50)
    with_missing_slot = tuple(
        replace(candle, candidate=replace(candle.candidate, x=x))
        for candle, x in zip(candles, x_positions, strict=True)
    )

    result = _resolve(with_missing_slot, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids
    assert any(gap.estimated_slot_count == 2 for gap in result.trace.evaluated_gaps)


def test_slot_residual_at_inclusive_boundary_remains_in_run() -> None:
    candles, ids = _series(6, start_x=0, pitch=10)
    fifth = replace(
        candles[4],
        candidate=replace(candles[4].candidate, x=42, width=9),
    )
    sixth = replace(
        candles[5],
        candidate=replace(candles[5].candidate, x=52, width=9),
    )
    at_boundary = candles[:4] + (fifth, sixth)

    result = _resolve(at_boundary, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids


def test_slot_residual_beyond_boundary_splits_candidate_run() -> None:
    candles, ids = _series(6, start_x=0, pitch=10)
    beyond_boundary = candles[:4] + tuple(
        replace(
            candle,
            candidate=replace(candle.candidate, x=x),
        )
        for candle, x in zip(candles[4:], (43, 53), strict=True)
    )

    result = _resolve(beyond_boundary, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids[:4]


def test_isolated_horizontal_candidate_is_excluded() -> None:
    candles, ids = _series()
    outlier = _candle(x=180, open_y=100, close_y=92)

    result = _resolve(candles + (outlier,), ids + ("text",))

    assert _exclusion_map(result)["text"].reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


@pytest.mark.parametrize("scale", (2, 3))
def test_scaled_spacing_preserves_membership(scale: int) -> None:
    fixture = _session_02_flag_fixture()
    transformed = _transform(fixture.candles, x_scale=scale, x_shift=37)

    result = _resolve(
        transformed,
        fixture.candidate_ids,
        dominant_width=22.0 * scale,
    )

    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id
    assert fixture.flag_candidate_id not in result.candidate_ids


def test_horizontally_plausible_vertical_contaminant_is_excluded() -> None:
    candles, ids = _series()
    next_x = candles[-1].candidate.x + 12
    flag = _candle(x=next_x, open_y=25, close_y=15)

    result = _resolve(candles + (flag,), ids + ("flag",))
    exclusion = _exclusion_map(result)["flag"]

    assert exclusion.reason is (
        CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
    )
    assert exclusion.vertical_gap_px is not None


def test_vertical_translation_preserves_membership() -> None:
    fixture = _session_02_flag_fixture()
    translated = _transform(fixture.candles, y_shift=500)

    result = _resolve(translated, fixture.candidate_ids, dominant_width=22.0)

    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id
    assert fixture.flag_candidate_id not in result.candidate_ids


def test_equivalent_clusters_are_ambiguous_and_return_no_members() -> None:
    candles, ids = _combine_runs(4, 4)

    result = _resolve(candles, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AMBIGUOUS
    assert result.candles == ()
    assert result.candidate_ids == ()
    assert result.trace.latest_candidate_id is None


def test_similar_clusters_are_ambiguous() -> None:
    candles, ids = _combine_runs(5, 4, cluster_gap=80)

    result = _resolve(candles, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AMBIGUOUS


def test_insufficient_support_returns_no_members() -> None:
    candles, ids = _series(3)

    result = _resolve(candles, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.INSUFFICIENT_SUPPORT
    assert result.candles == ()
    assert result.trace.estimated_pitch_px is None


def test_ambiguous_result_does_not_choose_rightmost_cluster() -> None:
    candles, ids = _combine_runs(4, 4, cluster_gap=100)

    result = _resolve(candles, ids)

    assert not any(
        identifier.startswith("right_") for identifier in result.candidate_ids
    )
    assert result.trace.latest_candidate_id is None


def test_same_input_produces_exactly_equal_result_and_trace() -> None:
    fixture = _session_02_flag_and_text_fixture()
    resolver = CandleSeriesMembershipResolver()

    first = resolver.resolve(fixture.candles, fixture.candidate_ids, 22.0)
    second = resolver.resolve(fixture.candles, fixture.candidate_ids, 22.0)

    assert first == second
    assert first.trace == second.trace


def test_input_order_does_not_change_horizontal_result() -> None:
    fixture = _session_02_flag_fixture()
    order = (6, 2, 0, 5, 1, 4, 3)
    shuffled_candles = tuple(fixture.candles[index] for index in order)
    shuffled_ids = tuple(fixture.candidate_ids[index] for index in order)

    original = _resolve(fixture.candles, fixture.candidate_ids, 22.0)
    shuffled = _resolve(shuffled_candles, shuffled_ids, 22.0)

    assert shuffled == original


def test_positive_affine_x_transform_preserves_relative_identity() -> None:
    fixture = _session_02_flag_and_text_fixture()
    transformed = _transform(fixture.candles, x_scale=3, x_shift=211)

    result = _resolve(transformed, fixture.candidate_ids, 66.0)

    assert result.candidate_ids == fixture.candidate_ids[:6]
    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id


def test_positive_affine_y_transform_preserves_relative_identity() -> None:
    fixture = _session_02_flag_fixture()
    transformed = _transform(fixture.candles, y_scale=3, y_shift=17)

    result = _resolve(transformed, fixture.candidate_ids, 22.0)

    assert result.candidate_ids == fixture.candidate_ids[:6]
    assert result.trace.latest_candidate_id == fixture.real_latest_candidate_id


@pytest.mark.parametrize("dominant_width", (7.0, 8.0, 9.0))
def test_small_dominant_width_variations_preserve_clean_series(
    dominant_width: float,
) -> None:
    candles, ids = _series()

    result = _resolve(candles, ids, dominant_width)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids


@pytest.mark.parametrize("flag_offset", (11, 12, 13))
def test_moving_flag_within_lattice_jitter_keeps_vertical_exclusion(
    flag_offset: int,
) -> None:
    candles, ids = _series()
    flag = _candle(
        x=candles[-1].candidate.x + flag_offset,
        open_y=20,
        close_y=10,
    )

    result = _resolve(candles + (flag,), ids + ("flag",))

    assert _exclusion_map(result)["flag"].reason is (
        CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
    )


@pytest.mark.parametrize("text_x", (160, 220))
def test_moving_distant_text_keeps_horizontal_exclusion(text_x: int) -> None:
    candles, ids = _series()
    text = _candle(x=text_x, open_y=105, close_y=100)

    result = _resolve(candles + (text,), ids + ("text",))

    assert _exclusion_map(result)["text"].reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


def test_resolver_can_derive_width_scale_without_dominant_width() -> None:
    candles, ids = _series()

    result = _resolve(candles, ids, dominant_width=None)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.trace.estimated_pitch_px == pytest.approx(12.0)


def test_exact_dominant_support_ratio_selects_larger_run() -> None:
    candles, ids = _combine_runs(6, 4, cluster_gap=100)

    result = _resolve(candles, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids[:6]
    assert all(
        exclusion.reason
        is CandleSeriesMembershipExclusionReason.NOT_SELECTED_CLUSTER
        for exclusion in result.trace.excluded_candidates
    )


def test_unknown_vertical_evidence_does_not_automatically_discard_candidate() -> None:
    candles, ids = _series()
    unknown = replace(
        candles[3],
        candidate=replace(candles[3].candidate, geometry=None),
        candle_type=CandleType.UNKNOWN,
    )
    changed = candles[:3] + (unknown,) + candles[4:]

    result = _resolve(changed, ids)

    assert result.trace.status is CandleSeriesMembershipStatus.AVAILABLE
    assert result.candidate_ids == ids


def test_public_contracts_are_immutable_and_runtime_typed() -> None:
    candles, ids = _series()
    result = _resolve(candles, ids)
    public_contracts = (
        CandleSeriesMembershipExclusion,
        CandleSeriesMembershipGapTrace,
        CandleSeriesMembershipRunTrace,
        CandleSeriesMembershipTrace,
        CandleSeriesMembershipResult,
    )

    for contract in public_contracts:
        assert get_type_hints(contract)
    assert get_type_hints(CandleSeriesMembershipStatus) == {}
    assert get_type_hints(CandleSeriesMembershipExclusionReason) == {}
    assert get_type_hints(CandleSeriesMembershipResolver.resolve)["return"] is (
        CandleSeriesMembershipResult
    )
    with pytest.raises(FrozenInstanceError):
        result.trace.diagnostic = "mutated"  # type: ignore[misc]


def test_trace_records_pitch_gaps_runs_and_support() -> None:
    fixture = _session_02_flag_fixture()

    result = _resolve(fixture.candles, fixture.candidate_ids, 22.0)

    assert result.trace.estimated_pitch_px == pytest.approx(25.75)
    assert len(result.trace.evaluated_gaps) == len(fixture.candles) - 1
    assert tuple(run.support for run in result.trace.candidate_runs) == (6, 1)
    assert result.trace.selected_run_support == 6
    assert result.trace.diagnostic == "dominant_supported_run_selected"
