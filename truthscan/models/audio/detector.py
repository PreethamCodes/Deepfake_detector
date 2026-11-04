"""AASIST CPU inference for one speech recording."""
import json
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Literal

import av
import torch
from pydantic import BaseModel

from truthscan.models.assets import verify
from truthscan.models.audio.aasist import Model
from truthscan.models.audio.weights import DEFAULT_DIR, NAME, SHA256
from truthscan.processing.audio import AudioMetadata, preprocess


class Result(BaseModel):
    model_name: Literal["AASIST"] = "AASIST"
    processing_time_ms: float
    metadata: AudioMetadata | None = None


class Detection(Result):
    metadata: AudioMetadata
    prediction: Literal["REAL", "AI-GENERATED"]
    raw_score: float
    spoof_logit: float


class Failure(Result):
    error_code: Literal["invalid_audio", "model_unavailable", "inference_failed"]
    error: str
    prediction: None = None
    raw_score: None = None


class AASISTDetector:
    def __init__(self, weights: Path = DEFAULT_DIR):
        self.weights = Path(weights)
        self._model = None
        self._lock = Lock()

    def _load(self):
        path = self.weights / NAME
        verify(path, SHA256)
        config = json.loads(Path(__file__).with_name("AASIST.conf").read_text())
        model = Model(config["model_config"])
        model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True), strict=True)
        return model.cpu().eval()

    @torch.inference_mode()
    def detect(self, path: str | Path) -> Detection | Failure:
        start = perf_counter()
        metadata = None

        def details():
            return dict(metadata=metadata, processing_time_ms=(perf_counter() - start) * 1000)

        try:
            waveform, metadata = preprocess(Path(path))
        except (OSError, ValueError, av.FFmpegError) as exc:
            return Failure(error_code="invalid_audio", error=str(exc), **details())

        with self._lock:
            if self._model is None:
                try:
                    self._model = self._load()
                except (OSError, RuntimeError, ValueError) as exc:
                    return Failure(error_code="model_unavailable", error=str(exc), **details())
            try:
                _, logits = self._model(torch.from_numpy(waveform).unsqueeze(0))
                if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                    raise ValueError("Invalid AASIST logits.")
                spoof, bona_fide = logits[0].tolist()
            except (RuntimeError, ValueError) as exc:
                return Failure(error_code="inference_failed", error=str(exc), **details())
        return Detection(raw_score=bona_fide, spoof_logit=spoof,
                         prediction="REAL" if bona_fide > spoof else "AI-GENERATED", **details())
