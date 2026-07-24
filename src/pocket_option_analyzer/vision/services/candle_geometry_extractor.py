from __future__ import annotations

from math import ceil

import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleGeometry,
)


class CandleGeometryExtractor:
    """
    Separa el cuerpo y las mechas de una vela dentro de una máscara binaria.

    Principio utilizado:

    - las mechas ocupan normalmente una o pocas columnas;
    - el cuerpo ocupa muchas columnas en la misma fila;
    - las filas con mayor ocupación horizontal pertenecen al cuerpo.

    El extractor trabaja después de detectar y filtrar candidatos.
    """

    def __init__(
        self,
        body_row_fill_ratio: float = 0.65,
        min_body_row_pixels: int = 3,
    ) -> None:
        if not 0 < body_row_fill_ratio <= 1:
            raise ValueError(
                "body_row_fill_ratio debe estar entre 0 y 1."
            )

        if min_body_row_pixels < 1:
            raise ValueError(
                "min_body_row_pixels debe ser mayor o igual a 1."
            )

        self._body_row_fill_ratio = body_row_fill_ratio
        self._min_body_row_pixels = min_body_row_pixels

    def extract(
        self,
        mask: np.ndarray,
        candidate: CandleCandidate,
    ) -> CandleGeometry | None:
        """
        Extrae la geometría vertical de un candidato.

        Devuelve None cuando:
        - el candidato queda fuera de la máscara;
        - no contiene píxeles activos;
        - parece ser solamente una línea vertical sin cuerpo.
        """

        if mask.ndim != 2:
            raise ValueError(
                "La máscara de velas debe tener dos dimensiones."
            )

        image_height, image_width = mask.shape

        left = max(
            0,
            candidate.x,
        )
        top = max(
            0,
            candidate.y,
        )
        right = min(
            image_width,
            candidate.x + candidate.width,
        )
        bottom = min(
            image_height,
            candidate.y + candidate.height,
        )

        if left >= right or top >= bottom:
            return None

        candidate_mask = (
            mask[
                top:bottom,
                left:right,
            ]
            > 0
        )

        row_occupancy = np.count_nonzero(
            candidate_mask,
            axis=1,
        )

        active_rows = np.flatnonzero(
            row_occupancy > 0,
        )

        if active_rows.size == 0:
            return None

        maximum_row_occupancy = int(
            row_occupancy.max()
        )

        # Una línea vertical aislada no constituye un cuerpo de vela.
        if (
            maximum_row_occupancy
            < self._min_body_row_pixels
        ):
            return None

        body_threshold = max(
            self._min_body_row_pixels,
            ceil(
                maximum_row_occupancy
                * self._body_row_fill_ratio
            ),
        )

        body_rows = np.flatnonzero(
            row_occupancy
            >= body_threshold,
        )

        if body_rows.size == 0:
            return None

        high_y = (
            top
            + int(
                active_rows[0]
            )
        )
        low_y = (
            top
            + int(
                active_rows[-1]
            )
        )
        body_top_y = (
            top
            + int(
                body_rows[0]
            )
        )
        body_bottom_y = (
            top
            + int(
                body_rows[-1]
            )
        )

        return CandleGeometry(
            high_y=high_y,
            body_top_y=body_top_y,
            body_bottom_y=body_bottom_y,
            low_y=low_y,
        )