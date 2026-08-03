from datetime import UTC, datetime

from pocket_option_analyzer.vision.services.dataset_filename_generator import (
    DatasetFilenameGenerator,
)


def test_generate_returns_png_filename() -> None:

    generator = DatasetFilenameGenerator()

    filename = generator.generate()

    assert filename.endswith(
        ".png",
    )
    assert len(filename) > 10


def test_generate_avoids_collision_for_identical_timestamp() -> None:

    fixed_timestamp = datetime(
        2026,
        8,
        3,
        20,
        50,
        25,
        123456,
        tzinfo=UTC,
    )

    tokens = iter(
        (
            "first",
            "second",
        )
    )

    generator = DatasetFilenameGenerator(
        clock=lambda: fixed_timestamp,
        token_factory=lambda: next(tokens),
    )

    first_filename = generator.generate()
    second_filename = generator.generate()

    assert first_filename == ("20260803_205025_123456_first.png")
    assert second_filename == ("20260803_205025_123456_second.png")
    assert first_filename != second_filename
