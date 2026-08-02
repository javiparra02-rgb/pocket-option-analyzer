from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    EntryAlertPresenter,
    SignalRecordViewModel,
)


def test_entry_alert_presenter_hides_alert_when_signal_is_not_actionable() -> None:
    presenter = EntryAlertPresenter()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
    )

    alert = presenter.present(
        view_model=view_model,
    )

    assert alert.text == ""
    assert alert.target_direction == "NONE"
    assert alert.is_visible is False


def test_entry_alert_presenter_shows_call_alert_when_signal_is_actionable() -> None:
    presenter = EntryAlertPresenter()

    view_model = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="CALL setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
    )

    alert = presenter.present(
        view_model=view_model,
    )

    assert alert.text == "ENTRADA CALL CONFIRMADA"
    assert alert.target_direction == "CALL"
    assert alert.is_visible is True


def test_entry_alert_presenter_shows_put_alert_when_signal_is_actionable() -> None:
    presenter = EntryAlertPresenter()

    view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-put",
    )

    alert = presenter.present(
        view_model=view_model,
    )

    assert alert.text == "ENTRADA PUT CONFIRMADA"
    assert alert.target_direction == "PUT"
    assert alert.is_visible is True


def test_entry_alert_presenter_hides_alert_for_unknown_actionable_direction() -> None:
    presenter = EntryAlertPresenter()

    view_model = SignalRecordViewModel(
        direction_label="UNKNOWN",
        strength_label="ALTA",
        reason="Unknown signal.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-neutral",
    )

    alert = presenter.present(
        view_model=view_model,
    )

    assert alert.text == ""
    assert alert.target_direction == "NONE"
    assert alert.is_visible is False
