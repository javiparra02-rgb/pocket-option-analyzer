from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class Frame:
    """
    Frame capturado desde pantalla.
    """

    image: NDArray[np.uint8]

    timestamp: float
