from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from pocket_option_analyzer.infrastructure.capture.models import Frame


class FrameBuffer:
    """
    Almacena los últimos fotogramas capturados.

    El tamaño máximo del búfer se controla mediante `max_size`.
    Cuando el búfer está lleno, el fotograma más antiguo se elimina
    automáticamente.
    """

    def __init__(self, max_size: int = 5) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero")

        self._frames: deque[Frame] = deque(maxlen=max_size)

    def append(self, frame: Frame) -> None:
        """Añade un fotograma al búfer."""
        self._frames.append(frame)

    def latest(self) -> Frame | None:
        """Devuelve el fotograma más reciente."""
        if not self._frames:
            return None
        return self._frames[-1]

    def clear(self) -> None:
        """Vacía el búfer."""
        self._frames.clear()

    def __len__(self) -> int:
        return len(self._frames)

    def __iter__(self) -> Iterator[Frame]:
        return iter(self._frames)
