from pocket_option_analyzer.infrastructure.config import get_settings
from pocket_option_analyzer.infrastructure.container import ServiceContainer
from pocket_option_analyzer.infrastructure.logging import LoggingManager
from pocket_option_analyzer.infrastructure.runtime import (
    ApplicationContext,
    RuntimeState,
)


def test_application_context_creation() -> None:
    settings = get_settings()

    logger = LoggingManager(settings)

    container = ServiceContainer()

    state = RuntimeState()

    context = ApplicationContext(
        settings=settings,
        logger=logger,
        runtime_state=state,
        services=container,
    )

    assert context.settings is settings
    assert context.logger is logger
    assert context.runtime_state is state
    assert context.services is container
