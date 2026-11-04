import argparse

from .detector import AASISTDetector, Failure
from .weights import DEFAULT_DIR


def main():
    parser = argparse.ArgumentParser(description="Analyze a speech recording with AASIST on CPU.")
    parser.add_argument("audio")
    parser.add_argument("--weights", default=DEFAULT_DIR)
    args = parser.parse_args()
    result = AASISTDetector(args.weights).detect(args.audio)
    print(result.model_dump_json(indent=2))
    return int(isinstance(result, Failure))


if __name__ == "__main__":
    raise SystemExit(main())
