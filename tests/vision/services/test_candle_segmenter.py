import cv2
import numpy as np

from pocket_option_analyzer.vision.services import (
    CandleSegmenter,
)


def test_segment_returns_candidates():

    mask = np.zeros(
        (200, 200),
        dtype=np.uint8,
    )

    cv2.rectangle(
        mask,
        (40, 50),
        (60, 150),
        255,
        -1,
    )

    result = CandleSegmenter().segment(mask)

    assert len(result) == 1

    assert result[0].width > 0

    assert result[0].height > 0
