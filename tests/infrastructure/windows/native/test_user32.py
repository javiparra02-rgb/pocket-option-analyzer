from pocket_option_analyzer.infrastructure.windows.native import User32


def test_can_create_user32() -> None:
    api = User32()

    assert api is not None