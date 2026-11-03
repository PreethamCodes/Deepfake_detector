"""CPU inference adapter for Yang et al.'s D³ classifier."""

import math
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Literal

import torch
from clip.model import VisionTransformer
from pydantic import BaseModel, Field
from torch import nn
from torch.nn import functional as F

from truthscan.models.image.weights import ASSETS, BACKBONE, DEFAULT_DIR, HEAD, verify
from truthscan.processing.image import ImageInputError, preprocess


class Result(BaseModel):
    model_name: Literal["D³ (ViT-L/14)"] = "D³ (ViT-L/14)"
    processing_time_ms: float = Field(ge=0)


class Detection(Result):
    prediction: Literal["REAL", "AI-GENERATED"]
    detection_score: float = Field(ge=0, le=1)
    warning: str = "The score is an uncalibrated classifier output."


class Failure(Result):
    error_code: Literal["invalid_image", "model_unavailable", "inference_failed"]
    error: str
    prediction: None = None
    detection_score: None = None


class AttentionHead(nn.Module):
    def __init__(self):
        super().__init__()
        self.query = nn.Linear(1024, 1024)
        self.key = nn.Linear(1024, 1024)
        self.value = nn.Linear(1024, 1024)
        self.fc = nn.Linear(2048, 1)

    def forward(self, features):
        similarities = self.query(features) @ self.key(features).transpose(1, 2)
        # The released classifier normalizes over query positions.
        attention = (similarities / math.sqrt(1024)).softmax(dim=1)
        return self.fc((attention @ self.value(features)).flatten(1))


class D3Detector:
    def __init__(self, weights: Path = DEFAULT_DIR):
        self.weights = Path(weights)
        self._model = None
        self._load_lock = Lock()

    def _load(self):
        for name, (_, digest) in ASSETS.items():
            verify(self.weights / name, digest)
        archive = torch.jit.load(str(self.weights / BACKBONE), map_location="cpu")
        with torch.device("meta"):
            visual = VisionTransformer(224, 14, 1024, 24, 16, 768)
            head = AttentionHead()
        visual.load_state_dict(archive.visual.state_dict(), assign=True)
        del archive
        visual.proj = None  # Expose CLIP's normalized, pre-projection CLS features.
        head.load_state_dict(torch.load(self.weights / HEAD, weights_only=True,
                                        map_location="cpu"), assign=True)
        return visual.float().eval(), head.float().eval()

    @torch.inference_mode()
    def detect(self, path: str | Path) -> Detection | Failure:
        start = perf_counter()

        def elapsed():
            return (perf_counter() - start) * 1000

        try:
            image = preprocess(Path(path))
        except ImageInputError as exc:
            return Failure(error_code="invalid_image", error=str(exc), processing_time_ms=elapsed())

        with self._load_lock:
            if self._model is None:
                try:
                    self._model = self._load()
                except (OSError, ValueError, RuntimeError) as exc:
                    return Failure(error_code="model_unavailable", error=str(exc), processing_time_ms=elapsed())

        visual, head = self._model
        try:
            patches = F.unfold(image, kernel_size=14, stride=14)
            order = torch.randperm(patches.size(-1), generator=torch.Generator().manual_seed(418))
            shuffled = F.fold(patches[:, :, order], (224, 224), kernel_size=14, stride=14)
            features = visual(torch.cat([shuffled, image])).unsqueeze(0)
            logit = head(features).item()
            if not math.isfinite(logit):
                raise ValueError("D³ produced a non-finite logit.")
            score = torch.sigmoid(torch.tensor(logit)).item()
        except (ValueError, RuntimeError) as exc:
            return Failure(error_code="inference_failed", error=str(exc), processing_time_ms=elapsed())
        return Detection(prediction="AI-GENERATED" if score > 0.5 else "REAL",
                         detection_score=score, processing_time_ms=elapsed())
