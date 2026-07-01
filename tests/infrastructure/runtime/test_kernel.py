from pocket_option_analyzer.infrastructure.config import get_settings
from pocket_option_analyzer.infrastructure.container import ServiceContainer
from pocket_option_analyzer.infrastructure.logging import LoggingManager
from pocket_option_analyzer.infrastructure.runtime import (
    ApplicationContext,
    ApplicationKernel,
    RuntimeState,
    RuntimeStatus,
)


def test_kernel_initialize() -> None:
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

    kernel = ApplicationKernel(context)

    kernel.initialize()

    assert state.status is RuntimeStatus.INITIALIZED