from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import file_digest, sha256
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSemanticResolutionStatus,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentPriceMaskBuilder,
    PocketOptionCurrentVisualPriceExtractor,
)
from pocket_option_analyzer.vision.services.composite_guide_price_extractor import (
    CompositeGuidePriceExtractor,
)


@dataclass(frozen=True, slots=True)
class _Oracle:
    frame_id: int
    frame_key: str
    width: int
    height: int
    roi_y: float


_ORACLES = (
    _Oracle(523, "frame_00000523_20260827T042002995979Z", 1180, 788, 265.4985835694051),
    _Oracle(532, "frame_00000532_20260827T042013038258Z", 1663, 788, 340.0),
    _Oracle(
        549, "frame_00000549_20260827T042032073087Z", 1652, 753, 242.49916247906197
    ),
    _Oracle(558, "frame_00000558_20260827T042042155147Z", 1493, 706, 142.0),
    _Oracle(576, "frame_00000576_20260827T042101977744Z", 1376, 653, 161.0),
    _Oracle(585, "frame_00000585_20260827T042112160063Z", 1376, 653, 188.0),
    _Oracle(603, "frame_00000603_20260827T042132408656Z", 1376, 653, 227.0),
    _Oracle(612, "frame_00000612_20260827T042142674815Z", 1376, 653, 259.0),
    _Oracle(630, "frame_00000630_20260827T042202923389Z", 1376, 653, 270.5),
    _Oracle(639, "frame_00000639_20260827T042213072698Z", 1376, 653, 312.4978448275862),
    _Oracle(656, "frame_00000656_20260827T042232190104Z", 1376, 653, 385.0),
    _Oracle(665, "frame_00000665_20260827T042242371343Z", 1376, 653, 398.0),
    _Oracle(683, "frame_00000683_20260827T042302637094Z", 1376, 653, 411.0),
    _Oracle(692, "frame_00000692_20260827T042312851910Z", 1376, 653, 432.498933901919),
)


def _evidence_root() -> Path:
    return (
        Path.home()
        / "Documents"
        / "Programas"
        / "p04b_session_06_postfix_01"
        / "visual_evidence"
    )


@lru_cache(maxsize=1)
def _images() -> dict[int, np.ndarray]:
    """Same original evidence; ZIP avoids requiring an expanded copy."""
    root = _evidence_root()
    archive_path = root.parent.with_suffix(".zip")
    if archive_path.is_file():
        with archive_path.open("rb") as stream:
            assert file_digest(stream, "sha256").hexdigest() == (
                "e25787f481f262f1f99f2b3f2e336c8cd595f73e1d0cbe67f9e1d72488e93bcd"
            )
        images = {}
        with ZipFile(archive_path) as archive:
            names = {n.replace("\\", "/"): n for n in archive.namelist()}
            for oracle in _ORACLES:
                member = (
                    f"p04b_session_06_postfix_01/visual_evidence/frames/"
                    f"{oracle.frame_key}/chart.png"
                )
                raw = archive.read(names[member])
                if oracle.frame_id == 523:
                    assert sha256(raw).hexdigest() == (
                        "b56419aca2fd89712b07fe765506f7f8a60bc8e68ab4886dcfb5873f5e793b4c"
                    )
                image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
                assert image is not None
                images[oracle.frame_id] = image
        return images
    try:
        available = root.is_dir()
    except OSError:
        available = False
    if not available:
        pytest.fail("Original Session06 evidence is required for this acceptance gate.")
    images = {}
    for oracle in _ORACLES:
        image_path = root / "frames" / oracle.frame_key / "chart.png"
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            pytest.fail(f"Unable to read local replay image: {image_path}")
        if oracle.frame_id == 523:
            assert sha256(image_path.read_bytes()).hexdigest() == (
                "b56419aca2fd89712b07fe765506f7f8a60bc8e68ab4886dcfb5873f5e793b4c"
            )
        images[oracle.frame_id] = image
    return images


@lru_cache(maxsize=1)
def _replay() -> dict[int, CurrentVisualPriceAnalysis]:
    extractor = PocketOptionCurrentVisualPriceExtractor()
    return {
        key: extractor.extract_with_trace(image) for key, image in _images().items()
    }


