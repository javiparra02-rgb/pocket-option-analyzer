from __future__ import annotations

from .hsv_range import HSVRange


class HSVConfig:
    """
    Configuración centralizada de colores HSV.
    """

    GREEN_CANDLE = HSVRange(
        lower=(35, 80, 80),
        upper=(90, 255, 255),
    )

    RED_CANDLE = HSVRange(
        lower=(0, 80, 80),
        upper=(15, 255, 255),
    )