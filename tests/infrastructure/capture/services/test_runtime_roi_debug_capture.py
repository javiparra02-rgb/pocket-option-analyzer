from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import numpy as np
import pytest

from pocket_option_analyzer.infrastructure.capture.services import (
    RuntimeRoiDebugCapture,
)


def _write_debug_image(
    path: str,
    _image: np.ndarray,
) -> bool:
    Path(
        path,
    ).write_bytes(
        b"runtime-roi-debug-image",
    )

    return True


def test_runtime_roi_debug_capture_saves_image(
    tmp_path: Path,
) -> None:

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="test_roi",
    )

    image = np.zeros(
        (
            20,
            30,
            3,
        ),
        dtype=np.uint8,
    )

    capture.save(
        image=image,
    )

    assert capture.latest_path is not None
    assert capture.latest_path.exists()

    assert capture.latest_path.name.startswith(
        "test_roi_",
    )

    assert capture.latest_path.suffix == ".png"


def test_runtime_roi_debug_capture_keeps_directory_bounded_during_long_session(
    tmp_path: Path,
) -> None:

    fixed_timestamp = datetime(
        2026,
        8,
        3,
        21,
        3,
        14,
        tzinfo=UTC,
    )

    sequence = count()

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        max_files=3,
        clock=lambda: fixed_timestamp,
        token_factory=lambda: f"{next(sequence):04d}",
        image_writer=_write_debug_image,
    )

    image = np.zeros(
        (
            20,
            30,
            3,
        ),
        dtype=np.uint8,
    )

    for _ in range(
        100,
    ):
        capture.save(
            image=image,
        )

        assert (
            len(
                list(
                    tmp_path.glob(
                        "roi_*.png",
                    )
                )
            )
            <= 3
        )

    retained_paths = sorted(
        tmp_path.glob(
            "roi_*.png",
        )
    )

    assert [path.name for path in retained_paths] == [
        "roi_20260803_210314_000000_0097.png",
        "roi_20260803_210314_000000_0098.png",
        "roi_20260803_210314_000000_0099.png",
    ]

    assert capture.latest_path == retained_paths[-1]
    assert capture.max_files == 3


def test_runtime_roi_debug_capture_preserves_unrelated_files(
    tmp_path: Path,
) -> None:

    unrelated_text = tmp_path / "notes.txt"

    unrelated_image = tmp_path / "other_20260803_210314_000000.png"

    unrelated_text.write_text(
        "keep",
        encoding="utf-8",
    )

    unrelated_image.write_bytes(
        b"keep-other-image",
    )

    tokens = iter(
        (
            "first",
            "second",
        )
    )

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        max_files=1,
        clock=lambda: datetime(
            2026,
            8,
            3,
            21,
            3,
            14,
            tzinfo=UTC,
        ),
        token_factory=lambda: next(
            tokens,
        ),
        image_writer=_write_debug_image,
    )

    image = np.zeros(
        (
            20,
            30,
            3,
        ),
        dtype=np.uint8,
    )

    capture.save(
        image=image,
    )

    capture.save(
        image=image,
    )

    retained_roi_paths = list(
        tmp_path.glob(
            "roi_*.png",
        )
    )

    assert (
        len(
            retained_roi_paths,
        )
        == 1
    )

    assert retained_roi_paths[0] == capture.latest_path

    assert (
        unrelated_text.read_text(
            encoding="utf-8",
        )
        == "keep"
    )

    assert unrelated_image.read_bytes() == (b"keep-other-image")


@pytest.mark.parametrize(
    "max_files",
    [
        0,
        -1,
    ],
)
def test_runtime_roi_debug_capture_rejects_invalid_retention(
    tmp_path: Path,
    max_files: int,
) -> None:

    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        RuntimeRoiDebugCapture(
            directory=tmp_path,
            max_files=max_files,
        )


def test_runtime_roi_debug_capture_removes_temporary_file_when_write_fails(
    tmp_path: Path,
) -> None:

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        clock=lambda: datetime(
            2026,
            8,
            3,
            21,
            3,
            14,
            tzinfo=UTC,
        ),
        token_factory=lambda: "failed",
        image_writer=lambda _path, _image: False,
    )

    image = np.zeros(
        (
            20,
            30,
            3,
        ),
        dtype=np.uint8,
    )

    with pytest.raises(
        RuntimeError,
        match="Could not save runtime ROI debug image",
    ):
        capture.save(
            image=image,
        )

    assert capture.latest_path is None

    assert (
        list(
            tmp_path.iterdir(),
        )
        == []
    )
