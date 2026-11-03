import argparse

from .detector import DetectionFailure, GenDDetector
from .weights import DEFAULT_DIR
from truthscan.processing.video import VideoConfig


def main():
    parser = argparse.ArgumentParser(description="Score sampled faces with GenD on CPU.")
    parser.add_argument("video")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--weights", default=DEFAULT_DIR)
    args = parser.parse_args()
    try:
        config = VideoConfig(samples=args.samples, size=512)
    except ValueError as exc:
        parser.error(str(exc))
    result = GenDDetector(args.weights).detect(args.video, config)
    print(result.model_dump_json(indent=2))
    return int(isinstance(result, DetectionFailure))


if __name__ == "__main__":
    raise SystemExit(main())
