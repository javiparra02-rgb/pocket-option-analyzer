from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResultRecord,
)


class ManualSignalResultWriter(Protocol):
    """
    Puerto de salida para persistir resultados manuales.

    La capa de aplicación no conoce JSONL ni el sistema de archivos.
    """

    def append(
        self,
        record: ManualSignalResultRecord,
    ) -> None:
        """
        Agrega un resultado al almacenamiento persistente.
        """
