from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    SessionSignalCounter,
    SignalRecordViewModel,
)


def _view_model(
    direction_label: str,
    is_actionable: bool,
    created_at_label: str = "2026-01-01 10:30:45",
) -> SignalRecordViewModel:
    return SignalRecordViewModel(
        direction_label=direction_label,
        strength_label="ALTA" if is_actionable else "NINGUNA",
        reason="Test signal.",
        source="test_source",
        created_at_label=created_at_label,
        is_actionable=is_actionable,
        css_class="signal-neutral",
        operational_summary_label=(
            f"Resumen operativo: ENTRADA {direction_label} confirmada"
            if is_actionable
            else "Resumen operativo: ESPERAR"
        ),
    )


def test_session_signal_counter_starts_empty() -> None:
    counter = SessionSignalCounter()

    assert counter.call_count == 0
    assert counter.put_count == 0
    assert counter.total_count == 0
    assert counter.text == "Sesión: 0 CALL | 0 PUT | 0 total"


def test_session_signal_counter_counts_call_and_put_signals() -> None:
    counter = SessionSignalCounter()

    counter.update(
        view_model=_view_model(
            direction_label="CALL",
            is_actionable=True,
            created_at_label="2026-01-01 10:30:45",
        ),
    )
    counter.update(
        view_model=_view_model(
            direction_label="PUT",
            is_actionable=True,
            created_at_label="2026-01-01 10:31:45",
        ),
    )

    assert counter.call_count == 1
    assert counter.put_count == 1
    assert counter.total_count == 2
    assert counter.text == "Sesión: 1 CALL | 1 PUT | 2 total"


def test_session_signal_counter_ignores_non_actionable_signals() -> None:
    counter = SessionSignalCounter()

    counter.update(
        view_model=_view_model(
            direction_label="SIN SEÑAL",
            is_actionable=False,
        ),
    )

    assert counter.total_count == 0
    assert counter.text == "Sesión: 0 CALL | 0 PUT | 0 total"


def test_session_signal_counter_ignores_unknown_actionable_direction() -> None:
    counter = SessionSignalCounter()

    counter.update(
        view_model=_view_model(
            direction_label="UNKNOWN",
            is_actionable=True,
        ),
    )

    assert counter.total_count == 0
    assert counter.text == "Sesión: 0 CALL | 0 PUT | 0 total"


def test_session_signal_counter_does_not_count_same_signal_twice() -> None:
    counter = SessionSignalCounter()

    view_model = _view_model(
        direction_label="PUT",
        is_actionable=True,
    )

    counter.update(
        view_model=view_model,
    )
    counter.update(
        view_model=view_model,
    )

    assert counter.call_count == 0
    assert counter.put_count == 1
    assert counter.total_count == 1


def test_session_signal_counter_reset_clears_counts_and_allows_recount() -> None:
    counter = SessionSignalCounter()

    view_model = _view_model(
        direction_label="CALL",
        is_actionable=True,
    )

    counter.update(
        view_model=view_model,
    )

    assert counter.total_count == 1

    counter.reset()

    assert counter.call_count == 0
    assert counter.put_count == 0
    assert counter.total_count == 0

    counter.update(
        view_model=view_model,
    )

    assert counter.call_count == 1
    assert counter.total_count == 1