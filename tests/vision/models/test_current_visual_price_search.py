from dataclasses import FrozenInstanceError, replace
from typing import get_type_hints

import pytest

from pocket_option_analyzer.infrastructure.evidence import VisualEvidenceSerializer
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
from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceLabelAssociation,
    CurrentVisualPriceLineLabelPair,
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


def _label_association() -> CurrentVisualPriceLabelAssociation:
    hypothesis = CurrentVisualPriceLineHypothesis(
        hypothesis_id="line_hypothesis_000",
        runs=(CurrentVisualPriceLineRun(row_y=10, start_x=20, end_x=30),),
    )
    first = CurrentVisualPriceLabelComponent(
        component_id="label_component_000",
        x=30,
        y=8,
        width=5,
        height=5,
        area=10,
    )
    second = CurrentVisualPriceLabelComponent(
        component_id="label_component_001",
        x=40,
        y=8,
        width=5,
        height=5,
        area=10,
    )
    return CurrentVisualPriceLabelAssociation(
        hypothesis_id=hypothesis.hypothesis_id,
        pairs=(
            CurrentVisualPriceLineLabelPair(
                pair_id="pair_0",
                hypothesis=hypothesis,
                component=first,
                window_id="search_window_000",
                window_start_x=20,
                pair_edge=32,
            ),
            CurrentVisualPriceLineLabelPair(
                pair_id="pair_1",
                hypothesis=hypothesis,
                component=second,
                window_id="search_window_001",
                window_start_x=30,
                pair_edge=42,
            ),
        ),
        eligible_pair_ids=("pair_0",),
        rejected_pair_ids=("pair_1",),
        component_groups=(("pair_0",),),
        admissible_groups=(("pair_0",),),
        canonical_window=CurrentVisualPriceSearchWindow(
            window_id="search_window_000",
            start_x=20,
            end_x=32,
            origin=CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR,
            line_hypothesis_ids=(hypothesis.hypothesis_id,),
            label_component_ids=(first.component_id,),
        ),
        max_line_gap_ratio=0.01,
    )


@pytest.mark.parametrize(
    "groups",
    [
        (("unknown_pair",),),
        ((),),
        (("pair_1",),),
    ],
)
def test_label_association_rejects_invalid_component_groups(
    groups: tuple[tuple[str, ...], ...],
) -> None:
    with pytest.raises(ValueError, match="component group"):
        replace(_label_association(), component_groups=groups)


def test_label_association_rejects_undeclared_admissible_group() -> None:
    with pytest.raises(ValueError, match="admissible group"):
        replace(_label_association(), admissible_groups=(("pair_0", "pair_0"),))


def test_valid_label_association_serializes_its_declared_group() -> None:
    association = _label_association()

    payload = VisualEvidenceSerializer._label_association_to_dict(association)

    assert payload["status"] == "available"
    assert payload["input_pair_ids"] == ["pair_0", "pair_1"]
    assert payload["groups"] == [
        {
            "group_id": "line_hypothesis_000:label_group_000",
            "pair_ids": ["pair_0"],
            "component_ids": ["label_component_000"],
            "envelope": {"start_x": 30, "end_x": 35, "start_y": 8, "end_y": 13},
            "admissible": True,
            "reason": "covers_line_band",
        }
    ]
    assert payload["label_ingress_x"] == 30
    assert payload["canonical_window_id"] == "search_window_000"


def test_unavailable_label_association_without_groups_serializes_as_empty() -> None:
    association = replace(
        _label_association(),
        pairs=(),
        eligible_pair_ids=(),
        rejected_pair_ids=(),
        component_groups=(),
        admissible_groups=(),
        canonical_window=None,
    )

    payload = VisualEvidenceSerializer._label_association_to_dict(association)

    assert payload["status"] == "unavailable"
    assert payload["input_pair_ids"] == []
    assert payload["groups"] == []
    assert payload["label_ingress_x"] is None
    assert payload["canonical_window_id"] is None


def test_label_association_preserves_declared_group_order() -> None:
    association = replace(
        _label_association(),
        eligible_pair_ids=("pair_0", "pair_1"),
        rejected_pair_ids=(),
        component_groups=(("pair_1",), ("pair_0",)),
    )

    payload = VisualEvidenceSerializer._label_association_to_dict(association)

    assert [group["pair_ids"] for group in payload["groups"]] == [
        ["pair_1"],
        ["pair_0"],
    ]
    assert [group["admissible"] for group in payload["groups"]] == [False, True]


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
