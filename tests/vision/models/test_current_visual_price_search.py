from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceLabelComponent,
    CurrentVisualPriceLineHypothesis,
    CurrentVisualPriceLineRun,
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSearchPlanStatus,
    CurrentVisualPriceSearchWindow,
    CurrentVisualPriceSearchWindowOrigin,
    CurrentVisualPriceSemanticSearchTrace,
)


def _constraints() -> CurrentVisualPriceSearchConstraints:
    return CurrentVisualPriceSearchConstraints(
        image_width=100,
        image_height=80,
        right_band_ratio=0.20,
        max_line_gap_ratio=0.01,
        max_line_start_offset_ratio=0.05,
        min_line_run_ratio=0.70,
        label_zone_ratio=0.25,
        label_vertical_radius_ratio=0.025,
        max_row_gap_px=1,
        max_candidate_height_px=7,
    )


def _semantic_window() -> CurrentVisualPriceSearchWindow:
    return CurrentVisualPriceSearchWindow(
        window_id="search_window_000",
        start_x=80,
        end_x=100,
        origin=CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR,
        line_hypothesis_ids=("line_hypothesis_000",),
        label_component_ids=("label_component_000",),
    )


def test_search_contracts_are_frozen_and_runtime_typed() -> None:
    window = _semantic_window()

    assert (
        get_type_hints(CurrentVisualPriceSearchWindow)["line_hypothesis_ids"]
        == tuple[str, ...]
    )
    assert (
        get_type_hints(CurrentVisualPriceSearchPlan)["windows"]
        == tuple[CurrentVisualPriceSearchWindow, ...]
    )
    assert (
        get_type_hints(CurrentVisualPriceSemanticSearchTrace)["selected_group_id"]
        == str | None
    )
    with pytest.raises(FrozenInstanceError):
        window.end_x = 101  # type: ignore[misc]


def test_semantic_window_requires_line_and_label_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        CurrentVisualPriceSearchWindow(
            window_id="window",
            start_x=80,
            end_x=100,
            origin=(CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR),
        )


def test_fixed_override_cannot_fake_semantic_provenance() -> None:
    with pytest.raises(ValueError, match="fingir"):
        CurrentVisualPriceSearchWindow(
            window_id="fixed",
            start_x=80,
            end_x=100,
            origin=CurrentVisualPriceSearchWindowOrigin.FIXED_OVERRIDE,
            line_hypothesis_ids=("line",),
        )


def test_available_plan_rejects_window_outside_image() -> None:
    with pytest.raises(ValueError, match="image_width"):
        CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.AVAILABLE,
            reason=(CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE),
            constraints=_constraints(),
            windows=(
                CurrentVisualPriceSearchWindow(
                    window_id="window",
                    start_x=80,
                    end_x=101,
                    origin=(
                        CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR
                    ),
                    line_hypothesis_ids=("line",),
                    label_component_ids=("label",),
                ),
            ),
            total_proposed_window_count=1,
        )


def test_line_and_label_models_use_half_open_coordinates() -> None:
    run = CurrentVisualPriceLineRun(row_y=10, start_x=20, end_x=30)
    hypothesis = CurrentVisualPriceLineHypothesis(
        hypothesis_id="line",
        runs=(run,),
    )
    label = CurrentVisualPriceLabelComponent(
        component_id="label",
        x=30,
        y=8,
        width=5,
        height=5,
        area=10,
    )

    assert hypothesis.runs[0].end_x - hypothesis.runs[0].start_x == 10
    assert label.end_x == 35
    assert label.end_y == 13


@pytest.mark.parametrize(
    "values",
    [
        {"image_width": 0},
        {"right_band_ratio": 0.0},
        {"label_zone_ratio": 0.0},
        {"max_row_gap_px": -1},
        {"max_candidate_height_px": -1},
        {"max_unique_windows": 0},
    ],
)
def test_constraints_reject_invalid_geometry(values: dict[str, object]) -> None:
    arguments: dict[str, object] = {
        "image_width": 100,
        "image_height": 80,
        "right_band_ratio": 0.20,
        "max_line_gap_ratio": 0.01,
        "max_line_start_offset_ratio": 0.05,
        "min_line_run_ratio": 0.70,
        "label_zone_ratio": 0.25,
        "label_vertical_radius_ratio": 0.025,
        "max_row_gap_px": 1,
        "max_candidate_height_px": 7,
    }
    arguments.update(values)

    with pytest.raises(ValueError):
        CurrentVisualPriceSearchConstraints(**arguments)  # type: ignore[arg-type]
