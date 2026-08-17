from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.vision.models import (
    CandleAnalysisResult,
    CandleCandidateTrace,
    CandleDetectionResult,
    CandleDetectionTrace,
    CandleFilterConfigurationTrace,
    CandleFilterResult,
    CandleMergeTrace,
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceCandidateTrace,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceRejectionCounts,
    FinalCandleTrace,
    MarketAnalysis,
)
from pocket_option_analyzer.vision.services import (
    CandleAnalysisPipeline,
    CandleDetectionPipeline,
    CandleFilter,
    MarketAnalysisPipeline,
    PocketOptionCurrentVisualPriceExtractor,
)


@pytest.mark.parametrize(
    "model",
    (
        CandleCandidateTrace,
        CandleMergeTrace,
        CandleFilterConfigurationTrace,
        FinalCandleTrace,
        CandleDetectionTrace,
        CandleFilterResult,
        CandleDetectionResult,
        CandleAnalysisResult,
        CurrentVisualPriceCandidateTrace,
        CurrentVisualPriceRejectionCounts,
        CurrentVisualPriceDetectionTrace,
        CurrentVisualPriceAnalysis,
        MarketAnalysis,
    ),
)
def test_diagnostic_trace_model_type_hints_resolve_at_runtime(model: type) -> None:
    assert get_type_hints(model)


def test_diagnostic_trace_public_return_types_resolve_at_runtime() -> None:
    assert get_type_hints(CandleFilter.filter_with_trace)["return"] is (
        CandleFilterResult
    )
    assert get_type_hints(CandleDetectionPipeline.detect_with_trace)["return"] is (
        CandleDetectionResult
    )
    assert get_type_hints(CandleAnalysisPipeline.analyze_with_trace)["return"] is (
        CandleAnalysisResult
    )
    assert (
        get_type_hints(PocketOptionCurrentVisualPriceExtractor.extract_with_trace)[
            "return"
        ]
        is CurrentVisualPriceAnalysis
    )
    assert get_type_hints(MarketAnalysisPipeline.analyze)["return"] is MarketAnalysis
    assert get_type_hints(
        VisualStrategySignalAnalysisPipeline._price_reference_analysis
    )
    assert get_type_hints(VisualStrategySignalAnalysisPipeline._with_reference_roles)
