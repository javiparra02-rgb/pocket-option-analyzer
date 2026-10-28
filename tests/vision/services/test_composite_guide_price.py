from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from hashlib import file_digest, sha256
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import CurrentVisualPriceStatus
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentPriceMaskBuilder,
    PocketOptionCurrentVisualPriceExtractor,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)
from pocket_option_analyzer.vision.services.composite_guide_price_extractor import (
    CompositeGuidePriceExtractor,
)
from pocket_option_analyzer.vision.services.composite_guide_support import (
    CompositeGuideSupportObserver,
)

BACKGROUND = np.array([48, 28, 25])
FOREGROUND = np.array([168, 118, 74])
DIRECT = ((BACKGROUND + FOREGROUND) / 2).astype(np.uint8)


def _scene(*, scale=1, occluder=240, gap=20, label=True, alpha=0.5):
    """Observed alpha composition, independent of photographic coordinates."""
    image = np.full((180 * scale, 480 * scale, 3), BACKGROUND, dtype=np.uint8)
    top, bottom = 80 * scale, 82 * scale
    start, end = (385 - gap) * scale, 385 * scale
    image[65 * scale : 100 * scale, start:end] = occluder
    color = np.rint(alpha * FOREGROUND + (1 - alpha) * BACKGROUND).astype(np.uint8)
    image[top:bottom, 10 * scale : 400 * scale] = color
    if label:
        image[70 * scale : 92 * scale, 400 * scale : 444 * scale] = DIRECT
        image[74 * scale : 78 * scale, 420 * scale : 422 * scale] = 240
    image[top:bottom, start:end] = np.rint(
        alpha * FOREGROUND + (1 - alpha) * occluder
    ).astype(np.uint8)
    return image


def _observe(image):
    mask = PocketOptionCurrentPriceMaskBuilder().build(image)
    return CompositeGuideSupportObserver().observe(image, mask, roi_origin=(0, 0))


@pytest.mark.parametrize("occluder", [0, 220, 240, 255])
@pytest.mark.parametrize("scale", [1, 2, 3])
def test_observed_light_dark_composition_requires_original_pixels(occluder, scale):
    image = _scene(scale=scale, occluder=occluder)
    original = image.copy()
    direct = PocketOptionCurrentPriceMaskBuilder().build(image)
    support, trace = _observe(image)
    expected = 20 * scale * 2 * scale
    assert sum(end - start for _, start, end in trace.composite_spans) == expected
    assert np.count_nonzero(support) == np.count_nonzero(direct) + expected
    assert np.array_equal(image, original)
    assert np.array_equal(PocketOptionCurrentPriceMaskBuilder().build(image), direct)
    assert all(r.accepted for r in trace.regions)
    assert all(row.maximum_residual <= 2 for r in trace.regions for row in r.rows)
    assert trace.contract_version == "dynamic_guide_label_v2"


@pytest.mark.parametrize("enabled", [False, True])
def test_ordinary_methods_never_enable_v2_or_independent_ocr(enabled):
    image = _scene()
    expected = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(image)
    extractor = CompositeGuidePriceExtractor(enabled=enabled)
    assert extractor.extract_with_trace(image) == expected
    assert extractor.extract(image) == expected.extraction
    assert expected.trace.independent_identity is None
    assert (
        expected.trace.semantic_search.qualification_contract
        == "dynamic_guide_label_v1"
    )


