from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


def test_window_info_properties() -> None:
    window = WindowInfo(
        title="Pocket Option",
        left=100,
        top=200,
        width=800,
        height=600,
    )

    assert window.right == 900
    assert window.bottom == 800