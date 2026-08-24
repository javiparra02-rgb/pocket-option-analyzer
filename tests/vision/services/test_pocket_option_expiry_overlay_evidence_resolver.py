from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleGeometry,
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    CandleType,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionExpiryOverlayEvidenceResolver,
)


def _candle(
    *,
    x: int = 50,
    y: int = 20,
    width: int = 20,
    height: int = 12,
    wickless: bool = True,
) -> ClassifiedCandle:
    upper_wick = 0 if wickless else 2
    lower_wick = 0 if wickless else 2
    geometry = CandleGeometry(
        high_y=y,
        body_top_y=y + upper_wick,
        body_bottom_y=y + height - lower_wick - 1,
        low_y=y + height - 1,
    )
    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=y,
            width=width,
            height=height,
            area=width * height,
            color=CandleColor.WHITE,
            geometry=geometry,
        ),
        candle_type=CandleType.BULLISH,
    )


def _image_with_candidate(
    candle: ClassifiedCandle,
    *,
    line_x: int | None,
    line_end_y: int = 199,
) -> np.ndarray:
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    candidate = candle.candidate
    cv2.rectangle(
        image,
        (candidate.x, candidate.y),
        (
            candidate.x + candidate.width - 1,
            candidate.y + candidate.height - 1,
        ),
        (255, 255, 255),
        thickness=-1,
    )
    if line_x is not None:
        cv2.line(
            image,
            (line_x, candidate.y + candidate.height),
            (line_x, line_end_y),
            (180, 180, 180),
            thickness=1,
        )
    return image


def _resolve(
    image: np.ndarray,
    candle: ClassifiedCandle,
) -> CandleOverlayEvidence:
    trace = PocketOptionExpiryOverlayEvidenceResolver().resolve(
        image=image,
        candles=(candle,),
        candidate_ids=("candidate",),
    )
    return trace.evidence[0]


def test_cap_attached_to_long_vertical_line_is_expiry_overlay() -> None:
    candle = _candle()
    evidence = _resolve(
        _image_with_candidate(candle, line_x=candle.candidate.x),
        candle,
    )

    assert evidence.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
    assert evidence.vertical_line_support_ratio is not None
    assert evidence.vertical_line_support_ratio > 0.80
    assert evidence.contact_gap_ratio is not None
    assert evidence.contact_gap_ratio <= 0.05
    assert evidence.horizontal_alignment_ratio is not None
    assert evidence.horizontal_alignment_ratio <= 0.05
    assert evidence.vertical_line_x is not None
    assert abs(evidence.vertical_line_x - candle.candidate.x) <= 1
    assert evidence.vertical_line_start_y == (
        candle.candidate.y + candle.candidate.height
    )
    assert evidence.vertical_line_end_y == 199


def test_small_candle_without_line_has_no_overlay_evidence() -> None:
    candle = _candle(height=8)

    evidence = _resolve(_image_with_candidate(candle, line_x=None), candle)

    assert evidence.status is CandleOverlayEvidenceStatus.NO_EVIDENCE
    assert evidence.vertical_line_x is None
    assert evidence.vertical_line_start_y is None
    assert evidence.vertical_line_end_y is None


def test_wickless_candle_without_line_has_no_overlay_evidence() -> None:
    candle = _candle(wickless=True)

    evidence = _resolve(_image_with_candidate(candle, line_x=None), candle)

    assert evidence.status is CandleOverlayEvidenceStatus.NO_EVIDENCE
    assert evidence.wickless is True


def test_short_vertical_noise_is_not_strong_overlay_evidence() -> None:
    candle = _candle()
    image = _image_with_candidate(
        candle,
        line_x=candle.candidate.x,
        line_end_y=70,
    )

    evidence = _resolve(image, candle)

    assert evidence.status is CandleOverlayEvidenceStatus.NO_EVIDENCE
    assert evidence.vertical_line_support_ratio is not None
    assert evidence.vertical_line_support_ratio < 0.50


def test_long_line_at_candidate_right_edge_is_not_expiry_cap_alignment() -> None:
    candle = _candle()
    image = _image_with_candidate(
        candle,
        line_x=candle.candidate.x + candle.candidate.width - 1,
    )

    evidence = _resolve(image, candle)

    assert evidence.status is CandleOverlayEvidenceStatus.NO_EVIDENCE
    assert evidence.horizontal_alignment_ratio is not None
    assert evidence.horizontal_alignment_ratio > 0.25


@pytest.mark.parametrize(
    ("line_length", "expected_status"),
    (
        (50, CandleOverlayEvidenceStatus.EXPIRY_OVERLAY),
        (49, CandleOverlayEvidenceStatus.NO_EVIDENCE),
    ),
)
def test_vertical_line_support_ratio_boundary_is_inclusive(
    line_length: int,
    expected_status: CandleOverlayEvidenceStatus,
) -> None:
    resolver = PocketOptionExpiryOverlayEvidenceResolver()
    candle = _candle(x=10, y=0, width=20, height=10)
    edges = np.zeros((100, 100), dtype=np.uint8)
    edges[10 : 10 + line_length, 10] = 255

    evidence = resolver._evaluate_candidate(
        edges=edges,
        candle=candle,
        candidate_id="candidate",
    )

    assert evidence.status is expected_status


