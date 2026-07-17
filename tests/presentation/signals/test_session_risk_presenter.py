from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    SessionRiskPresenter,
)


def test_session_risk_presenter_starts_with_ok_state() -> None:
    presenter = SessionRiskPresenter()

    risk = presenter.present(
        total_confirmed_signals=0,
    )

    assert risk.compact_text == "Riesgo: OK 0/12"
    assert risk.state == "OK"
    assert risk.text == (
        "Riesgo sesión: OK | Señales confirmadas: 0/12 | "
        "Recordatorio: detener si acumulas 3 pérdidas manuales"
    )


def test_session_risk_presenter_uses_warning_state_near_limit() -> None:
    presenter = SessionRiskPresenter()

    risk = presenter.present(
        total_confirmed_signals=10,
    )

    assert risk.compact_text == "Riesgo: ATENCIÓN 10/12"
    assert risk.state == "WARNING"
    assert risk.text == (
        "Riesgo sesión: ATENCIÓN | Señales confirmadas: 10/12 | "
        "Considera reducir operaciones"
    )


def test_session_risk_presenter_uses_limit_state_at_limit() -> None:
    presenter = SessionRiskPresenter()

    risk = presenter.present(
        total_confirmed_signals=12,
    )

    assert risk.compact_text == "Riesgo: LÍMITE 12/12"
    assert risk.state == "LIMIT_REACHED"
    assert risk.text == (
        "Riesgo sesión: LÍMITE ALCANZADO | "
        "Señales confirmadas: 12/12 | "
        "No buscar más entradas en esta sesión"
    )


def test_session_risk_presenter_uses_limit_state_above_limit() -> None:
    presenter = SessionRiskPresenter()

    risk = presenter.present(
        total_confirmed_signals=15,
    )

    assert risk.state == "LIMIT_REACHED"
    assert "15/12" in risk.text


def test_session_risk_presenter_allows_custom_limits() -> None:
    presenter = SessionRiskPresenter(
        max_session_signals=5,
        warning_signal_count=4,
    )

    warning = presenter.present(
        total_confirmed_signals=4,
    )
    limit = presenter.present(
        total_confirmed_signals=5,
    )

    assert warning.compact_text == "Riesgo: ATENCIÓN 4/5"
    assert limit.compact_text == "Riesgo: LÍMITE 5/5"
    assert warning.state == "WARNING"
    assert "4/5" in warning.text
    assert limit.state == "LIMIT_REACHED"
    assert "5/5" in limit.text