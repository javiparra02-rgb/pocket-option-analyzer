import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from pocket_option_analyzer.infrastructure.vision.windows_price_text_recognizer import (
    WindowsPriceTextRecognizer,
)
from pocket_option_analyzer.vision.services.price_text_recognizer import (
    PriceTextRecognitionError,
)


def payload(angle=0):
    return {
        "engine": "Windows.Media.Ocr",
        "image_width": 320,
        "image_height": 200,
        "text_angle": angle,
        "words": [{"text": "1.234", "x": 230, "y": 15, "width": 55, "height": 10}],
    }


def test_lazy_backend_has_no_side_effects():
    with patch("subprocess.run", side_effect=AssertionError("must not launch")):
        WindowsPriceTextRecognizer()


def test_original_coordinates_and_rotation():
    raw = payload()
    reading = WindowsPriceTextRecognizer._original_coordinates(raw, 320, 200, 400)
    assert reading.words[0].box.coordinates == (230, 15, 285, 25)
    rotated = WindowsPriceTextRecognizer._original_coordinates(
        payload(2), 320, 200, 400
    )
    assert rotated.text_angle == 2 and rotated.words[0].box != reading.words[0].box
    assert (
        raw == payload()
    )  # no clipping, normalization, or mutation of the backend result


@pytest.mark.parametrize(
    "change",
    [{"text_angle": 11}, {"image_width": 319}, {"engine": "remote"}, {"words": None}],
)
def test_invalid_backend_data_rejected(change):
    with pytest.raises(ValueError):
        WindowsPriceTextRecognizer._original_coordinates(
            payload() | change, 320, 200, 400
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows process adapter contract")
def test_process_input_output_and_temporary_cleanup(monkeypatch, tmp_path):
    seen = []

    def run(args, **kwargs):
        assert "-NonInteractive" in args and "-File" in args
        path = Path(args[args.index("-ImagePath") + 1])
        seen.append(path)
        assert path.is_file() and path.suffix == ".png"
        assert kwargs["timeout"] == 2 and kwargs["capture_output"]
        return subprocess.CompletedProcess(args, 0, json.dumps(payload()).encode(), b"")

    monkeypatch.setattr(subprocess, "run", run)
    result = WindowsPriceTextRecognizer().recognize(
        np.zeros((200, 320, 3), np.uint8), timeout=2, max_words=400
    )
    assert result.words[0].text == "1.234" and seen
    assert not seen[0].exists() and not seen[0].parent.exists()


@pytest.mark.parametrize("mode", ["timeout", "backend", "json"])
@pytest.mark.skipif(os.name != "nt", reason="Windows process adapter contract")
def test_process_errors_sanitized(monkeypatch, mode):
    def run(args, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired(args, 1)
        return subprocess.CompletedProcess(
            args, 1 if mode == "backend" else 0, b"not json", b"personal path"
        )

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises((TimeoutError, PriceTextRecognitionError)) as exc:
        WindowsPriceTextRecognizer().recognize(
            np.zeros((200, 320, 3), np.uint8), timeout=1, max_words=400
        )
    assert "personal" not in str(exc.value)
