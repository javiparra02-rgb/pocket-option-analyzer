from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class RuntimeStatus(Enum):
    """
    Estados posibles del Runtime.
    """

    CREATED = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


@dataclass(slots=True)
class RuntimeState:
    """
    Estado mutable del Runtime.

    Este objeto es propiedad del RuntimeEngine y representa
    el estado actual del ciclo de vida de la aplicación.
    """

    status: RuntimeStatus = RuntimeStatus.CREATED

    frame_count: int = 0

    fps: float = 0.0

    running: bool = False

    last_error: str | None = None

    def reset(self) -> None:
        """
        Restablece el estado del Runtime.
        """

        self.status = RuntimeStatus.CREATED
        self.frame_count = 0
        self.fps = 0.0
        self.running = False
        self.last_error = None