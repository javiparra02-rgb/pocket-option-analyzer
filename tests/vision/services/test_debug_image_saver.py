import numpy as np

from pocket_option_analyzer.vision.services import DebugImageSaver


def test_save_image(tmp_path) -> None:
    saver = DebugImageSaver(tmp_path)

    image = np.zeros((20, 20, 3), dtype=np.uint8)

    output = saver.save(
        image=image,
        filename="test.png",
    )

    assert output.exists()
    assert output.name == "test.png"
