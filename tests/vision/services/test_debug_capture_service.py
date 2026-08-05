from pathlib import Path

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services.debug_capture_service import (
    DebugCaptureService,
)


def test_save_debug_images(
    tmp_path: Path,
) -> None:

    image = np.zeros(
        (
            300,
            400,
            3,
        ),
        dtype=np.uint8,
    )

    region = ChartRegion(
        x=50,
        y=60,
        width=100,
        height=80,
    )

    service = DebugCaptureService(
        tmp_path,
    )

    service.save(
        image,
        region,
    )

    assert (tmp_path / "001_window.png").exists()

    assert (tmp_path / "002_roi_overlay.png").exists()

    assert (tmp_path / "003_chart_roi.png").exists()
