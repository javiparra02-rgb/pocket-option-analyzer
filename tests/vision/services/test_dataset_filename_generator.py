from pocket_option_analyzer.vision.services.dataset_filename_generator import (
    DatasetFilenameGenerator,
)


def test_generate_returns_png_filename() -> None:
    generator = DatasetFilenameGenerator()

    filename = generator.generate()

    assert filename.endswith(".png")
    assert len(filename) > 10
