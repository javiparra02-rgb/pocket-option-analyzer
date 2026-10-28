"""Explicit, local Windows OCR adapter. Never captures a screen or downloads models."""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from pocket_option_analyzer.vision.models.independent_visual_price import (
    OcrReading,
    OcrWord,
    PixelBox,
)
from pocket_option_analyzer.vision.services.price_text_recognizer import (
    PriceTextRecognitionError,
)


class WindowsPriceTextRecognizer:
    """Lazy backend; constructing this object performs no IO or process launch."""

    def recognize(
        self, image: NDArray[np.uint8], *, timeout: float, max_words: int
    ) -> OcrReading:
        if os.name != "nt":
            raise PriceTextRecognitionError("WINDOWS_OCR_UNAVAILABLE")
        if timeout <= 0 or max_words < 1 or image.size > 12_000_000:
            raise PriceTextRecognitionError("OCR_WORK_BUDGET")
        executable = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        bridge = Path(__file__).with_name("price_ocr_bridge.ps1")
        if not executable.is_file() or not bridge.is_file():
            raise PriceTextRecognitionError("WINDOWS_OCR_UNAVAILABLE")
        ok, png = cv2.imencode(".png", image)
        if not ok:
            raise PriceTextRecognitionError("OCR_IMAGE_ENCODING_FAILED")
        # A private temporary copy of the supplied observation, never a new capture.
        with tempfile.TemporaryDirectory(prefix="poa-h1-ocr-") as directory:
            input_path = Path(directory) / "observation.png"
            input_path.write_bytes(png.tobytes())
            try:
                completed = subprocess.run(
                    [
                        str(executable),
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(bridge),
                        "-ImagePath",
                        str(input_path),
                        "-MaxWords",
                        str(max_words),
                    ],
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("OCR_TIMEOUT") from exc
        if completed.returncode != 0:
            raise PriceTextRecognitionError("OCR_BACKEND_FAILED")
        if len(completed.stdout) > 1_000_000:
            raise PriceTextRecognitionError("OCR_OUTPUT_BUDGET")
        try:
            data = json.loads(completed.stdout.decode("utf-8-sig"))
            return self._original_coordinates(
                data, image.shape[1], image.shape[0], max_words
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise PriceTextRecognitionError("OCR_INVALID_RESULT") from exc

    @staticmethod
    def _original_coordinates(
        data: Any, width: int, height: int, max_words: int
    ) -> OcrReading:
        if not isinstance(data, dict) or data["engine"] != "Windows.Media.Ocr":
            raise ValueError("Unexpected OCR engine")
        if data["image_width"] != width or data["image_height"] != height:
            raise ValueError("OCR geometry mismatch")
        angle = float(data.get("text_angle") or 0)
        if not math.isfinite(angle) or abs(angle) > 10:
            raise ValueError("OCR rotation outside domain")
        words = data["words"]
        if not isinstance(words, list) or len(words) > max_words:
            raise ValueError("OCR word budget")
        radians = math.radians(angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        cx, cy = width / 2, height / 2
        output = []
        for word in words:
            if not isinstance(word["text"], str) or len(word["text"]) > 512:
                raise ValueError("Invalid OCR text")
            x, y, w, h = (float(word[k]) for k in ("x", "y", "width", "height"))
            if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0:
                raise ValueError("Invalid OCR rectangle")
            corners = [
                (
                    cx + cosine * (px - cx) - sine * (py - cy),
                    cy + sine * (px - cx) + cosine * (py - cy),
                )
                for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))
            ]
            box = PixelBox(
                math.floor(min(p[0] for p in corners)),
                math.floor(min(p[1] for p in corners)),
                math.ceil(max(p[0] for p in corners)),
                math.ceil(max(p[1] for p in corners)),
            )
            output.append(OcrWord(word["text"], box))
        return OcrReading(tuple(output), "Windows.Media.Ocr/es-ES", angle)
