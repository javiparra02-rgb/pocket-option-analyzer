import json
from datetime import UTC, datetime, timedelta

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonContext,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
    DirectionConditionAudit,
    PriceMovement,
    StrategyCondition,
    StrategyConditionAudit,
    StrategyConditionResult,
    StrategyObservation,
    StrategyObservationOutcome,
    StrategyObservationResolution,
    VisualPriceMovementClassification,
    VisualPriceMovementClassificationDiagnostic,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceMovement,
    VisualReferenceResolution,
    VisualReferenceValidation,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.infrastructure.signals import (
    JsonlStrategyObservationWriter,
)
from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
    TrendDirection,
)


def _direction(direction: SignalDirection) -> DirectionConditionAudit:
    return DirectionConditionAudit(
        direction=direction,
        conditions=(
            StrategyConditionResult(StrategyCondition.TREND, True),
            StrategyConditionResult(
                StrategyCondition.RSI_RANGE,
                False,
                "RSI blocks",
            ),
        ),
    )


def _exit_context(
    reference_result: VisualPriceReferenceResult,
    current_visual_price: CurrentVisualPriceExtraction | None = None,
) -> CurrentVisualPriceComparisonContext:
    return CurrentVisualPriceComparisonContext(
        current_visual_price=current_visual_price,
        chart_region=None,
        price_observation_region=None,
        reference_result=reference_result,
    )


