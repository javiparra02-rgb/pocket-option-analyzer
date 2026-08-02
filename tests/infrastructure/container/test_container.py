from pocket_option_analyzer.infrastructure.container import ServiceContainer


class DummyService:
    pass


def test_register_and_resolve() -> None:
    container = ServiceContainer()

    service = DummyService()

    container.register(DummyService, service)

    assert container.resolve(DummyService) is service


def test_is_registered() -> None:
    container = ServiceContainer()

    assert not container.is_registered(DummyService)

    container.register(DummyService, DummyService())

    assert container.is_registered(DummyService)


def test_clear() -> None:
    container = ServiceContainer()

    container.register(DummyService, DummyService())

    container.clear()

    assert not container.is_registered(DummyService)
