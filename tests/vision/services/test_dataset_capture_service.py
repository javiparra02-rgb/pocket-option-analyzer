from pathlib import Path

import numpy as np
import pytest

from pocket_option_analyzer.vision.services import (
    DatasetCaptureService,
    DatasetDirectoryManager,
    DatasetFilenameGenerator,
)
from pocket_option_analyzer.vision.services import (
    dataset_capture_service as dataset_capture_service_module,
)


class FixedFilenameGenerator:
    def __init__(
        self,
        filename: str,
    ) -> None:
        self._filename = filename

    def generate(
        self,
    ) -> str:
        return self._filename


def _image() -> np.ndarray:
    return np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )


def test_save_creates_image(tmp_path: Path) -> None:

    manager = DatasetDirectoryManager(
        tmp_path,
    )

    generator = DatasetFilenameGenerator()

    service = DatasetCaptureService(
        directory_manager=manager,
        filename_generator=generator,
    )

    path = service.save(
        _image(),
    )

    assert path.exists()
    assert path.is_file()
    assert path.suffix == ".png"
    assert path.stat().st_size > 0

    assert list(
        manager.raw.iterdir(),
    ) == [
        path,
    ]


def test_save_removes_temporary_file_when_encoder_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    manager = DatasetDirectoryManager(
        tmp_path,
    )

    service = DatasetCaptureService(
        directory_manager=manager,
        filename_generator=FixedFilenameGenerator(
            "failed.png",
        ),
    )

    def fail_write(
        _path: str,
        _image: np.ndarray,
    ) -> bool:
        return False

    monkeypatch.setattr(
        dataset_capture_service_module.cv2,
        "imwrite",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="Could not save dataset image",
    ):
        service.save(
            _image(),
        )

    assert (
        list(
            manager.raw.iterdir(),
        )
        == []
    )


def test_save_does_not_overwrite_existing_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    manager = DatasetDirectoryManager(
        tmp_path,
    )

    service = DatasetCaptureService(
        directory_manager=manager,
        filename_generator=FixedFilenameGenerator(
            "existing.png",
        ),
    )

    destination = manager.raw / "existing.png"

    original_content = b"original-dataset-image"

    destination.write_bytes(
        original_content,
    )

    def unexpected_write(
        _path: str,
        _image: np.ndarray,
    ) -> bool:
        raise AssertionError("cv2.imwrite should not be called.")

    monkeypatch.setattr(
        dataset_capture_service_module.cv2,
        "imwrite",
        unexpected_write,
    )

    with pytest.raises(
        FileExistsError,
        match="Dataset image already exists",
    ):
        service.save(
            _image(),
        )

    assert destination.read_bytes() == original_content
    assert list(
        manager.raw.iterdir(),
    ) == [
        destination,
    ]
