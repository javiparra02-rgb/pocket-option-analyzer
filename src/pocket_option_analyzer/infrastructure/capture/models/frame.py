from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion


@dataclass(slots=True, frozen=True)
class Frame:
    """
    Representa un fotograma capturado.
    """

    frame_id: int
    timestamp: datetime
    image: np.ndarray
    price_observation_image: np.ndarray | None = None
    chart_region: ChartRegion | None = None
    price_observation_region: ChartRegion | None = None
    monotonic_timestamp_ns: int | None = None
    source_key: str | None = None

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def channels(self) -> int:
        return int(self.image.shape[2])
