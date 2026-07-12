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
        "Las condiciones de OTC Precision 10S no fueron "
        "confirmadas completamente.\n\n"
        "Condiciones CALL no confirmadas:\n"
        "  - La tendencia visual no es alcista.\n"
        "  - La separación EMA es insuficiente.\n\n"
        "Condiciones PUT no confirmadas:\n"
        "  - La tendencia visual no es bajista.\n"
        "  - El Stochastic no confirmó cruce bajista."
    )


def test_presenter_extracts_visual_diagnostics_from_reason() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 24\n"
        "  Últimas: BEARISH, BULLISH, BULLISH\n"
        "  Cerradas: BEARISH, BEARISH, BULLISH\n"
        "  Direccionales: BEARISH, BEARISH, BULLISH\n"
        "  Contexto: BEARISH_PULLBACK\n"
        "  Vigilancia: ESPERAR\n"
        "  Estado: ESPERANDO_CONFIRMACION\n"
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
        == "Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 24\n"
        "  Últimas: BEARISH, BULLISH, BULLISH\n"
        "  Cerradas: BEARISH, BEARISH, BULLISH\n"
        "  Direccionales: BEARISH, BEARISH, BULLISH\n"
        "  Contexto: BEARISH_PULLBACK\n"
        "  Vigilancia: ESPERAR\n"
        "  Estado: ESPERANDO_CONFIRMACION"
    )
    assert "[visual_diagnostics]" not in view_model.reason
    assert "Tendencia: BEARISH" not in view_model.reason


def test_presenter_hides_visual_diagnostics_from_reason_when_indicators_are_missing() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 9\n"
        "  Últimas: BEARISH, BEARISH, BEARISH\n"
        "  Cerradas: BEARISH, BEARISH, BEARISH\n"
        "  Direccionales: BEARISH, BEARISH, BEARISH\n"
        "  Contexto: BEARISH_CONTINUATION\n"
        "  Vigilancia: VIGILAR_PUT\n"
        "  Estado: SIN_INDICADORES\n"
        "Not enough visual candles to calculate indicators. "
        "Detected candles: 9. Minimum visible required: 14. "
        "Minimum closed required: 13."
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
        == "Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 9\n"
        "  Últimas: BEARISH, BEARISH, BEARISH\n"
        "  Cerradas: BEARISH, BEARISH, BEARISH\n"
        "  Direccionales: BEARISH, BEARISH, BEARISH\n"
        "  Contexto: BEARISH_CONTINUATION\n"
        "  Vigilancia: VIGILAR_PUT\n"
        "  Estado: SIN_INDICADORES"
    )
    assert "[visual_diagnostics]" not in view_model.reason
    assert (
        view_model.reason
        == "No hay suficientes velas visuales para calcular indicadores. "
        "Velas detectadas: 9. Mínimo visible requerido: 14. "
        "Mínimo cerrado requerido: 13."
    )


def test_presenter_extracts_indicator_diagnostics_from_reason() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual: Tendencia: BEARISH | "
        "Velas: 18\n"
        "[indicator_diagnostics] Diagnóstico de indicadores:\n"
        "  EMA: bajista | rápida=10.00 | lenta=12.00 | "
        "separación=3/3 suficiente\n"
        "  RSI: 42.00 | CALL fuera de rango | PUT en rango\n"
        "  Stochastic: cruce bajista | K=76.00 | D=78.00 | "
        "prevK=82.00 | prevD=80.00\n"
        "  Estado: esperando confirmación de estrategia\n"
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: trend is not bullish. "
        "PUT failed: stochastic did not cross down."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.indicator_diagnostics_label
        == "Diagnóstico de indicadores:\n"
        "  EMA: bajista | rápida=10.00 | lenta=12.00 | "
        "separación=3/3 suficiente\n"
        "  RSI: 42.00 | CALL fuera de rango | PUT en rango\n"
        "  Stochastic: cruce bajista | K=76.00 | D=78.00 | "
        "prevK=82.00 | prevD=80.00\n"
        "  Estado: esperando confirmación de estrategia"
    )
    assert "[indicator_diagnostics]" not in view_model.reason
    assert "EMA: bajista" not in view_model.reason


def test_presenter_translates_strategy_failure_reason_to_spanish() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: trend is not bullish, RSI is not in CALL range. "
        "PUT failed: stochastic did not cross down, "
        "recent closed candle is not bearish."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.reason
        == "Las condiciones de OTC Precision 10S no fueron "
        "confirmadas completamente.\n\n"
        "Condiciones CALL no confirmadas:\n"
        "  - La tendencia visual no es alcista.\n"
        "  - El RSI no está en rango CALL.\n\n"
        "Condiciones PUT no confirmadas:\n"
        "  - El Stochastic no confirmó cruce bajista.\n"
        "  - La vela cerrada reciente no es bajista."
    )


def test_presenter_builds_operational_summary_for_watch_call() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual:\n"
        "  Tendencia: BULLISH\n"
        "  Velas detectadas: 20\n"
        "  Últimas: BULLISH, BEARISH, BULLISH\n"
        "  Cerradas: BULLISH, BULLISH, BULLISH\n"
        "  Direccionales: BULLISH, BULLISH, BULLISH\n"
        "  Contexto: BULLISH_CONTINUATION\n"
        "  Vigilancia: VIGILAR_CALL\n"
        "  Estado: ESPERANDO_CONFIRMACION\n"
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: stochastic did not cross up. "
        "PUT failed: trend is not bearish."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.operational_summary_label
        == "Resumen operativo: VIGILAR CALL — falta confirmación "
        "completa de la estrategia."
    )


def test_presenter_builds_operational_summary_for_watch_put() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "[visual_diagnostics] Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 20\n"
        "  Últimas: BEARISH, BULLISH, BEARISH\n"
        "  Cerradas: BEARISH, BEARISH, BEARISH\n"
        "  Direccionales: BEARISH, BEARISH, BEARISH\n"
        "  Contexto: BEARISH_CONTINUATION\n"
        "  Vigilancia: VIGILAR_PUT\n"
        "  Estado: ESPERANDO_CONFIRMACION\n"
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: trend is not bullish. "
        "PUT failed: stochastic did not cross down."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.operational_summary_label
        == "Resumen operativo: VIGILAR PUT — falta confirmación "
        "completa de la estrategia."
    )


def test_presenter_builds_operational_summary_when_candles_are_missing() -> None:

    presenter = SignalRecordPresenter()

    reason = (
        "Not enough visual candles to calculate indicators. "
        "Detected candles: 9. Minimum visible required: 14. "
        "Minimum closed required: 13."
    )

    view_model = presenter.present(
        record=_record(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        ),
    )

    assert (
        view_model.operational_summary_label
        == "Resumen operativo: ESPERAR — faltan velas visibles "
        "para calcular indicadores."
    )