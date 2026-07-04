from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.infrastructure.windows.models import Win32WindowInfo


@dataclass(frozen=True, slots=True)
class ChartRegion:
    left: int
    top: int
    width: int
    height: int


class ChartRegionExtractor:
    """
    Calcula el área del gráfico dentro de una ventana.
    """

    def extract(self, window: Win32WindowInfo) -> ChartRegion:
        """
        Heurística inicial (simple pero funcional).
        """

        # margen típico de UI (tabs, toolbar, etc.)
        margin_top = 80
        margin_bottom = 40
        margin_left = 10
        margin_right = 10

        left = window.left + margin_left
        top = window.top + margin_top
        width = window.width - (margin_left + margin_right)
        height = window.height - (margin_top + margin_bottom)

        return ChartRegion(
            left=left,
            top=top,
            width=width,
            height=height,
        )