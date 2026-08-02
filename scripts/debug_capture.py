from pathlib import Path

from pocket_option_analyzer.infrastructure.capture.adapters import (
    MSSCaptureAdapter,
    Win32WindowLocator,
)
from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)
from pocket_option_analyzer.vision import VisionPipeline
from pocket_option_analyzer.vision.services import DebugImageSaver


def main() -> None:
    locator = Win32WindowLocator()
    capture = MSSCaptureAdapter()

    service = CaptureService(
        locator=locator,
        capture=capture,
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    frame = service.capture_once()

    if frame is None:
        print("No se encontró la ventana de Pocket Option.")
        return

    pipeline = VisionPipeline()

    processed = pipeline.process(frame.image)

    saver = DebugImageSaver(Path("debug"))

    original_path = saver.save(frame.image, "001_original.png")
    processed_path = saver.save(processed, "002_processed.png")

    print("Captura completada correctamente.")
    print(f"Original:  {original_path}")
    print(f"Procesada: {processed_path}")


if __name__ == "__main__":
    main()
