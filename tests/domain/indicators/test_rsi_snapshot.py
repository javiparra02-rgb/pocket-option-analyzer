from pocket_option_analyzer.domain.indicators import RsiSnapshot


def test_rsi_snapshot_threshold_helpers() -> None:

    snapshot = RsiSnapshot(
        value=57.0,
    )

    assert snapshot.is_above(50.0) is True
    assert snapshot.is_below(50.0) is False
    assert snapshot.is_between(52.0, 65.0) is True