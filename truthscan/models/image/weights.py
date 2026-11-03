"""Install pinned model assets separately from the application source."""

import argparse
from pathlib import Path
from truthscan.models.assets import install_assets, verify

DEFAULT_DIR = Path("checkpoints/d3")
HEAD = "classifier.pth"
BACKBONE = "ViT-L-14.pt"
BACKBONE_SHA = "b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836"
ASSETS = {
    HEAD: (
        "https://raw.githubusercontent.com/BigAandSmallq/D3/"
        "14f21ad3797ef1e42f2f6090aa8ad4fabf07896c/ckpt/classifier.pth",
        "c0bb66e0de538b0330613da1865da025756c1dc7a7290990d5343c35290ab63b",
    ),
    BACKBONE: (
        f"https://openaipublic.azureedge.net/clip/models/{BACKBONE_SHA}/{BACKBONE}",
        BACKBONE_SHA,
    ),
}


def install(directory: Path) -> None:
    install_assets(directory, ASSETS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_DIR)
    try:
        install(parser.parse_args().weights)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Model setup failed: {exc}\n")
    print("Verified both D3 checkpoints.")
