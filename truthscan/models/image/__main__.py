import argparse
from pathlib import Path

from .detector import D3Detector, Failure
from .weights import DEFAULT_DIR


def main():
    parser = argparse.ArgumentParser(description="Analyze one image with D³ on CPU.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--weights", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    result = D3Detector(args.weights).detect(args.image)
    print(result.model_dump_json(indent=2, ensure_ascii=True))
    return int(isinstance(result, Failure))


if __name__ == "__main__":
    raise SystemExit(main())
