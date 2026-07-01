from pocket_option_analyzer.infrastructure.config import get_settings
from pocket_option_analyzer.infrastructure.logging import LoggingManager


def test_logger_creation() -> None:
    settings = get_settings()

    manager = LoggingManager(settings)

    manager.configure()

    assert manager.logger is not None