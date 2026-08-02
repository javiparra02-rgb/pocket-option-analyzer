from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    SessionResult,
    SessionResultTracker,
)


def test_session_result_tracker_starts_empty() -> None:
    tracker = SessionResultTracker()

    assert tracker.wins == 0
    assert tracker.losses == 0
    assert tracker.total == 0
    assert tracker.consecutive_losses == 0
    assert tracker.max_consecutive_losses == 3
    assert tracker.win_rate_percentage is None
    assert tracker.pause_recommended is False
    assert tracker.history == ()


def test_session_result_tracker_registers_win() -> None:
    tracker = SessionResultTracker()

    snapshot = tracker.register_win()

    assert snapshot.wins == 1
    assert snapshot.losses == 0
    assert snapshot.total == 1
    assert snapshot.consecutive_losses == 0
    assert snapshot.win_rate_percentage == 100.0
    assert tracker.history == (SessionResult.WIN,)


def test_session_result_tracker_registers_loss() -> None:
    tracker = SessionResultTracker()

    snapshot = tracker.register_loss()

    assert snapshot.wins == 0
    assert snapshot.losses == 1
    assert snapshot.total == 1
    assert snapshot.consecutive_losses == 1
    assert snapshot.win_rate_percentage == 0.0
    assert tracker.history == (SessionResult.LOSS,)


def test_session_result_tracker_win_resets_loss_streak() -> None:
    tracker = SessionResultTracker()

    tracker.register_loss()
    tracker.register_loss()

    assert tracker.consecutive_losses == 2

    tracker.register_win()

    assert tracker.consecutive_losses == 0
    assert tracker.pause_recommended is False


def test_session_result_tracker_recommends_pause_after_three_losses() -> None:
    tracker = SessionResultTracker()

    tracker.register_loss()
    tracker.register_loss()
    snapshot = tracker.register_loss()

    assert snapshot.losses == 3
    assert snapshot.consecutive_losses == 3
    assert snapshot.pause_recommended is True
    assert tracker.pause_recommended is True


def test_session_result_tracker_does_not_pause_for_non_consecutive_losses() -> None:
    tracker = SessionResultTracker()

    tracker.register_loss()
    tracker.register_loss()
    tracker.register_win()
    tracker.register_loss()

    assert tracker.losses == 3
    assert tracker.consecutive_losses == 1
    assert tracker.pause_recommended is False


def test_session_result_tracker_undoes_last_result() -> None:
    tracker = SessionResultTracker()

    tracker.register_win()
    tracker.register_loss()
    tracker.register_loss()

    removed_result = tracker.undo_last_result()

    assert removed_result == SessionResult.LOSS
    assert tracker.wins == 1
    assert tracker.losses == 1
    assert tracker.total == 2
    assert tracker.consecutive_losses == 1


def test_session_result_tracker_undo_on_empty_history_returns_none() -> None:
    tracker = SessionResultTracker()

    removed_result = tracker.undo_last_result()

    assert removed_result is None
    assert tracker.total == 0


def test_session_result_tracker_resets_session_results() -> None:
    tracker = SessionResultTracker()

    tracker.register_win()
    tracker.register_loss()
    tracker.register_loss()

    tracker.reset()

    assert tracker.wins == 0
    assert tracker.losses == 0
    assert tracker.total == 0
    assert tracker.consecutive_losses == 0
    assert tracker.pause_recommended is False
    assert tracker.history == ()


def test_session_result_tracker_supports_custom_loss_limit() -> None:
    tracker = SessionResultTracker(
        max_consecutive_losses=2,
    )

    tracker.register_loss()

    assert tracker.pause_recommended is False

    tracker.register_loss()

    assert tracker.max_consecutive_losses == 2
    assert tracker.consecutive_losses == 2
    assert tracker.pause_recommended is True
