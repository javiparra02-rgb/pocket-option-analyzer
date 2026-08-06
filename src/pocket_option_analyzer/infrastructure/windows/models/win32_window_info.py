from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Win32WindowInfo:
    """
    Representa una ventana nativa de Windows.

    Contiene la geometría de la ventana, la geometría de su área cliente
    y el estado necesario para determinar si puede utilizarse como origen
    de una captura de pantalla.
    """

    hwnd: int

    title: str

    left: int
    top: int

    width: int
    height: int

    client_left: int
    client_top: int

    client_width: int
    client_height: int

    visible: bool

    minimized: bool

    @property
    def right(
        self,
    ) -> int:
        """
        Devuelve el límite horizontal derecho de la ventana.
        """

        return self.left + self.width

    @property
    def bottom(
        self,
    ) -> int:
        """
        Devuelve el límite vertical inferior de la ventana.
        """

        return self.top + self.height

    @property
    def area(
        self,
    ) -> int:
        """
        Devuelve el área total de la ventana.
        """

        return self.width * self.height

    @property
    def is_capture_candidate(
        self,
    ) -> bool:
        """
        Indica si la ventana posee las condiciones mínimas para captura.

        Las coordenadas left y top pueden ser negativas cuando la ventana
        se encuentra en un monitor secundario.
        """

        return (
            self.hwnd > 0
            and bool(
                self.title.strip(),
            )
            and self.visible
            and not self.minimized
            and self.width > 0
            and self.height > 0
        )
