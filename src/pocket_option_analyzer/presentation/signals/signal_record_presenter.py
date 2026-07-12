from __future__ import annotations

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.presentation.signals.signal_record_view_model import (
    SignalRecordViewModel,
)


class SignalRecordPresenter:
    """
    Convierte SignalRecord en un ViewModel listo para la GUI.

    Soporta diagnósticos de una línea y diagnósticos multilínea.
    """

    VISUAL_DIAGNOSTICS_PREFIX = "[visual_diagnostics]"
    INDICATOR_DIAGNOSTICS_PREFIX = "[indicator_diagnostics]"

    def present(
        self,
        record: SignalRecord,
    ) -> SignalRecordViewModel:

        clean_reason = self._remove_diagnostics(
            reason=record.signal.reason,
        )

        return SignalRecordViewModel(
            direction_label=self._direction_label(
                direction=record.signal.direction,
            ),
            strength_label=self._strength_label(
                strength=record.signal.strength,
            ),
            reason=self._format_reason(
                reason=clean_reason,
            ),
            source=record.source,
            created_at_label=record.created_at.strftime(
                "%Y-%m-%d %H:%M:%S",
            ),
            is_actionable=record.is_actionable,
            css_class=self._css_class(
                direction=record.signal.direction,
            ),
            visual_diagnostics_label=self._diagnostics_label(
                reason=record.signal.reason,
                prefix=self.VISUAL_DIAGNOSTICS_PREFIX,
                default="Diagnóstico visual: -",
            ),
            indicator_diagnostics_label=self._diagnostics_label(
                reason=record.signal.reason,
                prefix=self.INDICATOR_DIAGNOSTICS_PREFIX,
                default="Diagnóstico de indicadores: -",
            ),
            operational_summary_label=self._operational_summary_label(
                record=record,
            ),
        )

    def _direction_label(
        self,
        direction: SignalDirection,
    ) -> str:

        if direction is SignalDirection.CALL:
            return "CALL"

        if direction is SignalDirection.PUT:
            return "PUT"

        return "SIN SEÑAL"

    def _strength_label(
        self,
        strength: SignalStrength,
    ) -> str:

        if strength is SignalStrength.HIGH:
            return "ALTA"

        if strength is SignalStrength.MEDIUM:
            return "MEDIA"

        if strength is SignalStrength.LOW:
            return "BAJA"

        return "NINGUNA"

    def _css_class(
        self,
        direction: SignalDirection,
    ) -> str:

        if direction is SignalDirection.CALL:
            return "signal-call"

        if direction is SignalDirection.PUT:
            return "signal-put"

        return "signal-neutral"

    def _diagnostics_label(
        self,
        reason: str,
        prefix: str,
        default: str,
    ) -> str:

        lines = reason.splitlines()

        for index, line in enumerate(
            lines,
        ):
            if line.startswith(
                prefix,
            ):
                return self._collect_diagnostic_block(
                    lines=lines,
                    start_index=index,
                    prefix=prefix,
                )

        return default

    def _collect_diagnostic_block(
        self,
        lines: list[str],
        start_index: int,
        prefix: str,
    ) -> str:

        first_line = lines[start_index].replace(
            prefix,
            "",
            1,
        ).strip()

        collected_lines = [
            first_line,
        ]

        for line in lines[start_index + 1 :]:
            if line.startswith(
                self._diagnostic_prefixes(),
            ):
                break

            if not line.startswith(
                "  ",
            ):
                break

            collected_lines.append(
                line.rstrip(),
            )

        return "\n".join(
            line
            for line in collected_lines
            if line
        ).strip()

    def _remove_diagnostics(
        self,
        reason: str,
    ) -> str:

        lines = reason.splitlines()

        cleaned_lines: list[str] = []
        skipping_diagnostic_block = False

        for line in lines:
            if line.startswith(
                self._diagnostic_prefixes(),
            ):
                skipping_diagnostic_block = True
                continue

            if skipping_diagnostic_block:
                if line.startswith(
                    "  ",
                ):
                    continue

                skipping_diagnostic_block = False

            cleaned_lines.append(
                line,
            )

        return "\n".join(
            cleaned_lines,
        ).strip()

    def _diagnostic_prefixes(
        self,
    ) -> tuple[str, str]:

        return (
            self.VISUAL_DIAGNOSTICS_PREFIX,
            self.INDICATOR_DIAGNOSTICS_PREFIX,
        )

    def _format_reason(
        self,
        reason: str,
    ) -> str:
        """
        Formatea el motivo técnico de estrategia para la GUI.
        """

        if (
            "CALL failed:" not in reason
            or "PUT failed:" not in reason
        ):
            return self._translate_reason(
                reason=reason,
            )

        prefix, call_and_put_text = reason.split(
            "CALL failed:",
            1,
        )

        call_text, put_text = call_and_put_text.split(
            "PUT failed:",
            1,
        )

        return (
            f"{self._translate_reason(prefix.strip())}\n\n"
            "Condiciones CALL no confirmadas:\n"
            f"{self._format_failure_items(call_text)}\n\n"
            "Condiciones PUT no confirmadas:\n"
            f"{self._format_failure_items(put_text)}"
        ).strip()

    def _format_failure_items(
        self,
        text: str,
    ) -> str:

        cleaned_text = text.strip().strip(".")

        if cleaned_text == "none":
            return "  - Ninguna."

        failures = [
            failure.strip()
            for failure in cleaned_text.split(",")
            if failure.strip()
        ]

        return "\n".join(
            f"  - {self._translate_failure(failure)}"
            for failure in failures
        )
    
    def _translate_reason(
        self,
        reason: str,
    ) -> str:

        translations = {
            "OTC Precision 10S conditions were not fully confirmed.": (
                "Las condiciones de OTC Precision 10S no fueron "
                "confirmadas completamente."
            ),
            "Not enough visual candles to calculate indicators.": (
                "No hay suficientes velas visuales para calcular "
                "indicadores."
            ),
            "Detected candles:": (
                "Velas detectadas:"
            ),
            "Minimum visible required:": (
                "Mínimo visible requerido:"
            ),
            "Minimum closed required:": (
                "Mínimo cerrado requerido:"
            ),
        }

        translated_reason = reason

        for english_text, spanish_text in translations.items():
            translated_reason = translated_reason.replace(
                english_text,
                spanish_text,
            )

        return translated_reason

    def _translate_failure(
        self,
        failure: str,
    ) -> str:

        translations = {
            "trend is not bullish": (
                "La tendencia visual no es alcista."
            ),
            "trend is not bearish": (
                "La tendencia visual no es bajista."
            ),
            "EMA alignment is not bullish": (
                "La alineación EMA no es alcista."
            ),
            "EMA alignment is not bearish": (
                "La alineación EMA no es bajista."
            ),
            "EMA separation is insufficient": (
                "La separación EMA es insuficiente."
            ),
            "RSI is not in CALL range": (
                "El RSI no está en rango CALL."
            ),
            "RSI is not in PUT range": (
                "El RSI no está en rango PUT."
            ),
            "stochastic did not cross up": (
                "El Stochastic no confirmó cruce alcista."
            ),
            "stochastic did not cross down": (
                "El Stochastic no confirmó cruce bajista."
            ),
            "stochastic previous K is above CALL trigger zone": (
                "El K previo del Stochastic está sobre la zona de activación CALL."
            ),
            "stochastic previous K is below PUT trigger zone": (
                "El K previo del Stochastic está bajo la zona de activación PUT."
            ),
            "latest candle is not bullish": (
                "La última vela no es alcista."
            ),
            "latest candle is not bearish": (
                "La última vela no es bajista."
            ),
            "recent closed candle is not bullish": (
                "La vela cerrada reciente no es alcista."
            ),
            "recent closed candle is not bearish": (
                "La vela cerrada reciente no es bajista."
            ),
        }

        return translations.get(
            failure,
            f"{failure}.",
        )
    
    def _operational_summary_label(
        self,
        record: SignalRecord,
    ) -> str:

        if record.signal.direction is SignalDirection.CALL:
            return (
                "Resumen operativo: ENTRADA CALL confirmada — "
                "revisar gestión de riesgo antes de operar manualmente."
            )

        if record.signal.direction is SignalDirection.PUT:
            return (
                "Resumen operativo: ENTRADA PUT confirmada — "
                "revisar gestión de riesgo antes de operar manualmente."
            )

        reason = record.signal.reason

        if "Not enough visual candles" in reason:
            return (
                "Resumen operativo: ESPERAR — faltan velas visibles "
                "para calcular indicadores."
            )

        visual_diagnostics = self._diagnostics_label(
            reason=reason,
            prefix=self.VISUAL_DIAGNOSTICS_PREFIX,
            default="",
        )

        vigilance = self._extract_diagnostic_value(
            diagnostics=visual_diagnostics,
            key="Vigilancia:",
        )

        if vigilance == "VIGILAR_CALL":
            return (
                "Resumen operativo: VIGILAR CALL — falta confirmación "
                "completa de la estrategia."
            )

        if vigilance == "VIGILAR_PUT":
            return (
                "Resumen operativo: VIGILAR PUT — falta confirmación "
                "completa de la estrategia."
            )

        return (
            "Resumen operativo: ESPERAR — no hay entrada confirmada."
        )

    def _extract_diagnostic_value(
        self,
        diagnostics: str,
        key: str,
    ) -> str:

        for line in diagnostics.splitlines():
            cleaned_line = line.strip()

            if cleaned_line.startswith(
                key,
            ):
                return cleaned_line.replace(
                    key,
                    "",
                    1,
                ).strip()

        return ""