from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class VisualIndicatorSnapshotContext:
    """
    Describe las velas visuales utilizadas para crear un snapshot.

    Los valores permanecen asociados al IndicatorSnapshot almacenado
    en caché y no cambian con las capturas posteriores del mismo
    intervalo temporal.
    """

    visible_candle_count: int
    ohlc_candle_count: int
    geometry_valid_count: int
    geometry_total_count: int

    def __post_init__(
        self,
    ) -> None:
        counts = {
            "visible_candle_count": self.visible_candle_count,
            "ohlc_candle_count": self.ohlc_candle_count,
            "geometry_valid_count": self.geometry_valid_count,
            "geometry_total_count": self.geometry_total_count,
        }

        for field_name, value in counts.items():
            if value < 0:
                raise ValueError(f"{field_name} no puede ser negativo.")

        if self.geometry_valid_count > self.geometry_total_count:
            raise ValueError(
                "geometry_valid_count no puede superar geometry_total_count."
            )

        if self.ohlc_candle_count != self.geometry_total_count:
            raise ValueError(
                "ohlc_candle_count debe coincidir con geometry_total_count."
            )

        if self.ohlc_candle_count > self.visible_candle_count:
            raise ValueError("ohlc_candle_count no puede superar visible_candle_count.")

    @property
    def has_complete_geometry(
        self,
    ) -> bool:
        return self.geometry_valid_count == self.geometry_total_count
