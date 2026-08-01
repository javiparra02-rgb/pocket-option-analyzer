from __future__ import annotations

from datetime import datetime

from pocket_option_analyzer.application.signals import (
    SignalGateAuditSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecordDisposition,
)
from pocket_option_analyzer.presentation.signals import (
    SignalGateAuditPresenter,
)


def test_presenter_formats_empty_audit() -> None:

    result = SignalGateAuditPresenter().present(
        SignalGateAuditSnapshot(),
    )

    assert result.text == (
        "Gate S30 (ejecución): "
        "0 aceptadas | "
        "0 duplicadas suprimidas | "
        "último: -"
    )
    assert result.css_class == "gate-neutral"


def test_presenter_formats_last_suppressed_signal() -> None:

    result = SignalGateAuditPresenter().present(
        SignalGateAuditSnapshot(
            accepted_count=1,
            duplicate_suppressed_count=2,
            last_disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            last_direction=SignalDirection.PUT,
            last_interval_started_at=datetime(
                2026,
                7,
                31,
                10,
                30,
                0,
            ),
        ),
    )

    assert result.text == (
        "Gate S30 (ejecución): "
        "1 aceptada | "
        "2 duplicadas suprimidas | "
        "último: PUT suprimida | "
        "vela 10:30:00"
    )
    assert result.css_class == "gate-suppressed"