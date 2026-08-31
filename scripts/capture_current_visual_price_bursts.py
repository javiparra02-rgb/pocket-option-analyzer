"""CLI del harness experimental de bursts de CurrentVisualPrice."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.current_visual_price_burst_harness import (
    CalibrationHarnessError,
    CurrentVisualPriceBurstHarness,
    HarnessConfig,
    build_productive_capture_service,
    build_productive_extractor,
)


def build_parser() -> argparse.ArgumentParser:
    """Construye una CLI explícita, observacional y fail-closed."""

    parser = argparse.ArgumentParser(
        description=(
            "EXPERIMENTAL: captura candidate bursts físicos de "
            "CurrentVisualPrice para calibración offline. Sólo observa; no "
            "hace trading, clicks ni automatización de Pocket Option."
        ),
        epilog=(
            "Un candidate burst NO es un burst S0 aceptado. El harness no "
            "clasifica S0/S1/M. El output debe estar fuera del repositorio y "
            "--expected-commit es obligatorio."
        ),
    )
    parser.add_argument(
        "--frames-per-burst",
        type=int,
        default=5,
        help="Capturas físicas por candidate burst (5–10; default: 5).",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=8.0,
        help="Target inicial de adquisición, no calibración aprobada (default: 8).",
    )
    parser.add_argument(
        "--candidate-bursts",
        type=int,
        default=20,
        help="Número de candidate bursts; no implica aceptación S0 (default: 20).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directorio nuevo/vacío y situado obligatoriamente fuera del repo.",
    )
    parser.add_argument(
        "--preflight-frames",
        type=int,
        default=30,
        help="Capturas capture-only para medir cadencia real (default: 30).",
    )
    parser.add_argument(
        "--expected-commit",
        required=True,
        help="SHA completo que debe coincidir con HEAD; falla cerrado si difiere.",
    )
    parser.add_argument(
        "--inter-burst-delay",
        type=float,
        default=0.0,
        help=(
            "Pausa operativa entre bursts; no define independencia estadística "
            "(default: 0)."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ejecuta el harness sin construir GUI, strategy ni identity runtime."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        config = HarnessConfig(
            frames_per_burst=arguments.frames_per_burst,
            target_fps=arguments.target_fps,
            candidate_bursts=arguments.candidate_bursts,
            preflight_frames=arguments.preflight_frames,
            inter_burst_delay_seconds=arguments.inter_burst_delay,
        )
        repository_root = Path(__file__).resolve().parents[1]
        harness = CurrentVisualPriceBurstHarness(
            capture_service=build_productive_capture_service(),
            extractor=build_productive_extractor(),
        )
        result = harness.run(
            config=config,
            output_directory=arguments.output_dir,
            repository_root=repository_root,
            expected_commit=arguments.expected_commit,
        )
    except (CalibrationHarnessError, OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"session_id={result.session_id}")
    print(f"output={result.output_directory}")
    print(f"source_commit={result.source_commit}")
    print(f"candidate_bursts={result.captured_bursts}")
    print(f"valid_technical_bursts={result.valid_technical_bursts}")
    print("ground_truth_classification=not_performed")
    return 130 if result.interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
