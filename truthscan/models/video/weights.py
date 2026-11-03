"""Fetch the pinned GenD checkpoint, CLIP configuration and YuNet face localizer."""

import argparse
from pathlib import Path

from truthscan.models.assets import install_assets

DEFAULT_DIR = Path("checkpoints/gend")
GEND_REV = "891ce014a0308386c4d7d25b3dcf436a22db5504"
CLIP_REV = "32bd64288804d66eefd0ccbe215aa642df71cc41"
CLIP_URL = f"https://huggingface.co/openai/clip-vit-large-patch14/resolve/{CLIP_REV}"
ASSETS = {
    "model.safetensors": (
        f"https://huggingface.co/yermandy/GenD_CLIP_L_14/resolve/{GEND_REV}/model.safetensors",
        "d76f0bdfd74a29fe1b1c1b84a80ac92486993e426878e8c7a3944281fbb96833",
    ),
    "config.json": (f"{CLIP_URL}/config.json",
                    "8a09b467700c58138c29d53c605b34ebc69beaadd13274a8a2af8ad2c2f4032a"),
    "preprocessor_config.json": (f"{CLIP_URL}/preprocessor_config.json",
                                 "910e70b3956ac9879ebc90b22fb3bc8a75b6a0677814500101a4c072bd7857bd"),
    "yunet.onnx": (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
        "48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_DIR)
    try:
        install_assets(parser.parse_args().weights, ASSETS)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"GenD setup failed: {exc}\n")
    print("Verified GenD, CLIP configuration and YuNet assets.")
