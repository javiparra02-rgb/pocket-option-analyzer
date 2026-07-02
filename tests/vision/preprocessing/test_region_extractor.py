import numpy as np

from pocket_option_analyzer.vision.preprocessing import RegionExtractor


def test_extract_region() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    roi = RegionExtractor.extract(
        image=image,
        x=20,
        y=10,
        width=80,
        height=50,
    )

    assert roi.shape == (50, 80, 3)