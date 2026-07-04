from pathlib import Path

from pocket_option_analyzer.vision.services.dataset_directory_manager import (
    DatasetDirectoryManager,
)


def test_create_directories(tmp_path: Path) -> None:

    manager = DatasetDirectoryManager(tmp_path)

    manager.create()

    assert manager.raw.exists()
    assert manager.processed.exists()
    assert manager.metadata.exists()

    assert manager.raw.is_dir()
    assert manager.processed.is_dir()
    assert manager.metadata.is_dir()