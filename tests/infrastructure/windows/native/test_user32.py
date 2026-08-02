from pocket_option_analyzer.infrastructure.windows.native import User32


def test_user32_instantiation():
    assert User32() is not None


def test_window_text_methods_exist():
    api = User32()

    # No depende de HWND real
    assert isinstance(api.get_window_text_length(0), int)
    assert isinstance(api.get_window_text(0), str)


def test_window_rect_methods_exist():
    api = User32()

    rect = api.get_window_rect(0)
    client = api.get_client_rect(0)

    assert hasattr(rect, "left")
    assert hasattr(client, "top")


def test_state_methods_return_bool():
    api = User32()

    assert isinstance(api.is_window_visible(0), bool)
    assert isinstance(api.is_iconic(0), bool)
