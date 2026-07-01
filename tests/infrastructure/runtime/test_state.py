from pocket_option_analyzer.infrastructure.runtime import (
    RuntimeState,
    RuntimeStatus,
)


def test_default_state() -> None:
    state = RuntimeState()

    assert state.status is RuntimeStatus.CREATED
    assert state.frame_count == 0
    assert state.running is False
    assert state.last_error is None


def test_reset() -> None:
    state = RuntimeState()

    state.status = RuntimeStatus.RUNNING
    state.frame_count = 50
    state.running = True
    state.last_error = "error"

    state.reset()

    assert state.status is RuntimeStatus.CREATED
    assert state.frame_count == 0
    assert state.running is False
    assert state.last_error is None