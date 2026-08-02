from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame


def test_frame_dimensions() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=image,
    )

    assert frame.width == 1280
    assert frame.height == 720
    assert frame.channels == 3
