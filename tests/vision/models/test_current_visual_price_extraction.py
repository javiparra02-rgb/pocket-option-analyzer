from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


def test_extraction_reports_available_price_when_status_is_ok() -> None:
    price = CurrentVisualPrice(
        roi_y=250.0,
        normalized_roi_y=0.5,
        roi_width=1200,
        roi_height=500,
        source="current_visual_price_roi_v1",
        confidence=0.9,
    )

    extraction = CurrentVisualPriceExtraction(
        price=price,
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1150.0,
        selected_y=250.0,
        confidence=0.9,
    )

    assert extraction.is_available
    assert extraction.price is price
    assert extraction.status is CurrentVisualPriceStatus.OK


def test_extraction_is_not_available_without_price() -> None:
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
    )

    assert extraction.is_available is False
    assert extraction.price is None


def test_extraction_is_not_available_when_status_is_not_ok() -> None:
    price = CurrentVisualPrice(
        roi_y=250.0,
        normalized_roi_y=0.5,
        roi_width=1200,
        roi_height=500,
        source="current_visual_price_roi_v1",
    )

    extraction = CurrentVisualPriceExtraction(
        price=price,
        status=CurrentVisualPriceStatus.LOW_CONFIDENCE,
        candidate_count=1,
    )

    assert extraction.is_available is False