"""Synthetic pixel contracts, not evidence of real-market accuracy."""

import hashlib
import json
from dataclasses import asdict, replace

import numpy as np
import pytest

from pocket_option_analyzer.infrastructure.evidence import VisualEvidenceSerializer
from pocket_option_analyzer.vision.models import ChartRegion, CurrentVisualPriceStatus
from pocket_option_analyzer.vision.models.independent_visual_price import (
    GridEvidence,
    LabelRoleState,
    ObservationGeometry,
    OcrReading,
    OcrWord,
    PixelBox,
    ScaleContext,
    ScaleContextState,
    ScaleTick,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
)
from pocket_option_analyzer.vision.services import (
    independent_current_visual_price_extractor as offline_price,
)
from pocket_option_analyzer.vision.services.independent_label_role_resolver import (
    IndependentLabelRoleResolver,
)
from pocket_option_analyzer.vision.services.independent_price_config import (
    IndependentPriceConfig,
    LabelRoleConfig,
    ScaleContextConfig,
)
from pocket_option_analyzer.vision.services.independent_scale_context_resolver import (
    IndependentScaleContextResolver,
)
from pocket_option_analyzer.vision.services.market_analysis_pipeline import (
    MarketAnalysisPipeline,
)

IndependentCurrentVisualPriceExtractor = (
    offline_price.IndependentCurrentVisualPriceExtractor
)


def scene(kind="valid", x=220):
    image = np.full((200, 320, 3), (45, 25, 22), np.uint8)

    def badge(bx, y):
        image[y : y + 24, bx : bx + 70] = (144, 100, 64)
        for gx in range(bx + 8, bx + 60, 8):
            image[y + 7 : y + 17, gx : gx + 3] = 230

    badge(x, 70)
    if kind not in ("internal", "none", "borrowed"):
        image[81:83, 10:x] = (144, 100, 64)
    if kind == "gap":
        image[81:83, x - 10 : x - 1] = (45, 25, 22)
    if kind == "fragment":
        image[70:94, x + 29 : x + 32] = (45, 25, 22)
    if kind == "borrowed":
        image[79:86, 10:x] = (144, 100, 64)
    if kind in ("near_ui", "two"):
        badge(x, 120)
        if kind == "two":
            image[131:133, 10:x] = (144, 100, 64)
    if kind == "none":
        image[:] = (45, 25, 22)
    if kind == "ui":
        image[:] = (45, 25, 22)
        badge(30, 70)
        image[81:83, 10:30] = (144, 100, 64)
    return image


def context(image, grid=None):
    grid = grid or PixelBox(5, 10, 290, 180)
    ticks = tuple(
        ScaleTick(
            str(i),
            str(i),
            PixelBox(230, y, 285, y + 10),
            GridEvidence(y + 15, 5, 290, 285),
        )
        for i, y in enumerate((10, 90, 160))
    )
    return ScaleContext(
        ScaleContextState.AVAILABLE,
        (),
        ObservationGeometry(0, 0, image.shape[1], image.shape[0]),
        hashlib.sha256(image[:, :, :3].tobytes()).hexdigest(),
        "fake",
        PixelBox(230, 10, 285, 170),
        grid,
        ticks,
    )


def scale_scene(kind="valid"):
    image = scene(kind)
    image[:, 290:] = 10
    words = []
    for y, value in ((15, "1.300"), (95, "1.200"), (175, "1.100")):
        image[y : y + 10, 230:285] = 35
        image[y + 15, 5:290] = 65
        words.append(OcrWord(value, PixelBox(230, y, 285, y + 10)))
    return image, OcrReading(tuple(words), "deterministic_test_ocr")