@pytest.mark.parametrize("value", (1.0540983606557377, -0.04))
def test_writer_preserves_unclamped_affine_reference_schema(
    tmp_path,
    value: float,
) -> None:
    instant = datetime(2026, 8, 23, 1, 42, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    anchors = (("bullish", 1.0, 0.8, 0.6, 0.0),)
    reference = VisualPriceReference(value=value, anchor_shape=anchors)

    JsonlStrategyObservationWriter(path).write_reference_validation(
        VisualReferenceValidation(
            snapshot_id=instant.isoformat(),
            observed_at=instant,
            resolve_at=instant + timedelta(seconds=10),
            entry_reference=reference,
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = payload["entry_reference"]
    assert set(serialized) == {
        "value",
        "normalized_close",
        "anchor_shape",
        "source",
    }
    assert serialized["value"] == value
    assert serialized["normalized_close"] == value
    assert serialized["anchor_shape"] == [list(anchor) for anchor in anchors]
    assert serialized["source"] == reference.source


def test_writer_serializes_structured_audit_and_indicators(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )

    reference_result = VisualPriceReferenceResult(
        reference=reference,
        status=VisualPriceReferenceStatus.OK,
        anchor_count=27,
        latest_candle_type="bullish",
        latest_candidate_x=620,
        latest_candidate_y=480,
        close_roi_y=514,
        anchor_top_roi_y=400,
        anchor_bottom_roi_y=700,
        raw_normalized_close=0.42,
    )
    observation = StrategyObservation(
        observed_at=instant,
        candle_interval_started_at=instant,
        audit=StrategyConditionAudit(
            call=_direction(SignalDirection.CALL),
            put=_direction(SignalDirection.PUT),
        ),
        trend=TrendDirection.BULLISH,
        indicators=IndicatorSnapshot(
            ema=EmaSnapshot(10.0, 9.0, 4),
            rsi=RsiSnapshot(60.0),
            stochastic=StochasticSnapshot(30.0, 20.0, 10.0, 15.0),
        ),
        resolve_at=instant + timedelta(seconds=10),
        direction=SignalDirection.CALL,
        entry_reference=reference,
        entry_reference_result=reference_result,
    )
    path = tmp_path / "observations.jsonl"

    JsonlStrategyObservationWriter(path).write(observation)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["snapshot_id"] == instant.isoformat()
    assert payload["call"]["passed_count"] == 1
    assert payload["call"]["conditions"]["rsi_range"]["passed"] is False
    assert payload["call"]["blockers"] == ["RSI blocks"]
    assert payload["indicators"]["stochastic"]["previous_d"] == 15.0
    assert payload["event_type"] == "observation"
    assert payload["resolve_at"] == (instant + timedelta(seconds=10)).isoformat()
    assert payload["direction"] == "call"
    assert payload["entry_reference"]["value"] == 0.42
    assert payload["entry_reference"]["normalized_close"] == 0.42
    assert payload["entry_reference_diagnostic"]["status"] == "ok"
    assert payload["entry_reference_diagnostic"]["anchor_count"] == 27
    assert payload["entry_reference_diagnostic"]["latest_candle_type"] == "bullish"
    assert payload["entry_reference_diagnostic"]["close_roi_y"] == 514
    assert payload["entry_reference_diagnostic"]["raw_normalized_close"] == 0.42
    assert payload["current_visual_price"] is None
    assert payload["outcome"] == "unresolved"


def test_writer_appends_resolution_event(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    anchors = (("bullish", 1.0, 0.8, 0.6, 0.0),)
    reference = VisualPriceReference(0.42, anchor_shape=anchors)
    exit_extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(
            roi_y=514.0,
            normalized_roi_y=0.73125,
            roi_width=1320,
            roi_height=800,
            source="current_visual_price_roi_v1",
            confidence=0.92,
        ),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )
    exit_reference = VisualPriceReference(0.45, anchor_shape=anchors)
    exit_reference_result = VisualPriceReferenceResult(
        reference=exit_reference,
        status=VisualPriceReferenceStatus.OK,
        anchor_count=27,
        latest_candle_type="bullish",
        latest_candidate_x=1042,
        latest_candidate_y=11,
        close_roi_y=354,
        anchor_top_roi_y=11,
        anchor_bottom_roi_y=787,
        raw_normalized_close=0.5579896907216495,
    )
    resolution = StrategyObservationResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        direction=SignalDirection.CALL,
        entry_reference=reference,
        exit_reference=exit_reference,
        outcome=StrategyObservationOutcome.WIN,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=_exit_context(
            exit_reference_result,
            exit_extraction,
        ),
        visual_price_comparison=CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.AVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ),
            entry_anchored_value=0.25,
            exit_anchored_value=0.75,
            delta=0.5,
            entry_price_y_in_chart_roi=250.0,
            exit_price_y_in_chart_roi=150.0,
            entry_anchor_span_px=200.0,
            exit_anchor_span_px=200.0,
        ),
        visual_price_movement_classification=(
            VisualPriceMovementClassification(
                movement=PriceMovement.UNRESOLVED,
                epsilon=None,
                pixel_tolerance=None,
                diagnostic=(
                    VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
                ),
            )
        ),
    )

    JsonlStrategyObservationWriter(path).write_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event_type"] == "resolution"
    assert payload["resolved_at"] == (instant + timedelta(seconds=11)).isoformat()
    assert payload["exit_reference"]["value"] == 0.45
    assert payload["exit_reference_diagnostic"] == {
        "status": "ok",
        "anchor_count": 27,
        "latest_candle_type": "bullish",
        "latest_candidate_x": 1042,
        "latest_candidate_y": 11,
        "close_roi_y": 354,
        "anchor_top_roi_y": 11,
        "anchor_bottom_roi_y": 787,
        "raw_normalized_close": 0.5579896907216495,
    }
    assert payload["exit_current_visual_price"] == {
        "status": "ok",
        "candidate_count": 1,
        "selected_x": 1268.5,
        "selected_y": 514.0,
        "confidence": 0.92,
        "diagnostic": None,
        "price": {
            "roi_y": 514.0,
            "normalized_roi_y": 0.73125,
            "roi_width": 1320,
            "roi_height": 800,
            "source": "current_visual_price_roi_v1",
            "confidence": 0.92,
        },
    }
    assert payload["visual_price_comparison"] == {
        "status": "available",
        "diagnostic": "comparison_available",
        "entry_anchored_value": 0.25,
        "exit_anchored_value": 0.75,
        "delta": 0.5,
        "entry_price_y_in_chart_roi": 250.0,
        "exit_price_y_in_chart_roi": 150.0,
        "entry_anchor_span_px": 200.0,
        "exit_anchor_span_px": 200.0,
    }
    assert payload["visual_price_movement_classification"] == {
        "movement": "unresolved",
        "epsilon": None,
        "pixel_tolerance": None,
        "diagnostic": "epsilon_not_calibrated",
    }
    assert payload["outcome"] == "win"


def test_writer_serializes_null_exit_visual_price_for_resolution(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    resolution = StrategyObservationResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        direction=SignalDirection.CALL,
        entry_reference=reference,
        exit_reference=None,
        outcome=StrategyObservationOutcome.UNRESOLVED,
        exit_current_visual_price=None,
    )

    JsonlStrategyObservationWriter(path).write_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["exit_current_visual_price"] is None
    assert payload["exit_reference_diagnostic"] is None
    assert payload["visual_price_comparison"] is None
    assert payload["visual_price_movement_classification"] is None


