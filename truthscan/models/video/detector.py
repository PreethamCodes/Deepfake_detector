"""Run face-based GenD inference on Phase 3 representative frames."""

from pathlib import Path
from statistics import fmean
from threading import Lock
from time import perf_counter
from typing import Literal

import cv2
from pydantic import BaseModel, Field

from truthscan.models.video.weights import DEFAULT_DIR
from truthscan.processing.video import VideoConfig, VideoFailure, VideoMetadata, process_video

Prediction = Literal["REAL", "AI-GENERATED"]


def _label(score: float) -> Prediction:
    return "AI-GENERATED" if score > 0.5 else "REAL"


class FrameResult(BaseModel):
    index: int
    timestamp_seconds: float
    prediction: Prediction | None
    detection_score: float | None = Field(ge=0, le=1)
    status: Literal["scored", "no_face"]


class Result(BaseModel):
    model_name: Literal["GenD CLIP-L/14"] = "GenD CLIP-L/14"
    processing_time_ms: float
    metadata: VideoMetadata | None = None
    frames: list[FrameResult] = Field(default_factory=list)


class VideoDetection(Result):
    metadata: VideoMetadata
    prediction: Prediction
    detection_score: float = Field(ge=0, le=1)
    warning: str = "Uncalibrated score for detected faces in sampled frames only."


class DetectionFailure(Result):
    error_code: Literal["invalid_video", "model_unavailable", "inference_failed", "no_faces"]
    error: str
    prediction: None = None
    detection_score: None = None


class GenDDetector:
    def __init__(self, weights: Path = DEFAULT_DIR):
        self.weights = Path(weights)
        self._scorer = None
        self._lock = Lock()

    def _load(self):
        from truthscan.models.video.model import FaceScorer
        return FaceScorer(self.weights)

    def detect(self, path: str | Path, config: VideoConfig | None = None) -> VideoDetection | DetectionFailure:
        start = perf_counter()
        frames = []
        processed = process_video(path, config or VideoConfig(size=512))

        def details():
            return dict(processing_time_ms=(perf_counter() - start) * 1000, frames=frames,
                        metadata=None if isinstance(processed, VideoFailure) else processed.metadata)

        if isinstance(processed, VideoFailure):
            return DetectionFailure(error_code="invalid_video", error=processed.error, **details())

        # YuNet input size and its internal buffers are mutable. Serialize shared-instance inference.
        with self._lock:
            if self._scorer is None:
                try:
                    self._scorer = self._load()
                except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as exc:
                    return DetectionFailure(error_code="model_unavailable", error=str(exc), **details())
            try:
                for sample in processed.frames:
                    score = self._scorer.score(sample.rgb)
                    frames.append(FrameResult(index=sample.index, timestamp_seconds=sample.timestamp_seconds,
                                              status="no_face" if score is None else "scored",
                                              detection_score=score, prediction=None if score is None else _label(score)))
            except (OSError, ValueError, RuntimeError, cv2.error) as exc:
                return DetectionFailure(error_code="inference_failed", error=str(exc), **details())

        scores = [frame.detection_score for frame in frames if frame.detection_score is not None]
        if not scores:
            return DetectionFailure(error_code="no_faces", error="No face detected in any sampled frame.", **details())
        average = fmean(scores)
        return VideoDetection(prediction=_label(average), detection_score=average, **details())
