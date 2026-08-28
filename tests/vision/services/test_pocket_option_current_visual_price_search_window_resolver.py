from __future__ import annotations

from typing import get_type_hints

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSearchPlanStatus,
    CurrentVisualPriceSearchWindowOrigin,
)
from pocket_option_analyzer.vision.services import (
    CurrentVisualPriceSearchWindowResolver,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)


def _constraints(
    width: int = 100,
    height: int = 100,
) -> CurrentVisualPriceSearchConstraints:
    return CurrentVisualPriceSearchConstraints(
        image_width=width,
        image_height=height,
        right_band_ratio=0.20,
        max_line_gap_ratio=0.01,
        max_line_start_offset_ratio=0.05,
        min_line_run_ratio=0.70,
        label_zone_ratio=0.25,
        label_vertical_radius_ratio=0.025,
        max_row_gap_px=1,
        max_candidate_height_px=7,
    )


def _marker(
    mask: np.ndarray,
    *,
    y: int,
    start_x: int,
    line_end_x: int,
    label_start_x: int,
    label_end_x: int,
) -> None:
    mask[y, start_x:label_end_x] = 255
    mask[y - 3 : y, label_start_x:label_end_x] = 255
    mask[y + 1 : y + 4, label_start_x:label_end_x] = 255
    assert line_end_x <= label_end_x


def test_resolver_implements_runtime_protocol_and_type_hints() -> None:
    resolver = PocketOptionCurrentVisualPriceSearchWindowResolver()

    assert isinstance(resolver, CurrentVisualPriceSearchWindowResolver)
    assert get_type_hints(resolver.resolve)


def test_resolver_builds_canonical_half_open_window_without_mutating_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        start_x=80,
        line_end_x=95,
        label_start_x=95,
        label_end_x=100,
    )
    original = mask.copy()

    plan = PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
        mask=mask,
        constraints=_constraints(),
    )

    assert plan.status is CurrentVisualPriceSearchPlanStatus.AVAILABLE
    assert plan.reason is (
        CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE
    )
    assert len(plan.windows) == 1
    window = plan.windows[0]
    assert (window.start_x, window.end_x, window.width) == (80, 100, 20)
    assert window.origin is (
        CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR
    )
    assert window.line_hypothesis_ids == ("line_hypothesis_000",)
    assert len(window.label_component_ids) == 2
    np.testing.assert_array_equal(mask, original)


def test_resolver_is_deterministic_for_identical_ndarray() -> None:
    mask = np.zeros((120, 240), dtype=np.uint8)
    _marker(
        mask,
        y=60,
        start_x=176,
        line_end_x=220,
        label_start_x=220,
        label_end_x=230,
    )
    resolver = PocketOptionCurrentVisualPriceSearchWindowResolver()

    first = resolver.resolve(mask=mask, constraints=_constraints(240, 120))
    second = resolver.resolve(mask=mask, constraints=_constraints(240, 120))

    assert first == second


def test_resolver_runs_connected_components_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        start_x=80,
        line_end_x=95,
        label_start_x=95,
        label_end_x=100,
    )
    calls = 0
    original = cv2.connectedComponentsWithStats

    def recording_connected_components(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        "pocket_option_analyzer.vision.services."
        "pocket_option_current_visual_price_search_window_resolver.cv2."
        "connectedComponentsWithStats",
        recording_connected_components,
    )

    PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
        mask=mask,
        constraints=_constraints(),
    )

    assert calls == 1


@pytest.mark.parametrize(
    "kind",
    ["line_only", "label_only", "side_panel_artifact"],
)
def test_incomplete_semantic_evidence_does_not_create_window(kind: str) -> None:
    mask = np.zeros((100, 120), dtype=np.uint8)
    if kind == "line_only":
        mask[50, 80:105] = 255
    elif kind == "label_only":
        mask[47:54, 105:115] = 255
    else:
        mask[20:80, 116:120] = 255

    plan = PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
        mask=mask,
        constraints=_constraints(120, 100),
    )

    assert plan.status is CurrentVisualPriceSearchPlanStatus.UNAVAILABLE
    assert plan.windows == ()


def test_tall_transitive_text_shape_is_not_a_horizontal_line() -> None:
    mask = np.zeros((100, 120), dtype=np.uint8)
    mask[40:48, 80:105] = 255
    mask[37:40, 105:115] = 255

    plan = PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
        mask=mask,
        constraints=_constraints(120, 100),
    )

    assert plan.status is CurrentVisualPriceSearchPlanStatus.UNAVAILABLE
    assert plan.reason is (
        CurrentVisualPriceSearchPlanReason.NO_HORIZONTAL_LINE_HYPOTHESES
    )
    assert plan.windows == ()


def test_window_guard_fails_closed_without_selecting_partial_result() -> None:
    mask = np.zeros((200, 200), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        start_x=120,
        line_end_x=170,
        label_start_x=170,
        label_end_x=180,
    )
    _marker(
        mask,
        y=140,
        start_x=130,
        line_end_x=180,
        label_start_x=180,
        label_end_x=190,
    )
    resolver = PocketOptionCurrentVisualPriceSearchWindowResolver(max_unique_windows=1)

    plan = resolver.resolve(mask=mask, constraints=_constraints(200, 200))

    assert plan.status is CurrentVisualPriceSearchPlanStatus.UNAVAILABLE
    assert plan.reason is CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED
    assert plan.total_proposed_window_count > 1
    assert len(plan.windows) == 1
    assert plan.full_window_set_sha256 is not None


def test_default_guard_rejects_more_than_32_unique_windows() -> None:
    mask = np.zeros((200, 2000), dtype=np.uint8)
    for index in range(33):
        edge = 1000 + index * 20
        y = 3 + index * 6
        band_width = int(np.ceil(edge * 0.20))
        _marker(
            mask,
            y=y,
            start_x=edge - band_width,
            line_end_x=edge - 5,
            label_start_x=edge - max(1, int(np.ceil(band_width * 0.25))),
            label_end_x=edge,
        )
    constraints = CurrentVisualPriceSearchConstraints(
        image_width=2000,
        image_height=200,
        right_band_ratio=0.20,
        max_line_gap_ratio=0.01,
        max_line_start_offset_ratio=0.05,
        min_line_run_ratio=0.70,
        label_zone_ratio=0.25,
        label_vertical_radius_ratio=0.0,
        max_row_gap_px=1,
        max_candidate_height_px=7,
    )

    plan = PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
        mask=mask,
        constraints=constraints,
    )

    assert plan.status is CurrentVisualPriceSearchPlanStatus.UNAVAILABLE
    assert plan.reason is CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED
    assert plan.total_proposed_window_count >= 33
    assert len(plan.windows) == 32


@pytest.mark.parametrize(
    "mask",
    [
        np.zeros((10, 10, 3), dtype=np.uint8),
        np.zeros((10, 10), dtype=np.float32),
        np.zeros((9, 10), dtype=np.uint8),
    ],
)
def test_resolver_rejects_malformed_masks(mask: np.ndarray) -> None:
    with pytest.raises(ValueError, match="mask"):
        PocketOptionCurrentVisualPriceSearchWindowResolver().resolve(
            mask=mask,
            constraints=_constraints(10, 10),
        )
