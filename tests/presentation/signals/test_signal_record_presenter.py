from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.presentation.signals import (
    SignalRecordPresenter,
)


def _record(
    direction: SignalDirection,
    strength: SignalStrength,
    reason: str = "Strategy conditions confirmed.",
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=strength,
            reason=reason,
        ),
        created_at=datetime(
            2026,
            1,
            1,
            10,
            30,
            45,
            tzinfo=timezone.utc,
        ),
        source="test_source",
    )


def test_presenter_formats_call_signal() -> None:

    presenter = SignalRecordPresenter()

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
        ),
    )

    assert view_model.direction_label == "CALL"
    assert view_model.strength_label == "ALTA"
    assert view_model.reason == "Strategy conditions confirmed."
    assert view_model.source == "test_source"
    assert view_model.created_at_label == "2026-01-01 10:30:45"
    assert view_model.is_actionable is True
    assert view_model.css_class == "signal-call"


def test_presenter_formats_put_signal() -> None:

    presenter = SignalRecordPresenter()

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.PUT,
            strength=SignalStrength.MEDIUM,
        ),
    )

    assert view_model.direction_label == "PUT"
    assert view_model.strength_label == "MEDIA"
    assert view_model.is_actionable is True
    assert view_model.css_class == "signal-put"


def test_presenter_formats_neutral_signal() -> None:

    presenter = SignalRecordPresenter()

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
        ),
    )

    assert view_model.direction_label == "SIN SEÑAL"
    assert view_model.strength_label == "NINGUNA"
    assert view_model.is_actionable is False
    assert view_model.css_class == "signal-neutral"


def test_presenter_formats_low_strength_signal() -> None:

    presenter = SignalRecordPresenter()

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.CALL,
            strength=SignalStrength.LOW,
        ),
    )

    assert view_model.strength_label == "BAJA"


def test_presenter_formats_strategy_diagnostics_in_multiple_lines() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: trend is not bullish, EMA separation is insufficient. "
        "PUT failed: trend is not bearish, stochastic did not cross down."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert view_model.reason == (
        "OTC Precision 10S conditions were not fully confirmed.\n\n"
        "CALL failed:\n"
        "  - trend is not bullish\n"
        "  - EMA separation is insufficient\n\n"
        "PUT failed:\n"
        "  - trend is not bearish\n"
        "  - stochastic did not cross down"
    )


def test_presenter_extracts_visual_diagnostics_from_reason() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual: Tendencia: BEARISH | "
        "Velas: 24 | Últimas: BEARISH, BULLISH, BULLISH | "
        "Cerradas: BEARISH, BEARISH, BULLISH | "
        "Contexto: BEARISH_PULLBACK | Entrada: ESPERAR\n"
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: trend is not bullish. "
        "PUT failed: recent closed candle is not bearish."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.visual_diagnostics_label
        == "Diagnóstico visual: Tendencia: BEARISH | "
        "Velas: 24 | Últimas: BEARISH, BULLISH, BULLISH | "
        "Cerradas: BEARISH, BEARISH, BULLISH | "
        "Contexto: BEARISH_PULLBACK | Entrada: ESPERAR"
    )
    assert "[visual_diagnostics]" not in view_model.reason


def test_presenter_hides_visual_diagnostics_from_reason_when_indicators_are_missing() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual: Tendencia: BEARISH | "
        "Velas: 9 | Últimas: BEARISH, BEARISH, BEARISH | "
        "Cerradas: BEARISH, BEARISH, BEARISH | "
        "Contexto: BEARISH_CONTINUATION | Entrada: BUSCAR_PUT\n"
        "Not enough visual candles to calculate indicators. "
        "Detected candles: 9. Minimum required: 13."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.visual_diagnostics_label
        == "Diagnóstico visual: Tendencia: BEARISH | "
        "Velas: 9 | Últimas: BEARISH, BEARISH, BEARISH | "
        "Cerradas: BEARISH, BEARISH, BEARISH | "
        "Contexto: BEARISH_CONTINUATION | Entrada: BUSCAR_PUT"
    )
    assert "[visual_diagnostics]" not in view_model.reason
    assert (
        view_model.reason
        == "Not enough visual candles to calculate indicators. "
        "Detected candles: 9. Minimum required: 13."
    )