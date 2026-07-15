from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    ConfirmationChecklistPresenter,
    SignalRecordViewModel,
)


def test_confirmation_checklist_presenter_returns_empty_waiting_state() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label="Resumen operativo: ESPERAR",
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ❌ | EMA: ❌ | RSI: ❌ | Stoch: ❌ | Entrada: ESPERAR"
    )
    assert checklist.target_direction == "NONE"
    assert checklist.is_actionable is False


def test_confirmation_checklist_presenter_handles_put_watch() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=108.14 | lenta=183.32 | "
            "separación=9/3 suficiente\n"
            "  RSI: 39.62 | CALL fuera de rango | PUT en rango\n"
            "  Stochastic: sin cruce | K=12.60 | D=15.25\n"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ❌ | EMA: ✅ | RSI: ✅ | Stoch: ❌ | Entrada: ESPERAR"
    )
    assert checklist.target_direction == "PUT"
    assert checklist.is_actionable is False


def test_confirmation_checklist_presenter_handles_confirmed_put_entry() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-put",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: SEÑAL_CONFIRMADA"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=89.09 | lenta=161.44 | "
            "separación=8/3 suficiente\n"
            "  RSI: 36.64 | CALL fuera de rango | PUT en rango\n"
            "  Stochastic: cruce bajista | K=70.00 | D=80.00\n"
        ),
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ✅ | EMA: ✅ | RSI: ✅ | Stoch: ✅ | Entrada: PUT"
    )
    assert checklist.target_direction == "PUT"
    assert checklist.is_actionable is True


def test_confirmation_checklist_presenter_handles_call_watch() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for CALL confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BULLISH\n"
            "  Contexto: BULLISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_CALL\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: alcista | rápida=551.54 | lenta=420.72 | "
            "separación=10/3 suficiente\n"
            "  RSI: 78.29 | CALL fuera de rango | PUT fuera de rango\n"
            "  Stochastic: sin cruce | K=89.73 | D=93.15\n"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR CALL — falta confirmación "
            "completa de la estrategia."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ❌ | EMA: ✅ | RSI: ❌ | Stoch: ❌ | Entrada: ESPERAR"
    )
    assert checklist.target_direction == "CALL"


def test_confirmation_checklist_presenter_handles_confirmed_call_entry() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="CALL setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BULLISH\n"
            "  Contexto: BULLISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_CALL\n"
            "  Estado: SEÑAL_CONFIRMADA"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: alcista | rápida=551.54 | lenta=420.72 | "
            "separación=10/3 suficiente\n"
            "  RSI: 58.00 | CALL en rango | PUT fuera de rango\n"
            "  Stochastic: cruce alcista | K=40.00 | D=35.00\n"
        ),
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ✅ | EMA: ✅ | RSI: ✅ | Stoch: ✅ | Entrada: CALL"
    )
    assert checklist.target_direction == "CALL"
    assert checklist.is_actionable is True


def test_confirmation_checklist_presenter_rejects_insufficient_call_ema() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for CALL confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Vigilancia: VIGILAR_CALL\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: alcista | rápida=318.00 | lenta=227.10 | "
            "separación=1/3 insuficiente\n"
            "  RSI: 57.00 | CALL en rango | PUT fuera de rango\n"
            "  Stochastic: cruce alcista | K=70.00 | D=60.00\n"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR CALL — falta confirmación "
            "completa de la estrategia."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ❌ | EMA: ❌ | RSI: ✅ | Stoch: ✅ | Entrada: ESPERAR"
    )


def test_confirmation_checklist_presenter_rejects_insufficient_put_ema() -> None:
    presenter = ConfirmationChecklistPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=309.10 | lenta=365.78 | "
            "separación=2/3 insuficiente\n"
            "  RSI: 69.11 | CALL fuera de rango | PUT fuera de rango\n"
            "  Stochastic: cruce bajista | K=33.33 | D=14.75\n"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    checklist = presenter.present(
        view_model=view_model,
    )

    assert checklist.text == (
        "Visual: ❌ | EMA: ❌ | RSI: ❌ | Stoch: ✅ | Entrada: ESPERAR"
    )