class FakeOcr:
    def __init__(self, reading=None, error=None):
        self.reading = reading
        self.error = error
        self.calls = 0

    def recognize(self, image, *, timeout, max_words):
        self.calls += 1
        assert timeout > 0 and max_words > 0
        if self.error:
            raise self.error
        return self.reading


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("valid", "ROLE_VERIFIED"),
        ("fragment", "ROLE_VERIFIED"),
        ("gap", "ROLE_INSUFFICIENT"),
        ("internal", "ROLE_INSUFFICIENT"),
        ("borrowed", "ROLE_INSUFFICIENT"),
        ("near_ui", "ROLE_INSUFFICIENT"),
        ("two", "ROLE_AMBIGUOUS"),
        ("ui", "ROLE_REJECTED"),
        ("none", "ROLE_NO_PROPOSAL"),
    ],
)
def test_original_pixel_contracts(kind, expected):
    image = scene(kind)
    result = IndependentLabelRoleResolver().resolve(image, context(image))
    assert result.state == expected
    if result.state is LabelRoleState.VERIFIED:
        assert result.selected_box == PixelBox(220, 70, 290, 94)
        assert any(g.accepted for c in result.candidates for g in c.guides)
    else:
        assert result.selected_box is None
    if kind in ("internal", "gap", "borrowed", "near_ui"):
        assert result.proposals
    if kind == "fragment":
        assert result.proposals[0].original_fill_components > 1


@pytest.mark.parametrize(
    "x,state",
    [
        (218, "ROLE_VERIFIED"),
        (220, "ROLE_VERIFIED"),
        (221, "ROLE_INSUFFICIENT"),
        (223, "ROLE_INSUFFICIENT"),
        (227, "ROLE_REJECTED"),
    ],
)
def test_r3d_right_containment_not_docking_tolerance(x, state):
    image = scene(x=x)
    h1 = context(image)
    result = IndependentLabelRoleResolver().resolve(image, h1)
    assert result.state == state
    assert result.proposals[0].box == PixelBox(x, 70, x + 70, 94)
    assert h1.observed_grid == PixelBox(5, 10, 290, 180)
    if x in (221, 223):
        assert result.candidates[0].reason == "OUTSIDE_OBSERVED_H1_FOOTPRINT"
        assert result.candidates[0].guides == ()
        assert result.selected_box is None


@pytest.mark.parametrize(
    "grid,reason",
    [
        (PixelBox(5, 70, 290, 94), "JOINT_SCALE_BODY_GUIDE_EVIDENCE"),
        (PixelBox(5, 71, 290, 94), "OUTSIDE_OBSERVED_H1_FOOTPRINT"),
        (PixelBox(5, 70, 290, 93), "OUTSIDE_OBSERVED_H1_FOOTPRINT"),
        (PixelBox(220, 10, 290, 180), "EXTERNAL_GUIDE_INGRESS_NOT_ACCREDITED"),
        (PixelBox(221, 10, 290, 180), "OUTSIDE_OBSERVED_H1_FOOTPRINT"),
        (PixelBox(5, 10, 297, 180), "NOT_DOCKED_TO_OBSERVED_SCALE"),
    ],
)
def test_other_half_open_boundaries(grid, reason):
    image = scene()
    result = IndependentLabelRoleResolver().resolve(image, context(image, grid))
    assert result.candidates[0].reason == reason
    assert (result.selected_box is not None) == (
        reason == "JOINT_SCALE_BODY_GUIDE_EVIDENCE"
    )


@pytest.mark.parametrize("state", list(ScaleContextState))
def test_context_state_preserves_proposals(state):
    image = scene()
    result = IndependentLabelRoleResolver().resolve(
        image, replace(context(image), state=state)
    )
    assert result.proposals
    assert (result.selected_box is not None) == (state is ScaleContextState.AVAILABLE)


def test_wrong_image_binding_never_reused():
    image = scene()
    h1 = context(image)
    image[0, 0] = 0
    assert (
        IndependentLabelRoleResolver().resolve(image, h1).reason == "H1_IMAGE_MISMATCH"
    )
    assert (
        IndependentLabelRoleResolver().resolve(image[:, :289], h1).reason
        == "H1_GEOMETRY_MISMATCH"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_pixels", 10),
        ("max_colors", 1),
        ("max_proposals", 1),
        ("max_associations", 1),
    ],
)
def test_work_budgets_abstain(field, value):
    image = scene("two")
    cfg = replace(LabelRoleConfig(), **{field: value})
    result = IndependentLabelRoleResolver(cfg).resolve(image, context(image))
    assert result.state is LabelRoleState.BUDGET and result.selected_box is None


def test_time_budget_does_not_select_partial():
    image = scene()
    times = iter((0.0, 5.0))
    result = IndependentLabelRoleResolver(clock=lambda: next(times)).resolve(
        image, context(image)
    )
    assert result.state is LabelRoleState.BUDGET
    assert result.selected_box is None


