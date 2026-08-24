from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import VisualPriceReferenceResult
from pocket_option_analyzer.infrastructure.evidence import VisualEvidenceSerializer
from pocket_option_analyzer.vision.models import (
    CandleAnalysisResult,
    CandleCandidate,
    CandleCandidateTrace,
    CandleDetectionResult,
    CandleDetectionTrace,
    CandleFilterConfigurationTrace,
    CandleFilterResult,
    CandleMergeTrace,
    CandleObservability,
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
    CandleObservabilityAnalyzer,
    MarketAnalysisPipeline,
    PocketOptionCurrentVisualPriceExtractor,
)


@pytest.mark.parametrize(
    "model",
    (
        CandleCandidateTrace,
        CandleCandidate,
        CandleMergeTrace,
        CandleObservability,
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
        VisualPriceReferenceResult,
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
    assert get_type_hints(CandleObservabilityAnalyzer.analyze)["return"] is (
        CandleObservability
    )
    assert get_type_hints(CandleObservability.close_boundary_for)
    assert get_type_hints(CandleObservability.fully_observable_close_for)
    assert get_type_hints(
        VisualStrategySignalAnalysisPipeline._price_reference_analysis
    )
    assert get_type_hints(VisualStrategySignalAnalysisPipeline._with_reference_roles)
    assert get_type_hints(VisualEvidenceSerializer._observability_to_dict)
