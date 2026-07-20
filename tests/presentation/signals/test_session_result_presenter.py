from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    SessionResultPresenter,
    SessionResultTracker,
)


def test_session_result_presenter_shows_empty_session() -> None:
    tracker = SessionResultTracker()
    presenter = SessionResultPresenter()

    view_model = presenter.present(
        snapshot=tracker.snapshot(),
    )

    assert view_model.text == (
        "Resultados: 0 ganadas | 0 perdidas | "
        "Tasa observada: - | Racha de pérdidas: 0/3"
    )
    assert view_model.compact_text == (
        "Resultados: 0G | 0P | - | Racha: 0/3"
    )
    assert view_model.pause_recommended is False
    assert view_model.pause_alert_text == ""


def test_session_result_presenter_calculates_observed_rate() -> None:
    tracker = SessionResultTracker()
    presenter = SessionResultPresenter()

    tracker.register_win()
    tracker.register_win()
    tracker.register_win()
    tracker.register_loss()
    tracker.register_loss()

    view_model = presenter.present(
        snapshot=tracker.snapshot(),
    )

    assert view_model.text == (
        "Resultados: 3 ganadas | 2 perdidas | "
        "Tasa observada: 60,0 % | Racha de pérdidas: 2/3"
    )


def test_session_result_presenter_builds_compact_text() -> None:
    tracker = SessionResultTracker()
    presenter = SessionResultPresenter()

    tracker.register_win()
    tracker.register_loss()

    view_model = presenter.present(
        snapshot=tracker.snapshot(),
    )

    assert view_model.compact_text == (
        "Resultados: 1G | 1P | 50,0 % | Racha: 1/3"
    )


def test_session_result_presenter_recommends_pause_after_loss_limit() -> None:
    tracker = SessionResultTracker()
    presenter = SessionResultPresenter()

    tracker.register_loss()
    tracker.register_loss()
    tracker.register_loss()

    view_model = presenter.present(
        snapshot=tracker.snapshot(),
    )

    assert view_model.pause_recommended is True
    assert view_model.pause_alert_text == (
        "PAUSA RECOMENDADA\n"
        "Se alcanzaron 3 pérdidas consecutivas\n"
        "Detén la sesión y revisa las operaciones"
    )


def test_session_result_presenter_respects_custom_loss_limit() -> None:
    tracker = SessionResultTracker(
        max_consecutive_losses=2,
    )
    presenter = SessionResultPresenter()

    tracker.register_loss()
    tracker.register_loss()

    view_model = presenter.present(
        snapshot=tracker.snapshot(),
    )

    assert view_model.pause_recommended is True
    assert view_model.pause_alert_text == (
        "PAUSA RECOMENDADA\n"
        "Se alcanzaron 2 pérdidas consecutivas\n"
        "Detén la sesión y revisa las operaciones"
    )
    assert view_model.text.endswith(
        "Racha de pérdidas: 2/2"
    )