def test_h1_from_pixels_and_independent_ocr():
    image, reading = scale_scene()
    ocr = FakeOcr(reading)
    geometry = ObservationGeometry(47, 39, 320, 200)
    result = IndependentScaleContextResolver(ocr).resolve(image, geometry)
    assert result.state is ScaleContextState.AVAILABLE
    assert result.observed_grid == PixelBox(5, 30, 290, 191)
    assert result.scale_region == PixelBox(230, 15, 285, 185)
    assert len(result.ticks) == 3 and result.linear_residual == 0
    assert result.panel_delta >= 4 and not result.full_chart_extent_certified
    assert (
        geometry.to_roi(geometry.to_frame(result.observed_grid)) == result.observed_grid
    )
    assert geometry.to_frame(result.observed_grid) == PixelBox(52, 69, 337, 230)
    assert ocr.calls == 1


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError(), "OCR_TIMEOUT"),
        (OSError(), "OCR_BACKEND_UNAVAILABLE"),
        (ValueError(), "OCR_RESULT_INVALID"),
    ],
)
def test_ocr_errors_controlled(error, reason):
    image, _ = scale_scene()
    result = IndependentScaleContextResolver(FakeOcr(error=error)).resolve(
        image, ObservationGeometry(0, 0, 320, 200)
    )
    assert reason in result.reasons and result.state is not ScaleContextState.AVAILABLE


def test_absent_ocr_and_insufficient_ticks():
    image, reading = scale_scene()
    geometry = ObservationGeometry(0, 0, 320, 200)
    assert IndependentScaleContextResolver(None).resolve(image, geometry).reasons == (
        "OCR_UNAVAILABLE",
    )
    result = IndependentScaleContextResolver(
        FakeOcr(replace(reading, words=reading.words[:2]))
    ).resolve(image, geometry)
    assert result.state is ScaleContextState.INSUFFICIENT
    assert len(result.ticks) == 2


def test_malformed_ocr_result_is_controlled():
    image, _ = scale_scene()
    result = IndependentScaleContextResolver(FakeOcr(None)).resolve(
        image,
        ObservationGeometry(0, 0, 320, 200),
    )
    assert result.state is ScaleContextState.INVALID
    assert result.reasons == ("OCR_RESULT_INVALID",)


def test_two_coherent_scales_are_ambiguous():
    image, reading = scale_scene()
    words = reading.words + tuple(
        replace(w, box=PixelBox(195, w.box.y0, 230, w.box.y1)) for w in reading.words
    )
    result = IndependentScaleContextResolver(
        FakeOcr(replace(reading, words=words))
    ).resolve(image, ObservationGeometry(0, 0, 320, 200))
    assert result.state is ScaleContextState.AMBIGUOUS


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("max_pixels", 10, "PIXEL_BUDGET_EXCEEDED"),
        ("max_words", 1, "OCR_WORD_BUDGET_EXCEEDED"),
        ("max_numeric_candidates", 1, "NUMERIC_BUDGET_EXCEEDED"),
    ],
)
def test_h1_work_limits(field, value, reason):
    image, reading = scale_scene()
    result = IndependentScaleContextResolver(
        FakeOcr(reading), replace(ScaleContextConfig(), **{field: value})
    ).resolve(image, ObservationGeometry(0, 0, 320, 200))
    assert result.reasons == (reason,)


def test_h1_time_limit():
    image, reading = scale_scene()
    times = iter((0.0, 21.0))
    result = IndependentScaleContextResolver(
        FakeOcr(reading), clock=lambda: next(times)
    ).resolve(image, ObservationGeometry(0, 0, 320, 200))
    assert result.reasons == ("CONTEXT_TIME_BUDGET_EXCEEDED",)


@pytest.mark.parametrize(
    "config", [None, IndependentPriceConfig(), IndependentPriceConfig(enabled=False)]
)
def test_off_exact_legacy_and_no_ocr(config):
    image, reading = scale_scene()
    ocr = FakeOcr(error=AssertionError("OFF must not invoke OCR"))
    extractor = IndependentCurrentVisualPriceExtractor(recognizer=ocr, config=config)
    legacy = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(image)
    assert extractor.extract_with_trace(image) == legacy
    assert (
        extractor.evaluate_offline(image, ObservationGeometry(0, 0, 320, 200)).analysis
        == legacy
    )
    assert ocr.calls == 0
    value = VisualEvidenceSerializer._current_visual_price_trace_to_dict(legacy.trace)
    assert "independent_identity" not in value


