from __future__ import annotations

import shutil
from pathlib import Path

from pocket_option_analyzer.infrastructure.config import (
    Settings,
)
from pocket_option_analyzer.infrastructure.logging import (
    LoggingManager,
)

OUTPUT_DIRECTORY = Path("debug") / "log_rotation"


def main() -> None:

    shutil.rmtree(
        OUTPUT_DIRECTORY,
        ignore_errors=True,
    )

    settings = Settings(
        log_directory=str(
            OUTPUT_DIRECTORY,
        ),
        log_level="INFO",
        log_max_bytes=4096,
        log_backup_count=2,
        log_compression=None,
    )

    manager = LoggingManager(
        settings=settings,
        enable_console=False,
    )

    manager.configure()

    for index in range(
        250,
    ):
        manager.logger.info(f"Rotación de prueba {index:03d} | " + ("X" * 200))

    manager.shutdown()

    generated_files = sorted(
        OUTPUT_DIRECTORY.glob(
            "application*.log*",
        )
    )

    print("Archivos generados:")

    for file_path in generated_files:
        print(f"- {file_path.name}: {file_path.stat().st_size} bytes")

    print(f"Total: {len(generated_files)} archivos")


if __name__ == "__main__":
    main()
