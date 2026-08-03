from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

Clock = Callable[[], datetime]
TokenFactory = Callable[[], str]


def _utc_now() -> datetime:
    return datetime.now(
        tz=UTC,
    )


def _unique_token() -> str:
    return uuid4().hex


class DatasetFilenameGenerator:
    """
    Genera nombres únicos y cronológicamente identificables
    para las imágenes del dataset.
    """

    def __init__(
        self,
        clock: Clock = _utc_now,
        token_factory: TokenFactory = _unique_token,
    ) -> None:
        self._clock = clock
        self._token_factory = token_factory

    def generate(
        self,
    ) -> str:
        timestamp = self._clock()

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=UTC,
            )

        timestamp_text = timestamp.astimezone(
            UTC,
        ).strftime(
            "%Y%m%d_%H%M%S_%f",
        )

        unique_token = self._token_factory()

        if not unique_token:
            raise ValueError("Dataset filename token cannot be empty.")

        return f"{timestamp_text}_{unique_token}.png"
