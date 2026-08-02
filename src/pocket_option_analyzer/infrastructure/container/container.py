from __future__ import annotations

from typing import Any


class ServiceContainer:
    """
    Contenedor ligero de dependencias.

    Registra y resuelve servicios compartidos de la aplicación.
    """

    def __init__(self) -> None:
        self._services: dict[type[Any], Any] = {}

    def register(self, service_type: type[Any], instance: Any) -> None:
        """
        Registra una instancia para un tipo.
        """
        if service_type in self._services:
            raise ValueError(
                f"Service '{service_type.__name__}' is already registered."
            )

        self._services[service_type] = instance

    def resolve(self, service_type: type[Any]) -> Any:
        """
        Devuelve la instancia registrada para un tipo.
        """
        try:
            return self._services[service_type]
        except KeyError as exc:
            raise LookupError(
                f"Service '{service_type.__name__}' is not registered."
            ) from exc

    def is_registered(self, service_type: type[Any]) -> bool:
        """
        Indica si un servicio está registrado.
        """
        return service_type in self._services

    def clear(self) -> None:
        """
        Elimina todos los servicios registrados.
        """
        self._services.clear()
