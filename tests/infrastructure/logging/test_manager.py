from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from pocket_option_analyzer.infrastructure.config import (
    Settings,
)
from pocket_option_analyzer.infrastructure.logging import (
    LoggingManager,
)


class FakeLogger:
    def __init__(
        self,
    ) -> None:
        self.remove_calls: list[int | None] = []
        self.add_calls: list[
            tuple[
                Any,
                dict[str, Any],
            ]
        ] = []
        self.complete_calls = 0

    def remove(
        self,
        handler_id: int | None = None,
    ) -> None:
        self.remove_calls.append(
            handler_id,
        )

    def add(
        self,
        sink,
        **kwargs,
    ) -> int:
        self.add_calls.append(
            (
                sink,
                kwargs,
            )
        )

        return len(
            self.add_calls,
        )

    def complete(
        self,
    ) -> None:
        self.complete_calls += 1


def test_manager_configures_console_and_rotating_file(
    tmp_path: Path,
) -> None:

    fake_logger = FakeLogger()

    settings = Settings(
        log_directory=str(
            tmp_path,
        ),
        log_level="DEBUG",
        log_max_bytes=2048,
        log_backup_count=3,
        log_compression=None,
    )

    manager = LoggingManager(
        settings=settings,
        logger_instance=fake_logger,
    )

    manager.configure()

    assert fake_logger.remove_calls == [
        None,
    ]

    assert (
        len(
            fake_logger.add_calls,
        )
        == 2
    )

    console_sink, console_options = fake_logger.add_calls[0]

    file_sink, file_options = fake_logger.add_calls[1]

    assert console_sink is sys.stdout
    assert console_options["level"] == "DEBUG"
    assert console_options["enqueue"] is True
    assert console_options["diagnose"] is False

    assert file_sink == (tmp_path / "application.log")
    assert file_options["rotation"] == 2048
    assert file_options["retention"] == 3
    assert file_options["compression"] is None
    assert file_options["enqueue"] is True
    assert file_options["encoding"] == "utf-8"
    assert file_options["delay"] is True

    assert manager.handler_ids == (
        1,
        2,
    )
    assert manager.log_file_path == (tmp_path / "application.log")


def test_manager_can_disable_console_and_flush_logger(
    tmp_path: Path,
) -> None:

    fake_logger = FakeLogger()

    manager = LoggingManager(
        settings=Settings(
            log_directory=str(
                tmp_path,
            ),
        ),
        logger_instance=fake_logger,
        enable_console=False,
    )

    manager.configure()
    manager.shutdown()

    assert (
        len(
            fake_logger.add_calls,
        )
        == 1
    )

    file_sink, _ = fake_logger.add_calls[0]

    assert file_sink == (tmp_path / "application.log")
    assert fake_logger.complete_calls == 1


def test_settings_reject_invalid_log_rotation_values() -> None:

    with pytest.raises(
        ValidationError,
    ):
        Settings(
            log_max_bytes=0,
        )

    with pytest.raises(
        ValidationError,
    ):
        Settings(
            log_backup_count=-1,
        )
