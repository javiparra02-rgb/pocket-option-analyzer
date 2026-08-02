from pocket_option_analyzer.domain.indicators import StochasticSnapshot


def test_stochastic_snapshot_detects_cross_up() -> None:

    snapshot = StochasticSnapshot(
        k_previous=18.0,
        d_previous=20.0,
        k_value=24.0,
        d_value=21.0,
    )

    assert snapshot.crossed_up is True
    assert snapshot.crossed_down is False


def test_stochastic_snapshot_detects_cross_down() -> None:

    snapshot = StochasticSnapshot(
        k_previous=82.0,
        d_previous=80.0,
        k_value=76.0,
        d_value=78.0,
    )

    assert snapshot.crossed_up is False
    assert snapshot.crossed_down is True