def test_default_off_and_bad_activation():
    with pytest.raises(ValueError, match="explicit offline"):
        CompositeGuidePriceExtractor().evaluate_offline(_scene())
    with pytest.raises(TypeError):
        CompositeGuidePriceExtractor(enabled="true")


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_full_chain_composite_identity_and_direct_label(scale):
    image = _scene(scale=scale)
    v1 = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(image)
    v2 = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert v1.extraction.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    assert v2.analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert 80 * scale <= v2.analysis.extraction.price.roi_y < 82 * scale
    semantic = v2.analysis.trace.semantic_search
    assert len(semantic.semantic_groups) == 1
    assert semantic.qualification_contract == "dynamic_guide_label_v2"
    assert any(g.qualified for w in semantic.window_evaluations for g in w.local_guides)
    # New support lies exclusively outside LABEL. Direct pixels still supply it.
    assert all(end <= 400 * scale for _, _, end in v2.support.composite_spans)
    assert all(
        g.contract_version == "dynamic_guide_label_v2"
        for w in semantic.window_evaluations
        for g in w.local_guides
    )
    assert v2.analysis.trace.masked_pixel_count == np.count_nonzero(
        PocketOptionCurrentPriceMaskBuilder().build(image)
    )


@pytest.mark.parametrize(
    "defect",
    [
        "no_stroke",
        "wrong_color",
        "texture",
        "different_anchors",
        "shifted_row",
        "opacity_change",
        "empty_gap",
        "missing_anchor",
    ],
)
def test_contradictions_never_create_composite_support_or_identity(defect):
    image = _scene()
    if defect == "no_stroke":
        image[80:82, 365:385] = 240
    elif defect == "wrong_color":
        image[80:82, 365:385] = [190, 200, 180]
    elif defect == "texture":
        image[78:80, 365:385] = 100
    elif defect == "different_anchors":
        image[80:82, 385:400] = [140, 90, 60]
    elif defect == "shifted_row":
        image[84:86, 365:385] = image[80:82, 365:385]
        image[80:82, 365:385] = 240
    elif defect == "opacity_change":
        image[80:82, 375:385] = np.rint(0.8 * FOREGROUND + 0.2 * 240).astype(np.uint8)
    elif defect == "empty_gap":
        image[65:100, 365:385] = BACKGROUND
    else:
        image[80:82, 385:400] = BACKGROUND
    _, trace = _observe(image)
    assert not trace.composite_spans
    v2 = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert (
        v2.analysis.extraction.status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert v2.analysis.extraction.price is None


@pytest.mark.parametrize("scale", [1, 2])
def test_composite_guide_does_not_create_label_from_detached_ui(scale):
    image = _scene(scale=scale, label=False)
    image[70 * scale : 80 * scale, 400 * scale : 420 * scale] = DIRECT
    image[85 * scale : 92 * scale, 400 * scale : 420 * scale] = DIRECT
    v2 = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert (
        v2.support.composite_spans
    )  # Test reaches association, not earlier rejection.
    assert (
        v2.analysis.extraction.status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert not v2.analysis.trace.semantic_search.semantic_groups


def test_no_label_and_composite_color_without_direct_anchors():
    image = _scene(label=False)
    v2 = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert v2.support.composite_spans
    assert v2.analysis.extraction.price is None
    image[80:82, 10:365] = BACKGROUND
    image[80:82, 385:400] = BACKGROUND
    assert not _observe(image)[1].composite_spans


def test_two_genuine_prices_remain_ambiguous_despite_unequal_quality():
    image = _scene()
    image[130:132, 10:400] = DIRECT
    image[120:142, 400:444] = DIRECT
    v2 = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert (
        v2.analysis.extraction.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    )
    assert v2.analysis.extraction.price is None
    assert len(v2.analysis.trace.semantic_search.semantic_groups) == 2


def test_low_confidence_only_after_identity():
    result = CompositeGuidePriceExtractor(
        enabled=True, min_confidence=0.999
    ).evaluate_offline(_scene())
    assert result.analysis.extraction.status is CurrentVisualPriceStatus.LOW_CONFIDENCE
    assert len(result.analysis.trace.semantic_search.semantic_groups) == 1
    image = _scene(label=False)
    result = CompositeGuidePriceExtractor(
        enabled=True, min_confidence=0.999
    ).evaluate_offline(image)
    assert (
        result.analysis.extraction.status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_deterministic_json_raster_binding_and_geometry():
    image = _scene()
    extractor = CompositeGuidePriceExtractor(enabled=True)
    result = extractor.evaluate_offline(image, roi_origin=(7, 19))
    assert result == extractor.evaluate_offline(image, roi_origin=(7, 19))
    assert result.to_dict() == json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert result.support.roi_origin == (7, 19)
    changed = image.copy()
    changed[0, 0, 0] += 1
    other = extractor.evaluate_offline(changed)
    assert other.support.raster_sha256 != result.support.raster_sha256
    assert other.support.config_sha256 == result.support.config_sha256
    assert result.analysis.trace.independent_identity is None


def test_reverse_proposals_cannot_change_selected_identity(monkeypatch):
    image = _scene()
    extractor = CompositeGuidePriceExtractor(enabled=True)
    before = extractor.evaluate_offline(image)
    original = (
        PocketOptionCurrentVisualPriceSearchWindowResolver.resolve_with_guide_support
    )

    def reversed_plan(self, **kwargs):
        plan = original(self, **kwargs)
        return replace(
            plan,
            windows=tuple(reversed(plan.windows)),
            line_label_pairs=tuple(reversed(plan.line_label_pairs)),
        )

    monkeypatch.setattr(
        PocketOptionCurrentVisualPriceSearchWindowResolver,
        "resolve_with_guide_support",
        reversed_plan,
    )
    after = extractor.evaluate_offline(image)
    assert before.analysis.extraction == after.analysis.extraction
    assert (
        before.analysis.trace.semantic_search.semantic_groups
        == after.analysis.trace.semantic_search.semantic_groups
    )


@pytest.mark.parametrize("origin", [(-1, 0), (True, 0), (0,), (1.1, 0)])
def test_invalid_coordinate_context_is_rejected(origin):
    with pytest.raises(ValueError, match="ROI origin"):
        CompositeGuidePriceExtractor(enabled=True).evaluate_offline(
            _scene(), roi_origin=origin
        )


def test_image_and_pixel_budget_fail_before_evaluation():
    extractor = CompositeGuidePriceExtractor(enabled=True)
    with pytest.raises(ValueError, match="invalid original"):
        extractor.evaluate_offline(np.zeros((0, 0, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="budget"):
        extractor.evaluate_offline(np.zeros((2001, 2000, 3), dtype=np.uint8))


@pytest.mark.parametrize(
    "start, expected", [(337, "ok"), (338, "no_visual_price_candidate")]
)
def test_v2_preserves_exterior_length_boundary(start, expected):
    image = _scene()
    image[65:100, 365:385] = BACKGROUND
    image[80:82, 10:400] = BACKGROUND
    image[80:82, start:400] = DIRECT
    result = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert not result.support.composite_spans
    assert result.analysis.extraction.status.value == expected
    guides = [
        g
        for w in result.analysis.trace.semantic_search.window_evaluations
        for g in w.local_guides
    ]
    assert any(g.minimum_span == 63 for g in guides)
    assert any(g.qualified for g in guides) == (expected == "ok")


@pytest.mark.parametrize(
    "holes, expected", [(6, "ok"), (7, "no_visual_price_candidate")]
)
def test_v2_preserves_true_gap_and_continuity_boundary(holes, expected):
    image = _scene()
    image[65:100, 365:385] = BACKGROUND
    image[80:82, 10:400] = BACKGROUND
    image[80:82, 337:400] = DIRECT
    for x in range(342, 342 + 3 * holes, 3):
        image[80:82, x] = BACKGROUND
    result = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert not result.support.composite_spans
    guides = [
        g
        for w in result.analysis.trace.semantic_search.window_evaluations
        for g in w.local_guides
    ]
    assert guides and all(g.maximum_gap == 1 for g in guides)
    assert result.analysis.extraction.status.value == expected


def test_direct_seed_uses_only_v1_bounded_gaps_not_recursive_composite():
    image = _scene()
    image[80:82, 330] = BACKGROUND  # One true gap: allowed by existing v1 rule.
    result = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    assert result.analysis.extraction.status is CurrentVisualPriceStatus.OK
    accepted = [r for r in result.support.regions if r.accepted]
    assert accepted and all(r.direct_seed_bounds for r in accepted)
    # Without enough original seed, a chain of individually plausible tiles
    # must not bootstrap itself into a long GUIDE.
    image = _scene()
    for x in range(10, 400, 30):
        image[65:100, x : x + 20] = 240
        image[80:82, x : x + 20] = np.rint(0.5 * FOREGROUND + 120).astype(np.uint8)
    assert not _observe(image)[1].composite_spans


def test_label_support_and_v1_serializer_are_not_rewritten():
    from pocket_option_analyzer.infrastructure.evidence import (
        VisualEvidenceSerializer,
    )

    image = _scene()
    wrapper = CompositeGuidePriceExtractor(enabled=True)
    legacy = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(image)
    actual = wrapper.extract_with_trace(image)
    assert VisualEvidenceSerializer._current_visual_price_trace_to_dict(
        actual.trace
    ) == VisualEvidenceSerializer._current_visual_price_trace_to_dict(legacy.trace)
    composite = wrapper.evaluate_offline(image)
    direct_image = image.copy()
    direct_image[65:100, 365:385] = BACKGROUND
    direct_image[80:82, 365:385] = DIRECT
    direct = wrapper.evaluate_offline(direct_image)
    left = [
        r.label_support_trace
        for r in composite.analysis.trace.row_evaluations
        if r.qualified
    ]
    right = [
        r.label_support_trace
        for r in direct.analysis.trace.row_evaluations
        if r.qualified
    ]
    assert left and left == right


@lru_cache(maxsize=1)
def _known_photographs():
    archive_path = (
        Path.home() / "Documents/Programas/p04b_session_08_noise_floor_02.zip"
    )
    assert archive_path.is_file(), "Original Session08 required for v2 acceptance"
    with archive_path.open("rb") as stream:
        assert file_digest(stream, "sha256").hexdigest() == (
            "53b8e198821a69f7b9f0343f33531ff83fdbf56f5b197d74ee64663899eb3091"
        )
    prefix = "p04b_session_08_noise_floor_02/visual_evidence/"
    results = {}
    with ZipFile(archive_path) as archive:
        records = [
            json.loads(line)
            for line in archive.read(
                prefix + "identity_shadow/frames.jsonl"
            ).splitlines()
        ]
        for record in records:
            if record["frame_id"] not in {
                166,
                1354,
                1363,
                1728,
                2402,
                2451,
                1021,
                1067,
            }:
                continue
            raw = archive.read(prefix + record["png"]["filename"])
            assert sha256(raw).hexdigest() == record["png"]["sha256"]
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
            assert image is not None
            results[record["frame_id"]] = image
    return results


@pytest.mark.parametrize(
    "frame_id, row",
    [
        (166, 129),
        (1354, 178),
        (1363, 197),
        (1728, 150),
        (2402, 155),
        (2451, 185),
        (1021, 398),
        (1067, 171),
    ],
)
def test_known_photographic_identities_v1_and_v2(frame_id, row):
    image = _known_photographs()[frame_id]
    extractor = CompositeGuidePriceExtractor(enabled=True)
    original = image.copy()
    v2 = extractor.evaluate_offline(image)
    for analysis in (extractor.extract_with_trace(image), v2.analysis):
        assert analysis.extraction.status is CurrentVisualPriceStatus.OK
        assert analysis.extraction.price.roi_y == row
        assert len(analysis.trace.semantic_search.semantic_groups) == 1
        if frame_id == 1067:
            guides = [
                g
                for w in analysis.trace.semantic_search.window_evaluations
                for g in w.local_guides
            ]
            assert not any(g.row_y == 121 and g.qualified for g in guides)
            assert any(g.row_y == 171 and g.qualified for g in guides)
    assert np.array_equal(image, original)
    if frame_id == 1067:
        assert not v2.support.composite_spans
        assert any(
            r.top <= 121 < r.bottom and r.rejection_reasons for r in v2.support.regions
        )
