from __future__ import annotations

from pocket_option_analyzer.presentation.signals import (
    SignalRecordViewModel,
    VoiceSignalNotifier,
)


class FakeSpeechEngine:

    def __init__(self) -> None:
        self.spoken_messages: list[str] = []

    def speak(
        self,
        text: str,
    ) -> None:
        self.spoken_messages.append(
            text,
        )


def _view_model(
    direction: str,
    actionable: bool,
) -> SignalRecordViewModel:
    return SignalRecordViewModel(
        direction_label=direction,
        strength_label="ALTA" if actionable else "NINGUNA",
        reason="Test voice signal.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=actionable,
        css_class="signal-neutral",
    )


def test_voice_signal_notifier_starts_enabled() -> None:
    notifier = VoiceSignalNotifier(
        speech_engine=FakeSpeechEngine(),
    )

    assert notifier.is_enabled is True
    assert notifier.active_direction is None


def test_voice_signal_notifier_ignores_non_actionable_signal() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    notifier.notify(
        view_model=_view_model(
            direction="SIN SEÑAL",
            actionable=False,
        ),
    )

    assert engine.spoken_messages == []
    assert notifier.active_direction is None


def test_voice_signal_notifier_announces_confirmed_call() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == [
        "Compra",
    ]
    assert notifier.active_direction == "CALL"


def test_voice_signal_notifier_announces_confirmed_put() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    notifier.notify(
        view_model=_view_model(
            direction="PUT",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == [
        "Vende",
    ]
    assert notifier.active_direction == "PUT"


def test_voice_signal_notifier_does_not_repeat_same_active_signal() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    view_model = _view_model(
        direction="PUT",
        actionable=True,
    )

    notifier.notify(
        view_model=view_model,
    )
    notifier.notify(
        view_model=view_model,
    )
    notifier.notify(
        view_model=view_model,
    )

    assert engine.spoken_messages == [
        "Vende",
    ]


def test_voice_signal_notifier_allows_same_direction_after_neutral_state() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )
    notifier.notify(
        view_model=_view_model(
            direction="SIN SEÑAL",
            actionable=False,
        ),
    )
    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == [
        "Compra",
        "Compra",
    ]


def test_voice_signal_notifier_announces_direction_change() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
    )

    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )
    notifier.notify(
        view_model=_view_model(
            direction="PUT",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == [
        "Compra",
        "Vende",
    ]


def test_voice_signal_notifier_can_be_disabled_and_enabled() -> None:
    engine = FakeSpeechEngine()
    notifier = VoiceSignalNotifier(
        speech_engine=engine,
        enabled=False,
    )

    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == []

    notifier.set_enabled(
        True,
    )
    notifier.notify(
        view_model=_view_model(
            direction="CALL",
            actionable=True,
        ),
    )

    assert engine.spoken_messages == [
        "Compra",
    ]