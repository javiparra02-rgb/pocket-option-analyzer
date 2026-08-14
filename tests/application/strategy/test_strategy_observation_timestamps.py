from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparisonContext,
    StrategyObservation,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
    TrendDirection,
)


def _observation(
    instant: datetime,
    **evidence,
) -> StrategyObservation:
    entry_reference = evidence.pop("entry_reference", None)
    return StrategyObservation(
        observed_at=instant,
        candle_interval_started_at=instant.replace(microsecond=0),
        audit=SimpleNamespace(),  # type: ignore[arg-type]
        trend=TrendDirection.SIDEWAYS,
        indicators=SimpleNamespace(),  # type: ignore[arg-type]
        resolve_at=instant + timedelta(seconds=10),
        direction=SignalDirection.CALL,
        entry_reference=entry_reference,
        **evidence,
    )


def _comparison_context() -> CurrentVisualPriceComparisonContext:
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(50.0, 0.5, 100, 101, "test", 0.9),
        status=CurrentVisualPriceStatus.OK,
    )
    result = VisualPriceReferenceResult(
        reference=VisualPriceReference(0.5),
        status=VisualPriceReferenceStatus.OK,
        anchor_top_roi_y=10,
        anchor_bottom_roi_y=90,
    )
    return CurrentVisualPriceComparisonContext(
        current_visual_price=extraction,
        chart_region=None,
        price_observation_region=None,
        reference_result=result,
    )


def test_observation_normalizes_all_timestamps_to_utc() -> None:
    local_instant = datetime(
        2026,
        8,
        9,
        12,
        0,
        tzinfo=timezone(timedelta(hours=-4)),
    )

    observation = _observation(local_instant)

    assert observation.observed_at == datetime(2026, 8, 9, 16, 0, tzinfo=UTC)
    assert observation.resolve_at == datetime(2026, 8, 9, 16, 0, 10, tzinfo=UTC)
    assert observation.candle_interval_started_at.tzinfo is UTC
    assert observation.visual_price_comparison_context is None


def test_observation_rejects_timezone_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        _observation(datetime(2026, 8, 9, 12, 0))


def test_observation_derives_legacy_evidence_from_canonical_context() -> None:
    context = _comparison_context()

    observation = _observation(
        datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        visual_price_comparison_context=context,
    )

    assert observation.current_visual_price is context.current_visual_price
    assert observation.entry_reference_result is context.reference_result
    assert observation.entry_reference is context.reference_result.reference


@pytest.mark.parametrize(
    ("evidence", "field_name"),
    (
        (
            {
                "current_visual_price": CurrentVisualPriceExtraction(
                    price=None,
                    status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
                )
            },
            "current_visual_price",
        ),
        ({"entry_reference": VisualPriceReference(0.7)}, "entry_reference"),
        (
            {
                "entry_reference_result": VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
                )
            },
            "entry_reference_result",
        ),
    ),
)
def test_observation_rejects_legacy_evidence_that_conflicts_with_context(
    evidence: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        _observation(
            datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
            visual_price_comparison_context=_comparison_context(),
            **evidence,
        )
