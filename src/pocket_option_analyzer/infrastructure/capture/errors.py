from __future__ import annotations


class CaptureUnavailableError(RuntimeError):
    """
    Indica que una captura no puede realizarse por un estado externo
    temporalmente no disponible.

    Ejemplos:
    - la ventana desapareció entre localización y lectura;
    - la ventana fue minimizada;
    - la ventana dejó de ser visible;
    - su geometría dejó de ser capturable.

    No representa un error interno de programación.
    """