def test_writer_appends_passive_reference_events(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    exit_extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=2,
        diagnostic="no candidate matched the visual price mask",
    )
    exit_reference = VisualPriceReference(
        0.45,
        anchor_shape=reference.anchor_shape,
    )
    exit_reference_result = VisualPriceReferenceResult(
        reference=exit_reference,
        status=VisualPriceReferenceStatus.OK,
        anchor_count=25,
        latest_candle_type="bullish",
        latest_candidate_x=1042,
        latest_candidate_y=11,
        close_roi_y=354,
        anchor_top_roi_y=11,
        anchor_bottom_roi_y=787,
        raw_normalized_close=0.5579896907216495,
    )
    writer = JsonlStrategyObservationWriter(path)
    writer.write_reference_validation(
        VisualReferenceValidation(
            snapshot_id=instant.isoformat(),
            observed_at=instant,
            resolve_at=instant + timedelta(seconds=10),
            entry_reference=reference,
        )
    )
    writer.write_reference_resolution(
        VisualReferenceResolution(
            snapshot_id=instant.isoformat(),
            observed_at=instant,
            resolve_at=instant + timedelta(seconds=10),
            resolved_at=instant + timedelta(seconds=11),
            entry_reference=reference,
            exit_reference=exit_reference,
            movement=VisualReferenceMovement.UP,
            exit_current_visual_price=exit_extraction,
            exit_visual_price_context=_exit_context(
                exit_reference_result,
                exit_extraction,
            ),
            visual_price_comparison=CurrentVisualPriceComparison(
                status=CurrentVisualPriceComparisonStatus.AVAILABLE,
                diagnostic=(
                    CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
                ),
                entry_anchored_value=0.42,
                exit_anchored_value=0.42,
                delta=0.0,
                entry_price_y_in_chart_roi=514.0,
                exit_price_y_in_chart_roi=514.0,
                entry_anchor_span_px=256.0,
                exit_anchor_span_px=256.0,
            ),
            visual_price_movement_classification=(
                VisualPriceMovementClassification(
                    movement=PriceMovement.FLAT,
                    epsilon=0.0078125,
                    pixel_tolerance=1.0,
                    diagnostic=(
                        VisualPriceMovementClassificationDiagnostic.CLASSIFIED
                    ),
                )
            ),
        )
    )

    payloads = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert [payload["event_type"] for payload in payloads] == [
        "reference_validation",
        "reference_resolution",
    ]
    assert payloads[0]["entry_reference"]["value"] == 0.42
    assert payloads[1]["exit_reference"]["value"] == 0.45
    assert payloads[1]["exit_reference_diagnostic"] == {
        "status": "ok",
        "anchor_count": 25,
        "latest_candle_type": "bullish",
        "latest_candidate_x": 1042,
        "latest_candidate_y": 11,
        "close_roi_y": 354,
        "anchor_top_roi_y": 11,
        "anchor_bottom_roi_y": 787,
        "raw_normalized_close": 0.5579896907216495,
    }
    assert payloads[1]["movement"] == "up"
    assert payloads[1]["exit_current_visual_price"] == {
        "status": "no_visual_price_candidate",
        "candidate_count": 2,
        "selected_x": None,
        "selected_y": None,
        "confidence": None,
        "diagnostic": "no candidate matched the visual price mask",
        "price": None,
    }
    assert payloads[1]["visual_price_comparison"]["delta"] == 0.0
    assert payloads[1]["visual_price_comparison"]["entry_anchor_span_px"] == 256.0
    assert payloads[1]["visual_price_comparison"]["exit_anchor_span_px"] == 256.0
    assert payloads[1]["visual_price_movement_classification"] == {
        "movement": "flat",
        "epsilon": 0.0078125,
        "pixel_tolerance": 1.0,
        "diagnostic": "classified",
    }


def test_writer_serializes_null_exit_visual_price_for_reference_resolution(
    tmp_path,
) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    resolution = VisualReferenceResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        entry_reference=reference,
        exit_reference=None,
        movement=VisualReferenceMovement.UNRESOLVED,
        diagnostic="missing_exit_reference",
        exit_current_visual_price=None,
    )

    JsonlStrategyObservationWriter(path).write_reference_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["exit_current_visual_price"] is None
    assert payload["exit_reference_diagnostic"] is None
    assert payload["visual_price_comparison"] is None
    assert payload["visual_price_movement_classification"] is None


