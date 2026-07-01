"""
Jerarquía de excepciones del proyecto.
"""

from __future__ import annotations


class AnalyzerError(Exception):
    """Excepción base del proyecto."""


class ConfigurationError(AnalyzerError):
    """Error de configuración."""


class RuntimeEngineError(AnalyzerError):
    """Error del motor de ejecución."""


class VisionError(AnalyzerError):
    """Error del sistema de visión."""


class CaptureError(AnalyzerError):
    """Error durante la captura de pantalla."""


class StrategyError(AnalyzerError):
    """Error durante la evaluación de la estrategia."""


class IndicatorError(AnalyzerError):
    """Error en el cálculo de indicadores."""