def test_enabled_does_not_change_regular_interface():
    image, reading = scale_scene()
    ocr = FakeOcr(reading)
    extractor = IndependentCurrentVisualPriceExtractor(
        recognizer=ocr, config=IndependentPriceConfig(enabled=True)
    )
    assert extractor.extract(
        image
    ) == PocketOptionCurrentVisualPriceExtractor().extract(image)
    assert ocr.calls == 0


@pytest.mark.parametrize(
    "kind,status",
    [
        ("valid", CurrentVisualPriceStatus.OK),
        ("two", CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE),
        ("near_ui", CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE),
        ("gap", CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE),
    ],
)
def test_full_pipeline_offline_only(kind, status):
    image, reading = scale_scene(kind)
    extractor = IndependentCurrentVisualPriceExtractor(
        recognizer=FakeOcr(reading), config=IndependentPriceConfig(enabled=True)
    )
    before = image.copy()
    output = MarketAnalysisPipeline.analyze_offline_current_visual_price(
        image, ChartRegion(40, 50, 320, 200), extractor
    )
    assert output.analysis.extraction.status is status
    assert np.array_equal(before, image)
    trace = output.analysis.trace.independent_identity
    assert trace.context.geometry.frame_x == 40
    assert (
        trace.execution_scope == "EXPLICIT_OFFLINE_ONLY" and not trace.absence_certified
    )
    assert not hasattr(output, "outcome") and not hasattr(output, "series")
    if status is CurrentVisualPriceStatus.OK:
        assert trace.role.selected_box == PixelBox(220, 70, 290, 94)
        assert output.analysis.extraction.price.roi_y == 81.5


def test_low_quality_only_after_identity_and_no_score_selection():
    image, reading = scale_scene()
    output = (
        IndependentCurrentVisualPriceExtractor(
            recognizer=FakeOcr(reading),
            config=IndependentPriceConfig(enabled=True, min_quality=0.99),
        )
        .evaluate_offline(image, ObservationGeometry(0, 0, 320, 200))
        .analysis
    )
    assert output.trace.independent_identity.role.state is LabelRoleState.VERIFIED
    assert output.extraction.status is CurrentVisualPriceStatus.LOW_CONFIDENCE
    assert output.extraction.price is None and output.extraction.confidence < 0.99


def test_deterministic_trace_without_durations_or_paths():
    image, reading = scale_scene()
    extractor = IndependentCurrentVisualPriceExtractor(
        recognizer=FakeOcr(reading), config=IndependentPriceConfig(enabled=True)
    )
    a = extractor.evaluate_offline(image, ObservationGeometry(0, 0, 320, 200))
    b = extractor.evaluate_offline(image, ObservationGeometry(0, 0, 320, 200))
    assert a.analysis == b.analysis
    encoded = json.dumps(
        VisualEvidenceSerializer._current_visual_price_trace_to_dict(a.analysis.trace),
        sort_keys=True,
    )
    assert (
        json.loads(encoded)["independent_identity"]["contract_version"]
        == "independent_h1_h2_r3d_v1"
    )
    assert (
        "h1_seconds" not in encoded
        and "h2_seconds" not in encoded
        and "Temp" not in encoded
    )
    assert asdict(a.analysis.trace.independent_identity) == asdict(
        b.analysis.trace.independent_identity
    )


@pytest.mark.parametrize("mode", ["float", "geometry", "gray"])
def test_invalid_inputs_never_ok(mode):
    image, reading = scale_scene()
    geometry = ObservationGeometry(0, 0, 319 if mode == "geometry" else 320, 200)
    if mode == "float":
        image = image.astype(float)
    if mode == "gray":
        image = image[:, :, 0]
    result = IndependentCurrentVisualPriceExtractor(
        recognizer=FakeOcr(reading), config=IndependentPriceConfig(enabled=True)
    ).evaluate_offline(image, geometry)
    assert result.analysis.extraction.status is CurrentVisualPriceStatus.INVALID_IMAGE
    assert result.analysis.extraction.price is None
