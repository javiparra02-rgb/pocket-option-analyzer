from __future__ import annotations

from collections.abc import Iterable

import pygetwindow as gw

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class WindowEnumerator:
    """
    Enumera las ventanas visibles del sistema.
    """

    def enumerate(self) -> Iterable[WindowInfo]:
        for window in gw.getAllWindows():
            try:
                if not window.title.strip():
                    continue

                if window.width <= 0 or window.height <= 0:
                    continue

                yield WindowInfo(
                    title=window.title,
                    left=window.left,
                    top=window.top,
                    width=window.width,
                    height=window.height,
                )

            except Exception:
                # Algunas ventanas del sistema pueden lanzar excepciones
                # al consultar sus propiedades.
                continue