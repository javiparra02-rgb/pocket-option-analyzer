from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSemanticResolutionStatus,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
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
def _replay() -> dict[int, CurrentVisualPriceAnalysis]:
    root = _evidence_root()
    try:
        available = root.is_dir()
    except OSError:
        available = False
    if not available:
        pytest.skip("P0.4b session06 evidence is not available locally.")
    extractor = PocketOptionCurrentVisualPriceExtractor()
    results: dict[int, CurrentVisualPriceAnalysis] = {}
    for oracle in _ORACLES:
        image_path = root / "frames" / oracle.frame_key / "chart.png"
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            pytest.skip(f"Unable to read local replay image: {image_path}")
        results[oracle.frame_id] = extractor.extract_with_trace(image)
    return results


@pytest.mark.parametrize("oracle", _ORACLES, ids=lambda item: f"frame{item.frame_id}")
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
