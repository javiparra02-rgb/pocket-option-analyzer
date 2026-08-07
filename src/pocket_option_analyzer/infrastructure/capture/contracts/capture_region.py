from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CaptureRegion(Protocol):
    """
    Contrato estructural de una región rectangular capturable.

    La captura de pantalla solo necesita conocer el título descriptivo
    y la geometría absoluta de la región. No depende del modelo nativo
    concreto que proporciona esos datos.
    """

    @property
    def title(
        self,
    ) -> str: ...

    @property
    def left(
        self,
    ) -> int: ...

    @property
    def top(
        self,
    ) -> int: ...

    @property
    def width(
        self,
    ) -> int: ...

    @property
    def height(
        self,
    ) -> int: ...
