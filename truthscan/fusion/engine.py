"""Combine detector labels for one case without comparing their score scales."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, JsonValue

if TYPE_CHECKING:
    from truthscan.models.audio.detector import Detection as Audio, Failure as AudioFailure
    from truthscan.models.image.detector import Detection as Image, Failure as ImageFailure
    from truthscan.models.video.detector import DetectionFailure as VideoFailure, VideoDetection

Modality = Literal["image", "video", "audio"]
Label = Literal["REAL", "AI-GENERATED"]
MODELS = {"image": "D³ (ViT-L/14)", "video": "GenD CLIP-L/14", "audio": "AASIST"}


class Finding(BaseModel):
    source: str
    result: dict[str, JsonValue]


class FrameLocation(BaseModel):
    index: int
    timestamp_seconds: float


class DetectorException(BaseModel):
    model_name: str
    prediction: None = None
    error_code: Literal["detector_exception"] = "detector_exception"
    error: str


class ForensicReport(BaseModel):
    assessment: Literal["REAL", "AI-GENERATED", "INCONCLUSIVE"]
    agreement: Literal["none", "single", "agree", "conflict"]
    reason: str
    findings: dict[Modality, Finding]
    not_supplied: list[Modality]
    flagged_modalities: list[Modality]
    flagged_video_frames: list[FrameLocation]
    scope: str = ("Labels describe model findings on the analyzed inputs. "
                  "Scores are uncalibrated. Content truth and common provenance are unverified.")


def _detect(modality: Modality, path: str | Path):
    # Load only the optional dependencies needed for the supplied input.
    if modality == "image":
        from truthscan.models.image.detector import D3Detector
        return D3Detector().detect(path)
    if modality == "video":
        from truthscan.models.video.detector import GenDDetector
        return GenDDetector().detect(path)
    from truthscan.models.audio.detector import AASISTDetector
    return AASISTDetector().detect(path)


def analyze(*, image: str | Path | None = None, video: str | Path | None = None,
            audio: str | Path | None = None) -> ForensicReport:
    """Run the requested detectors on caller-associated local files, one at a time."""
    inputs: dict[Modality, str | Path | None] = {"image": image, "video": video, "audio": audio}
    completed = {}
    for modality, path in inputs.items():
        if path is None:
            continue
        try:
            outcome = _detect(modality, path)
        except Exception as exc:
            # Isolate optional import/native runtime errors to this modality.
            outcome = DetectorException(model_name=MODELS[modality], error=f"{type(exc).__name__}: {exc}")
        completed[modality] = (path, outcome)
    return fuse(**completed)


def fuse(*, image: tuple[str | Path, Image | ImageFailure | DetectorException] | None = None,
         video: tuple[str | Path, VideoDetection | VideoFailure | DetectorException] | None = None,
         audio: tuple[str | Path, Audio | AudioFailure | DetectorException] | None = None) -> ForensicReport:
    """Combine existing native detector results with their source paths, without running inference."""
    findings = {}
    votes: dict[Modality, Label] = {}
    failures = []
    flagged_frames = []
    inputs = {"image": image, "video": video, "audio": audio}
    for modality, item in inputs.items():
        if item is None:
            continue
        path, outcome = item
        if outcome.model_name != MODELS[modality]:
            raise ValueError(f"Unexpected detector for {modality}: {outcome.model_name}")
        findings[modality] = Finding(source=str(path), result=outcome.model_dump(mode="json"))
        if outcome.prediction is None:
            failures.append(modality)
        else:
            votes[modality] = outcome.prediction
        if modality == "video" and not isinstance(outcome, DetectorException):
            flagged_frames = [
                FrameLocation(index=f.index, timestamp_seconds=f.timestamp_seconds)
                for f in outcome.frames if f.status == "scored" and f.prediction == "AI-GENERATED"
            ]

    labels = set(votes.values())
    if not votes:
        agreement, assessment, reason = "none", "INCONCLUSIVE", "No detector returned a verdict."
    elif len(labels) > 1:
        agreement, assessment, reason = "conflict", "INCONCLUSIVE", "Detector labels conflict."
    else:
        assessment = next(iter(labels))
        agreement = "single" if len(votes) == 1 else "agree"
        reason = ("One detector returned a verdict." if len(votes) == 1
                  else "All detectors that returned verdicts agree.")
    if failures:
        assessment = "INCONCLUSIVE"
        reason += " Requested analysis failed for " + ", ".join(failures) + "."
    return ForensicReport(
        assessment=assessment, agreement=agreement, reason=reason, findings=findings,
        not_supplied=[m for m in inputs if m not in findings],
        flagged_modalities=[m for m, label in votes.items() if label == "AI-GENERATED"],
        flagged_video_frames=flagged_frames,
    )