def test_writer_serializes_unavailable_visual_price_comparison(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    resolution = VisualReferenceResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        entry_reference=reference,
        exit_reference=None,
        movement=VisualReferenceMovement.UNRESOLVED,
        visual_price_comparison=CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.EXIT_GEOMETRY_MISSING
            ),
        ),
        visual_price_movement_classification=(
            VisualPriceMovementClassification(
                movement=PriceMovement.UNRESOLVED,
                epsilon=None,
                pixel_tolerance=1.0,
                diagnostic=(
                    VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
                ),
            )
        ),
    )

    JsonlStrategyObservationWriter(path).write_reference_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["visual_price_comparison"] == {
        "status": "unavailable",
        "diagnostic": "exit_geometry_missing",
        "entry_anchored_value": None,
        "exit_anchored_value": None,
        "delta": None,
        "entry_price_y_in_chart_roi": None,
        "exit_price_y_in_chart_roi": None,
        "entry_anchor_span_px": None,
        "exit_anchor_span_px": None,
    }
    assert payload["visual_price_movement_classification"] == {
        "movement": "unresolved",
        "epsilon": None,
        "pixel_tolerance": 1.0,
        "diagnostic": "comparison_unavailable",
    }


@pytest.mark.parametrize(
    ("movement", "epsilon", "pixel_tolerance"),
    [
        (PriceMovement.UP, 0.012345678901234567, 1.2345678901234567),
        (PriceMovement.DOWN, 0.0078125, 1.0),
        (PriceMovement.FLAT, 0.0, 0.0),
    ],
)
def test_writer_serializes_shadow_movement_without_rounding(
    tmp_path,
    movement: PriceMovement,
    epsilon: float,
    pixel_tolerance: float,
) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / f"{movement.value}.jsonl"
    reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    resolution = StrategyObservationResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        direction=SignalDirection.CALL,
        entry_reference=reference,
        exit_reference=reference,
        outcome=StrategyObservationOutcome.UNRESOLVED,
        visual_price_movement_classification=(
            VisualPriceMovementClassification(
                movement=movement,
                epsilon=epsilon,
                pixel_tolerance=pixel_tolerance,
                diagnostic=(
                    VisualPriceMovementClassificationDiagnostic.CLASSIFIED
                ),
            )
        ),
    )

    JsonlStrategyObservationWriter(path).write_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["visual_price_movement_classification"] == {
        "movement": movement.value,
        "epsilon": epsilon,
        "pixel_tolerance": pixel_tolerance,
        "diagnostic": "classified",
    }
    assert payload["outcome"] == "unresolved"


