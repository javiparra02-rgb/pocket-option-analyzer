from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandleFilterDiagnostics:
    """
    Diagnóstico de una ejecución de CandleFilter.

    Permite identificar en qué etapa se redujo la cantidad de
    candidatos sin modificar el comportamiento del filtro.
    """

    input_count: int

    dimension_valid_count: int

    width_valid_count: int

    merged_count: int

    returned_count: int

    dominant_width: float | None

    @property
    def rejected_by_dimensions(
        self,
    ) -> int:
        """
        Cantidad descartada por área o dimensiones absolutas.
        """

        return self.input_count - self.dimension_valid_count

    @property
    def rejected_by_width(
        self,
    ) -> int:
        """
        Cantidad descartada por incompatibilidad con el ancho dominante.
        """

        return self.dimension_valid_count - self.width_valid_count

    @property
    def merged_fragments(
        self,
    ) -> int:
        """
        Reducción producida al fusionar fragmentos de una misma vela.
        """

        return self.width_valid_count - self.merged_count

    @property
    def truncated_count(
        self,
    ) -> int:
        """
        Cantidad descartada exclusivamente por max_candidates.
        """

        return self.merged_count - self.returned_count
