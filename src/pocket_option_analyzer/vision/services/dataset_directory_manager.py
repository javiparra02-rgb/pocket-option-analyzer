from __future__ import annotations

from pathlib import Path


class DatasetDirectoryManager:
    """
    Gestiona la estructura de directorios utilizada para construir
    el dataset del proyecto.
    """

    def __init__(
        self,
        root: Path,
    ) -> None:
        self._root = root

    @property
    def raw(self) -> Path:
        return self._root / "raw"

    @property
    def processed(self) -> Path:
        return self._root / "processed"

    @property
    def metadata(self) -> Path:
        return self._root / "metadata"

    def create(self) -> None:
        """
        Crea toda la estructura del dataset.
        """

        self.raw.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.processed.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.metadata.mkdir(
            parents=True,
            exist_ok=True,
        )