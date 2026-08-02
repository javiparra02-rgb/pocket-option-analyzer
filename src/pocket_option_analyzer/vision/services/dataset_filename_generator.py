from __future__ import annotations

from datetime import datetime


class DatasetFilenameGenerator:
    """
    Genera nombres únicos para las imágenes del dataset.
    """

    def generate(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f.png")
