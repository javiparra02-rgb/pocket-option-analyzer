from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass(slots=True, frozen=True)
class Frame:
    """
    Representa un fotograma capturado.
    """

    frame_id: int
    timestamp: datetime
    image: np.ndarray

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def channels(self) -> int:
        return int(self.image.shape[2])
