import argparse

from .engine import analyze


def main():
    parser = argparse.ArgumentParser(description="Analyze related local files as one forensic case.")
    parser.add_argument("--image", help="JPEG or PNG image")
    parser.add_argument("--video", help="Video for sampled-face analysis")
    parser.add_argument("--audio", help="Standalone WAV, MP3 or FLAC speech recording")
    args = parser.parse_args()
    report = analyze(image=args.image, video=args.video, audio=args.audio)
    print(report.model_dump_json(indent=2, ensure_ascii=True))
    return int(report.assessment == "INCONCLUSIVE")


if __name__ == "__main__":
    raise SystemExit(main())
