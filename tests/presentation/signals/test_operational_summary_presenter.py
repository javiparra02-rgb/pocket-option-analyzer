from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    OperationalSummaryPresenter,
    SignalRecordViewModel,
)


def test_operational_summary_presenter_handles_waiting_state() -> None:
    presenter = OperationalSummaryPresenter()

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

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.text == "Resumen operativo: ESPERAR"
    assert summary.target_direction == "NONE"
    assert summary.state == "WAITING"


def test_operational_summary_presenter_handles_call_watch_state() -> None:
    presenter = OperationalSummaryPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for CALL confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label=(
            "Resumen operativo: VIGILAR CALL — falta confirmación "
            "completa de la estrategia."
        ),
    )

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.target_direction == "CALL"
    assert summary.state == "WATCH"


def test_operational_summary_presenter_handles_put_watch_state() -> None:
    presenter = OperationalSummaryPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.target_direction == "PUT"
    assert summary.state == "WATCH"


def test_operational_summary_presenter_handles_confirmed_call_state() -> None:
    presenter = OperationalSummaryPresenter()

    view_model = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="CALL setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.target_direction == "CALL"
    assert summary.state == "CONFIRMED"


def test_operational_summary_presenter_handles_confirmed_put_state() -> None:
    presenter = OperationalSummaryPresenter()

    view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-put",
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.target_direction == "PUT"
    assert summary.state == "CONFIRMED"


def test_operational_summary_presenter_uses_summary_text_when_not_actionable() -> None:
    presenter = OperationalSummaryPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    summary = presenter.present(
        view_model=view_model,
    )

    assert summary.target_direction == "PUT"
    assert summary.state == "CONFIRMED"