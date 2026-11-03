"""CPU adapter for the official GenD CLIP-L/14 LinearNorm checkpoint."""

import cv2
import numpy as np
import torch
from PIL import Image
from safetensors import SafetensorError
from safetensors.torch import load_file
from torch import nn
from torch.nn import functional as F
from transformers import CLIPImageProcessorFast, CLIPVisionConfig, CLIPVisionModelWithProjection

from truthscan.models.assets import verify
from truthscan.models.video.weights import ASSETS


class GenDModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.feature_extractor = CLIPVisionModelWithProjection(config)
        self.model = nn.Module()
        self.model.linear = nn.Linear(config.hidden_size, 2)

    def forward(self, pixels):
        features = self.feature_extractor.vision_model(pixels).pooler_output
        return self.model.linear(F.normalize(features, dim=1))


class FaceScorer:
    def __init__(self, directory):
        for name, (_, digest) in ASSETS.items():
            verify(directory / name, digest)
        config = CLIPVisionConfig.from_pretrained(directory, local_files_only=True)
        # Avoid allocating a second, randomly initialized 1.2 GB parameter set.
        with torch.device("meta"):
            self.model = GenDModel(config)
        try:
            state = load_file(directory / "model.safetensors")
        except SafetensorError as exc:
            raise ValueError("Cannot read GenD checkpoint tensors.") from exc
        self.model.load_state_dict(state, strict=True, assign=True)
        embeddings = self.model.feature_extractor.vision_model.embeddings
        # Transformers marks this deterministic index buffer as nonpersistent.
        embeddings.position_ids = torch.arange(embeddings.num_positions).unsqueeze(0)
        self.model.eval()
        self.processor = CLIPImageProcessorFast.from_pretrained(directory, local_files_only=True)
        self.faces = cv2.FaceDetectorYN.create(str(directory / "yunet.onnx"), "", (512, 512), 0.75)

    @torch.inference_mode()
    def score(self, rgb):
        self.faces.setInputSize((rgb.shape[1], rgb.shape[0]))
        _, faces = self.faces.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if faces is None or not len(faces):
            return None
        face = max(faces, key=lambda detection: detection[2] * detection[3])
        crop = align_face(rgb, face[4:14].reshape(5, 2))
        pixels = self.processor(images=Image.fromarray(crop), return_tensors="pt").pixel_values
        score = self.model(pixels).softmax(dim=-1)[0, 1].item()
        if not np.isfinite(score):
            raise ValueError("GenD produced a non-finite score.")
        return score


def align_face(rgb, landmarks):
    # GenD reference landmark template and 1.3 context margin, at target size 224.
    template = np.array([[.34, .46], [.66, .46], [.5, .64], [.37, .82], [.63, .82]],
                        dtype=np.float32)
    target = (template + .15) * (224 / 1.3)
    transform, _ = cv2.estimateAffinePartial2D(landmarks, target, method=cv2.LMEDS)
    if transform is None or not np.isfinite(transform).all():
        raise ValueError("Cannot align face landmarks.")
    return cv2.warpAffine(rgb, transform, (224, 224), flags=cv2.INTER_LINEAR)
