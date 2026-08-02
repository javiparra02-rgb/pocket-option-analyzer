from pathlib import Path

import numpy as np

from pocket_option_analyzer.vision.services import (
    DatasetCaptureService,
    DatasetDirectoryManager,
    DatasetFilenameGenerator,
)


def test_save_creates_image(tmp_path: Path) -> None:

    manager = DatasetDirectoryManager(tmp_path)

    generator = DatasetFilenameGenerator()

    service = DatasetCaptureService(
        directory_manager=manager,
        filename_generator=generator,
    )

    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    path = service.save(image)

    assert path.exists()
    assert path.suffix == ".png"
