import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleFilterDiagnostics,
    CandleSeries,
    CandleType,
    ChartRegion,
    ClassifiedCandle,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


class FakeCandleAnalysisPipeline:
    last_detection_diagnostics = CandleFilterDiagnostics(
        input_count=23,
        dimension_valid_count=19,
        width_valid_count=12,
        merged_count=12,
        returned_count=12,
        dominant_width=34.0,
    )

    def __init__(self) -> None:
        self.received_image: np.ndarray | None = None

    def analyze(self, image):
        self.received_image = image
        return [
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=20,
                    width=5,
                    height=30,
                    area=150,
                    color=CandleColor.GREEN,
                ),
                candle_type=CandleType.BULLISH,
            )
        ]


class FakeSeriesBuilder:
    def build(self, candles):
        return CandleSeries(
            candles=tuple(candles),
        )


class FakeTrendDetector:
    def detect(self, series):
        return TrendDirection.BULLISH


class FakeCurrentVisualPriceExtractor:
    def __init__(
        self,
        result: CurrentVisualPriceExtraction,
    ) -> None:
        self.result = result
        self.received_image: np.ndarray | None = None

    def extract(
        self,
        image: np.ndarray,
    ) -> CurrentVisualPriceExtraction:
        self.received_image = image
        return self.result


def test_analyze_returns_market_analysis() -> None:

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert len(result.series) == 1
    assert result.trend is TrendDirection.BULLISH


def test_market_analysis_preserves_detection_diagnostics() -> None:

    candle_pipeline = FakeCandleAnalysisPipeline()

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert result.detection_diagnostics is (candle_pipeline.last_detection_diagnostics)


def test_market_analysis_has_no_current_visual_price_without_extractor() -> None:
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert result.current_visual_price is None


def test_market_analysis_preserves_current_visual_price_extraction() -> None:
    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    price = CurrentVisualPrice(
        roi_y=40.0,
        normalized_roi_y=1.0 - 40.0 / 99.0,
        roi_width=100,
        roi_height=100,
        source="pocket_option_right_band_v1",
        confidence=0.9,
    )

    extraction = CurrentVisualPriceExtraction(
        price=price,
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=95.0,
        selected_y=40.0,
        confidence=0.9,
    )

    extractor = FakeCurrentVisualPriceExtractor(
        result=extraction,
    )

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    result = pipeline.analyze(image)

    assert result.current_visual_price is extraction
    assert extractor.received_image is image


def test_analyze_routes_each_image_to_its_exclusive_consumer() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    price_observation_image = np.zeros((20, 100, 3), dtype=np.uint8)
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
    )
    candle_pipeline = FakeCandleAnalysisPipeline()
    extractor = FakeCurrentVisualPriceExtractor(result=extraction)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    pipeline.analyze(
        image=image,
        price_observation_image=price_observation_image,
    )

    assert candle_pipeline.received_image is image
    assert extractor.received_image is price_observation_image


def test_analyze_uses_main_image_for_visual_price_when_second_image_is_none() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
    )
    candle_pipeline = FakeCandleAnalysisPipeline()
    extractor = FakeCurrentVisualPriceExtractor(result=extraction)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    pipeline.analyze(image=image, price_observation_image=None)

    assert candle_pipeline.received_image is image
    assert extractor.received_image is image


def test_market_analysis_preserves_capture_geometry_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        chart_region=chart_region,
        price_observation_region=price_region,
    )

    assert result.chart_region is chart_region
    assert result.price_observation_region is price_region
