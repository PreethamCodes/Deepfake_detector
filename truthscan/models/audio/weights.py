"""Install the official pretrained AASIST (full-size) checkpoint."""
import argparse
from pathlib import Path

from truthscan.models.assets import install_assets

DEFAULT_DIR = Path("checkpoints/aasist")
REV = "a04c9863f63d44471dde8a6abcb3b082b07cd1d1"
NAME = "AASIST.pth"
SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
ASSETS = {NAME: (f"https://raw.githubusercontent.com/clovaai/aasist/{REV}/models/weights/{NAME}", SHA256)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_DIR)
    try:
        install_assets(parser.parse_args().weights, ASSETS)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"AASIST setup failed: {exc}\n")
    print("Verified official AASIST checkpoint.")