@pytest.mark.parametrize(
    ("line_x", "expected_status"),
    (
        (15, CandleOverlayEvidenceStatus.EXPIRY_OVERLAY),
        (16, CandleOverlayEvidenceStatus.NO_EVIDENCE),
    ),
)
def test_horizontal_alignment_boundary_is_inclusive(
    line_x: int,
    expected_status: CandleOverlayEvidenceStatus,
) -> None:
    resolver = PocketOptionExpiryOverlayEvidenceResolver()
    candle = _candle(x=10, y=0, width=20, height=10)
    edges = np.zeros((100, 100), dtype=np.uint8)
    edges[10:90, line_x] = 255

    evidence = resolver._evaluate_candidate(
        edges=edges,
        candle=candle,
        candidate_id="candidate",
    )

    assert evidence.status is expected_status


@pytest.mark.parametrize(
    ("contact_gap", "expected_status"),
    (
        (3, CandleOverlayEvidenceStatus.EXPIRY_OVERLAY),
        (4, CandleOverlayEvidenceStatus.NO_EVIDENCE),
    ),
)
def test_contact_gap_ratio_boundary_is_inclusive(
    contact_gap: int,
    expected_status: CandleOverlayEvidenceStatus,
) -> None:
    resolver = PocketOptionExpiryOverlayEvidenceResolver()
    candle = _candle(x=10, y=0, width=20, height=10)
    edges = np.zeros((120, 100), dtype=np.uint8)
    edges[10 + contact_gap : 110, 10] = 255

    evidence = resolver._evaluate_candidate(
        edges=edges,
        candle=candle,
        candidate_id="candidate",
    )

    assert evidence.status is expected_status


@pytest.mark.parametrize(
    ("height", "expected_status"),
    (
        (16, CandleOverlayEvidenceStatus.EXPIRY_OVERLAY),
        (17, CandleOverlayEvidenceStatus.NO_EVIDENCE),
    ),
)
def test_cap_height_to_width_boundary_is_inclusive(
    height: int,
    expected_status: CandleOverlayEvidenceStatus,
) -> None:
    resolver = PocketOptionExpiryOverlayEvidenceResolver()
    candle = _candle(x=10, y=0, width=20, height=height)
    edges = np.zeros((120, 100), dtype=np.uint8)
    edges[height:110, 10] = 255

    evidence = resolver._evaluate_candidate(
        edges=edges,
        candle=candle,
        candidate_id="candidate",
    )

    assert evidence.status is expected_status


def test_vertical_edge_interruption_boundary_is_inclusive() -> None:
    resolver = PocketOptionExpiryOverlayEvidenceResolver()

    accepted = resolver._longest_run(
        active_rows=np.array((0, 4), dtype=np.int64),
        maximum_interruption=3,
    )
    split = resolver._longest_run(
        active_rows=np.array((0, 5), dtype=np.int64),
        maximum_interruption=3,
    )

    assert accepted == (0, 4)
    assert split == (0, 0)


def test_evidence_trace_rejects_unknown_or_misaligned_candidate_ids() -> None:
    evidence = CandleOverlayEvidence(
        candidate_id="unexpected",
        status=CandleOverlayEvidenceStatus.NO_EVIDENCE,
        vertical_line_support_ratio=0.0,
        contact_gap_ratio=0.0,
        horizontal_alignment_ratio=0.0,
        cap_height_to_width_ratio=1.0,
        wickless=False,
        diagnostic="test",
    )

    with pytest.raises(ValueError, match="alineada"):
        CandleOverlayEvidenceTrace(
            evaluated_candidate_ids=("expected",),
            evidence=(evidence,),
        )


def test_overlay_evidence_requires_complete_line_geometry() -> None:
    with pytest.raises(ValueError, match="conjuntamente"):
        CandleOverlayEvidence(
            candidate_id="candidate",
            status=CandleOverlayEvidenceStatus.NO_EVIDENCE,
            vertical_line_support_ratio=0.5,
            contact_gap_ratio=0.0,
            horizontal_alignment_ratio=0.0,
            cap_height_to_width_ratio=1.0,
            wickless=False,
            diagnostic="test",
            vertical_line_x=10,
        )


def test_evidence_trace_rejects_duplicate_candidate_ids() -> None:
    evidence = CandleOverlayEvidence(
        candidate_id="candidate",
        status=CandleOverlayEvidenceStatus.NO_EVIDENCE,
        vertical_line_support_ratio=0.0,
        contact_gap_ratio=0.0,
        horizontal_alignment_ratio=0.0,
        cap_height_to_width_ratio=1.0,
        wickless=False,
        diagnostic="test",
    )

    with pytest.raises(ValueError, match="repetirse"):
        CandleOverlayEvidenceTrace(
            evaluated_candidate_ids=("candidate", "candidate"),
            evidence=(evidence, evidence),
        )


def test_overlay_contracts_are_immutable_and_runtime_typed() -> None:
    evidence = CandleOverlayEvidence(
        candidate_id="candidate",
        status=CandleOverlayEvidenceStatus.NO_EVIDENCE,
        vertical_line_support_ratio=0.0,
        contact_gap_ratio=0.0,
        horizontal_alignment_ratio=0.0,
        cap_height_to_width_ratio=1.0,
        wickless=False,
        diagnostic="test",
    )
    trace = CandleOverlayEvidenceTrace(
        evaluated_candidate_ids=("candidate",),
        evidence=(evidence,),
    )

    with pytest.raises(FrozenInstanceError):
        evidence.diagnostic = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        trace.evidence = ()  # type: ignore[misc]
    assert get_type_hints(CandleOverlayEvidence)
    assert get_type_hints(CandleOverlayEvidenceTrace)
    assert get_type_hints(PocketOptionExpiryOverlayEvidenceResolver.resolve)
