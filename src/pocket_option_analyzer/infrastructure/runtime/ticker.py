from __future__ import annotations

import time


class Ticker:
    """
    Controla el intervalo de ejecución de un bucle.

    Permite mantener una frecuencia aproximadamente constante
    independientemente del tiempo que tarde el procesamiento.
    """

    def __init__(self, target_fps: int) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be greater than zero.")

        self._target_fps = target_fps
        self._frame_duration = 1.0 / target_fps
        self._last_tick = time.perf_counter()

    @property
    def target_fps(self) -> int:
        return self._target_fps

    @property
    def frame_duration(self) -> float:
        return self._frame_duration

    def wait_next(self) -> float:
        """
        Espera el tiempo necesario para mantener el FPS objetivo.

        Returns
        -------
        float
            Tiempo transcurrido desde el último ciclo.
        """
        now = time.perf_counter()
        elapsed = now - self._last_tick

        remaining = self._frame_duration - elapsed

        if remaining > 0:
            time.sleep(remaining)

        current = time.perf_counter()
        delta = current - self._last_tick
        self._last_tick = current

        return delta

    def reset(self) -> None:
        """
        Reinicia el contador interno.
        """
        self._last_tick = time.perf_counter()