def test_writer_serializes_missing_reference_diagnostic(tmp_path) -> None:
    instant = datetime(
        2026,
        8,
        9,
        12,
        0,
        tzinfo=UTC,
    )

    path = tmp_path / "observations.jsonl"

    diagnostic = VisualPriceReferenceResult(
        reference=None,
        status=VisualPriceReferenceStatus.CLOSE_OUTSIDE_ANCHOR_RANGE,
        anchor_count=27,
        latest_candle_type="bullish",
        latest_candidate_x=620,
        latest_candidate_y=480,
        close_roi_y=514,
        anchor_top_roi_y=526,
        anchor_bottom_roi_y=782,
        raw_normalized_close=1.046875,
    )

    validation = VisualReferenceValidation(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        entry_reference=None,
        entry_reference_result=diagnostic,
    )

    writer = JsonlStrategyObservationWriter(path)

    writer.write_reference_validation(
        validation,
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["event_type"] == "reference_validation"
    assert payload["entry_reference"] is None

    reference_diagnostic = payload["entry_reference_diagnostic"]

    assert reference_diagnostic["status"] == "close_outside_anchor_range"
    assert reference_diagnostic["anchor_count"] == 27
    assert reference_diagnostic["latest_candle_type"] == "bullish"
    assert reference_diagnostic["latest_candidate_x"] == 620
    assert reference_diagnostic["latest_candidate_y"] == 480
    assert reference_diagnostic["close_roi_y"] == 514
    assert reference_diagnostic["anchor_top_roi_y"] == 526
    assert reference_diagnostic["anchor_bottom_roi_y"] == 782
    assert reference_diagnostic["raw_normalized_close"] == 1.046875


def test_writer_serializes_failed_exit_reference_diagnostic(tmp_path) -> None:
    instant = datetime(2026, 8, 16, 22, 47, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"
    entry_reference = VisualPriceReference(
        0.42,
        anchor_shape=(("bullish", 1.0, 0.8, 0.6, 0.0),),
    )
    exit_reference_result = VisualPriceReferenceResult(
        reference=None,
        status=VisualPriceReferenceStatus.CLOSE_OUTSIDE_ANCHOR_RANGE,
        anchor_count=26,
        latest_candle_type="bullish",
        latest_candidate_x=712,
        latest_candidate_y=11,
        close_roi_y=11,
        anchor_top_roi_y=123,
        anchor_bottom_roi_y=787,
        raw_normalized_close=1.1686746987951808,
    )
    resolution = VisualReferenceResolution(
        snapshot_id=instant.isoformat(),
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        resolved_at=instant + timedelta(seconds=11),
        entry_reference=entry_reference,
        exit_reference=None,
        movement=VisualReferenceMovement.UNRESOLVED,
        diagnostic="missing_exit_reference",
        exit_visual_price_context=_exit_context(exit_reference_result),
    )

    JsonlStrategyObservationWriter(path).write_reference_resolution(resolution)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event_type"] == "reference_resolution"
    assert payload["exit_reference"] is None
    assert payload["movement"] == "unresolved"
    assert payload["diagnostic"] == "missing_exit_reference"
    assert payload["exit_reference_diagnostic"] == {
        "status": "close_outside_anchor_range",
        "anchor_count": 26,
        "latest_candle_type": "bullish",
        "latest_candidate_x": 712,
        "latest_candidate_y": 11,
        "close_roi_y": 11,
        "anchor_top_roi_y": 123,
        "anchor_bottom_roi_y": 787,
        "raw_normalized_close": 1.1686746987951808,
    }
    assert payload["visual_price_comparison"] is None
    assert payload["visual_price_movement_classification"] is None


def test_writer_serializes_current_visual_price_for_observation(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(
            roi_y=514.0,
            normalized_roi_y=0.73125,
            roi_width=1320,
            roi_height=800,
            source="current_visual_price_roi_v1",
            confidence=0.92,
        ),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )
    observation = StrategyObservation(
        observed_at=instant,
        candle_interval_started_at=instant,
        audit=StrategyConditionAudit(
            call=_direction(SignalDirection.CALL),
            put=_direction(SignalDirection.PUT),
        ),
        trend=TrendDirection.BULLISH,
        indicators=IndicatorSnapshot(
            ema=EmaSnapshot(10.0, 9.0, 4),
            rsi=RsiSnapshot(60.0),
            stochastic=StochasticSnapshot(30.0, 20.0, 10.0, 15.0),
        ),
        resolve_at=instant + timedelta(seconds=10),
        direction=None,
        entry_reference=None,
        current_visual_price=extraction,
    )
    path = tmp_path / "observations.jsonl"

    JsonlStrategyObservationWriter(path).write(observation)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["current_visual_price"] == {
        "status": "ok",
        "candidate_count": 1,
        "selected_x": 1268.5,
        "selected_y": 514.0,
        "confidence": 0.92,
        "diagnostic": None,
        "price": {
            "roi_y": 514.0,
            "normalized_roi_y": 0.73125,
            "roi_width": 1320,
            "roi_height": 800,
            "source": "current_visual_price_roi_v1",
            "confidence": 0.92,
        },
    }


def test_writer_serializes_unavailable_current_visual_price_for_validation(
    tmp_path,
) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        diagnostic="no candidate matched the visual price mask",
    )
    path = tmp_path / "observations.jsonl"

    JsonlStrategyObservationWriter(path).write_reference_validation(
        VisualReferenceValidation(
            snapshot_id=instant.isoformat(),
            observed_at=instant,
            resolve_at=instant + timedelta(seconds=10),
            entry_reference=None,
            current_visual_price=extraction,
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["current_visual_price"] == {
        "status": "no_visual_price_candidate",
        "candidate_count": 0,
        "selected_x": None,
        "selected_y": None,
        "confidence": None,
        "diagnostic": "no candidate matched the visual price mask",
        "price": None,
    }


def test_writer_serializes_null_current_visual_price(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "observations.jsonl"

    JsonlStrategyObservationWriter(path).write_reference_validation(
        VisualReferenceValidation(
            snapshot_id=instant.isoformat(),
            observed_at=instant,
            resolve_at=instant + timedelta(seconds=10),
            entry_reference=None,
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["current_visual_price"] is None