# F523D Principal explicitly authorized the version split and raster-band oracle.
# F523 retains its positive acceptance below; the other 13 v1 expectations stay exact.
@pytest.mark.parametrize(
    "oracle", _ORACLES[1:], ids=lambda item: f"frame{item.frame_id}"
)
def test_session06_post_resize_endpoints_are_recovered(oracle: _Oracle) -> None:
    analysis = _replay()[oracle.frame_id]

    assert analysis.trace.image_width == oracle.width
    assert analysis.trace.image_height == oracle.height
    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.price is not None
    assert analysis.extraction.price.roi_y == pytest.approx(oracle.roi_y)
    semantic = analysis.trace.semantic_search
    assert semantic is not None
    assert semantic.plan_reason is (
        CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE
    )
    assert semantic.resolution_status is (
        CurrentVisualPriceSemanticResolutionStatus.AVAILABLE
    )
    assert semantic.selected_group_id == "semantic_price_000"
    assert len(semantic.semantic_groups) == 1
    representative_id = semantic.semantic_groups[0].representative_window_id
    representative = next(
        window for window in semantic.windows if window.window_id == representative_id
    )
    assert analysis.trace.effective_chart_right_x == representative.end_x
    assert analysis.trace.effective_chart_right_source == "semantic_resolver"


def test_session06_f523_v1_conservative_compatibility_not_visual_absence() -> None:
    analysis = _replay()[523]
    assert (
        analysis.extraction.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.extraction.price is None
    assert (
        analysis.trace.semantic_search.qualification_contract
        == "dynamic_guide_label_v1"
    )
    assert analysis.trace.independent_identity is None


def test_session06_f523_v2_positive_raster_identity_and_exact_centroid() -> None:
    image = _images()[523]
    result = CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)
    analysis, evidence = result.analysis, result.support
    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.price is not None
    assert analysis.extraction.price.source == "dynamic_guide_label_v2"
    assert (analysis.trace.image_width, analysis.trace.image_height) == (1180, 788)
    semantic = analysis.trace.semantic_search
    assert semantic.qualification_contract == "dynamic_guide_label_v2"
    assert len(semantic.semantic_groups) == 1
    assert (
        semantic.resolution_status
        is CurrentVisualPriceSemanticResolutionStatus.AVAILABLE
    )
    assert semantic.selected_group_id == "semantic_price_000"
    associations = [a for a in semantic.label_associations if a.status == "available"]
    assert len(associations) == 1
    assert associations[0].label_ingress_x == 1022
    assert associations[0].canonical_window.end_x == 1093
    guides = [
        g for w in semantic.window_evaluations for g in w.local_guides if g.qualified
    ]
    assert {g.row_y for g in guides} == {265, 266}
    assert all((g.selected_start_x, g.selected_end_x) == (865, 1022) for g in guides)
    assert all(g.minimum_span == 154 and g.maximum_gap == 3 for g in guides)
    assert all(g.continuity >= 0.90 for g in guides)
    accepted = [r for r in evidence.regions if r.accepted]
    assert any(
        (r.top, r.bottom, r.start_x, r.end_x) == (265, 267, 968, 990) for r in accepted
    )
    assert all(r.rows and r.direct_seed_bounds for r in accepted)
    assert all(row.maximum_residual <= 2 for r in accepted for row in r.rows)
    direct = PocketOptionCurrentPriceMaskBuilder().build(image)
    for guide in guides:
        a, b = guide.selected_start_x, guide.selected_end_x
        direct_count = int(np.count_nonzero(direct[guide.row_y, a:b]))
        composite_count = sum(
            max(0, min(b, end) - max(a, start))
            for y, start, end in evidence.composite_spans
            if y == guide.row_y
        )
        assert guide.supported_pixels == direct_count + composite_count
        assert composite_count > 0 and direct_count > composite_count
    # The visual authority identifies these two raster rows, not an old weighted
    # subpixel centroid. Preserve that historical value as a positive reference.
    assert 265 <= _ORACLES[0].roi_y <= 266
    assert 265 <= analysis.extraction.price.roi_y <= 266
    counts = np.count_nonzero(direct[265:267, 874:1093], axis=1)
    expected = float(np.average([265, 266], weights=counts))
    assert analysis.extraction.price.roi_y == expected
    assert analysis.trace.independent_identity is None
