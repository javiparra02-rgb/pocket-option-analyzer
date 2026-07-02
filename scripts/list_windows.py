from pocket_option_analyzer.infrastructure.capture.adapters import (
    WindowEnumerator,
)


def main() -> None:
    enumerator = WindowEnumerator()

    print("=" * 80)
    print("VENTANAS DETECTADAS")
    print("=" * 80)

    for index, window in enumerate(enumerator.enumerate(), start=1):
        print(f"\n[{index}]")
        print(f"Título : {window.title}")
        print(f"Posición: ({window.left}, {window.top})")
        print(f"Tamaño  : {window.width} x {window.height}")


if __name__ == "__main__":
    main()