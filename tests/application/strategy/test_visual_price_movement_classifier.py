from dataclasses import FrozenInstanceError
from math import inf, nan, nextafter

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
    PriceMovement,
    VisualPriceMovementClassification,
    VisualPriceMovementClassificationDiagnostic,
    VisualPriceMovementClassifier,
)


def _available_comparison(
    delta: float,
    *,
    entry_span: float = 100.0,
    exit_span: float = 100.0,
) -> CurrentVisualPriceComparison:
    return CurrentVisualPriceComparison(
        status=CurrentVisualPriceComparisonStatus.AVAILABLE,
        diagnostic=(
            CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
        ),
        entry_anchored_value=0.5,
        exit_anchored_value=0.5 + delta,
        delta=delta,
        entry_price_y_in_chart_roi=100.0,
        exit_price_y_in_chart_roi=100.0,
        entry_anchor_span_px=entry_span,
        exit_anchor_span_px=exit_span,
    )


def _unavailable_comparison() -> CurrentVisualPriceComparison:
    return CurrentVisualPriceComparison(
        status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
        diagnostic=(
            CurrentVisualPriceComparisonDiagnostic.EXIT_CONTEXT_MISSING
        ),
    )


def test_classification_model_is_immutable() -> None:
    classification = VisualPriceMovementClassifier(1.0).classify(
        _available_comparison(0.0),
    )

    with pytest.raises(FrozenInstanceError):
        classification.epsilon = 1.0  # type: ignore[misc]


def test_classified_model_requires_resolved_movement_and_numeric_policy() -> None:
    with pytest.raises(ValueError, match="movimiento resuelto"):
        VisualPriceMovementClassification(
            movement=PriceMovement.UNRESOLVED,
            epsilon=0.1,
            pixel_tolerance=1.0,
            diagnostic=VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
        )

    with pytest.raises(ValueError, match="requiere epsilon"):
        VisualPriceMovementClassification(
            movement=PriceMovement.UP,
            epsilon=None,
            pixel_tolerance=1.0,
            diagnostic=VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
        )


def test_unavailable_model_rejects_resolved_movement_or_epsilon() -> None:
    with pytest.raises(ValueError, match="UNRESOLVED"):
        VisualPriceMovementClassification(
            movement=PriceMovement.UP,
            epsilon=None,
            pixel_tolerance=None,
            diagnostic=(
                VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
            ),
        )

    with pytest.raises(ValueError, match="epsilon=None"):
        VisualPriceMovementClassification(
            movement=PriceMovement.UNRESOLVED,
            epsilon=0.1,
            pixel_tolerance=1.0,
            diagnostic=(
                VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
            ),
        )


@pytest.mark.parametrize("field_name", ("epsilon", "pixel_tolerance"))
@pytest.mark.parametrize("value", (True, nan, inf, -inf, "1.0"))
def test_classification_model_rejects_invalid_numeric_evidence(
    field_name: str,
    value: object,
) -> None:
    values = {
        "movement": PriceMovement.UP,
        "epsilon": 0.1,
        "pixel_tolerance": 1.0,
        "diagnostic": VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=field_name):
        VisualPriceMovementClassification(**values)  # type: ignore[arg-type]


def test_classification_model_rejects_invalid_enum_contracts() -> None:
    with pytest.raises(ValueError, match="movement"):
        VisualPriceMovementClassification(
            movement="up",  # type: ignore[arg-type]
            epsilon=0.1,
            pixel_tolerance=1.0,
            diagnostic=VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
        )

    with pytest.raises(ValueError, match="diagnostic"):
        VisualPriceMovementClassification(
            movement=PriceMovement.UP,
            epsilon=0.1,
            pixel_tolerance=1.0,
            diagnostic="classified",  # type: ignore[arg-type]
        )


def test_unavailable_comparison_is_unresolved_without_epsilon() -> None:
    classification = VisualPriceMovementClassifier(1.0).classify(
        _unavailable_comparison(),
    )

    assert classification.movement is PriceMovement.UNRESOLVED
    assert classification.epsilon is None
    assert classification.pixel_tolerance == 1.0
    assert (
        classification.diagnostic
        is VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
    )


def test_available_comparison_without_calibration_is_unresolved() -> None:
    classification = VisualPriceMovementClassifier().classify(
        _available_comparison(0.2),
    )

    assert classification.movement is PriceMovement.UNRESOLVED
    assert classification.epsilon is None
    assert classification.pixel_tolerance is None
    assert (
        classification.diagnostic
        is VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
    )


@pytest.mark.parametrize("pixel_tolerance", (-1.0, nan, inf, -inf))
def test_classifier_rejects_invalid_configuration(
    pixel_tolerance: float,
) -> None:
    with pytest.raises(ValueError, match="pixel_tolerance"):
        VisualPriceMovementClassifier(pixel_tolerance)


@pytest.mark.parametrize(
    "delta", (0.021, -0.021, 0.019, -0.019, 0.02, -0.02),
)
def test_i2_legacy_delta_and_configured_number_do_not_certify_movement(
    delta: float,
) -> None:
    classification = VisualPriceMovementClassifier(1.0).classify(
        _available_comparison(delta),
    )

    assert classification.movement is PriceMovement.UNRESOLVED
    assert classification.epsilon is None
    assert classification.pixel_tolerance == 1.0
    assert (
        classification.diagnostic
        is VisualPriceMovementClassificationDiagnostic.COMPARABILITY_NOT_VERIFIED
    )


def test_i2_values_outside_old_epsilon_are_still_unverified() -> None:
    epsilon = 0.02
    positive = nextafter(epsilon, inf)
    negative = nextafter(-epsilon, -inf)
    classifier = VisualPriceMovementClassifier(1.0)

    assert (
        classifier.classify(_available_comparison(positive)).movement
        is PriceMovement.UNRESOLVED
    )
    assert (
        classifier.classify(_available_comparison(negative)).movement
        is PriceMovement.UNRESOLVED
    )


def test_i2_different_spans_do_not_establish_a_noise_policy() -> None:
    classification = VisualPriceMovementClassifier(1.5).classify(
        _available_comparison(0.0, entry_span=100.0, exit_span=300.0),
    )

    assert classification.epsilon is None
    assert classification.movement is PriceMovement.UNRESOLVED


def test_i2_span_scaling_does_not_approve_a_tolerance() -> None:
    classifier = VisualPriceMovementClassifier(1.0)

    narrow = classifier.classify(
        _available_comparison(0.0, entry_span=100.0, exit_span=100.0),
    )
    wide = classifier.classify(
        _available_comparison(0.0, entry_span=400.0, exit_span=400.0),
    )

    assert narrow.epsilon is None
    assert wide.epsilon is None
    assert narrow.movement is wide.movement is PriceMovement.UNRESOLVED


def test_i2_zero_tolerance_is_not_an_accredited_policy() -> None:
    classifier = VisualPriceMovementClassifier(0.0)

    flat = classifier.classify(_available_comparison(0.0))
    up = classifier.classify(_available_comparison(0.000001))
    down = classifier.classify(_available_comparison(-0.000001))

    assert flat.movement is PriceMovement.UNRESOLVED
    assert up.movement is PriceMovement.UNRESOLVED
    assert down.movement is PriceMovement.UNRESOLVED
    assert flat.epsilon is None
    assert flat.pixel_tolerance == 0.0
