"""Validate and sample a local video without retaining the decoded sequence."""

import argparse
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Literal

import av
import cv2
import numpy as np
from av.stream import Disposition
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from truthscan.processing.limits import VIDEO_BYTES

CONTAINER_FORMATS = {".mp4": "mov", ".mov": "mov", ".avi": "avi", ".mkv": "matroska"}


class VideoConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    samples: int = Field(default=8, ge=1, le=64)
    size: int = Field(default=224, ge=32, le=512)
    max_bytes: int = Field(default=VIDEO_BYTES, gt=0)
    max_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    max_frames: int = Field(default=36_000, gt=0)
    max_pixels: int = Field(default=3840 * 2160, gt=0)


class VideoMetadata(BaseModel):
    width: int
    height: int
    frame_count: int
    duration_seconds: float
    fps: float


class SampledFrame(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    index: int
    timestamp_seconds: float
    rgb: SkipJsonSchema[np.ndarray] = Field(exclude=True, repr=False)


class ProcessedVideo(BaseModel):
    status: Literal["processed"] = "processed"
    metadata: VideoMetadata
    frame_size: int
    frames: list[SampledFrame]
    processing_time_ms: float


class VideoFailure(BaseModel):
    status: Literal["error"] = "error"
    error: str
    processing_time_ms: float


def _indices(total: int, requested: int) -> set[int]:
    count = min(total, requested)
    if count == 1:
        return {total // 2}
    return {round(i * (total - 1) / (count - 1)) for i in range(count)}


def _prepare(frame: av.VideoFrame, size: int) -> np.ndarray:
    rgb = frame.to_ndarray(format="rgb24")
    angle = frame.rotation
    if angle % 90:
        raise ValueError("Unsupported non-right-angle display rotation.")
    rgb = np.rot90(rgb, k=angle // 90)
    height, width = rgb.shape[:2]
    scale = size / max(width, height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    resized = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    output = np.zeros((size, size, 3), dtype=np.uint8)
    x, y = (size - w) // 2, (size - h) // 2
    output[y:y+h, x:x+w] = resized
    return output


@contextmanager
def _open(path: Path, config: VideoConfig):
    expected = CONTAINER_FORMATS[path.suffix.lower()]
    with av.open(str(path.resolve()), options={"format_whitelist": "avi,mov,matroska",
                                               "enable_drefs": "0"}) as container:
        if expected not in container.format.name.split(","):
            raise ValueError("Container and filename extension disagree.")
        stream = next((s for s in container.streams.video
                       if not s.disposition & Disposition.attached_pic), None)
        if stream is None:
            raise ValueError("No video track found.")
        if not 0 < stream.width * stream.height <= config.max_pixels:
            raise ValueError("Invalid or oversized video resolution.")
        if stream.frames > config.max_frames:
            raise ValueError("Video exceeds the frame count limit.")
        if stream.duration and stream.duration * stream.time_base > config.max_seconds:
            raise ValueError("Video exceeds the duration limit.")
        stream.codec_context.thread_count = 2
        stream.codec_context.options = {"err_detect": "explode", "max_pixels": str(config.max_pixels)}
        yield container, stream


def _scan(container, stream, config: VideoConfig, indices: set[int]):
    width, height = stream.width, stream.height
    frames = []
    first = previous = end = None
    count = 0
    for index, frame in enumerate(container.decode(stream)):
        count = index + 1
        if count > config.max_frames:
            raise ValueError("Video exceeds the frame count limit.")
        if frame.is_corrupt or (frame.width, frame.height) != (width, height):
            raise ValueError("Damaged frame or changing video resolution.")
        if frame.pts is None or frame.time_base is None:
            raise ValueError("Video is missing frame timestamps.")
        timestamp = float(frame.pts * frame.time_base)
        if first is None:
            first = timestamp
        if previous is not None and timestamp < previous:
            raise ValueError("Video timestamps run backwards.")
        interval = float(frame.duration * frame.time_base) if frame.duration else 0
        if interval <= 0:
            interval = timestamp - previous if previous is not None else 0
            if interval == 0 and stream.average_rate:
                interval = 1 / float(stream.average_rate)
        end = timestamp + interval
        if end - first > config.max_seconds:
            raise ValueError("Video exceeds the duration limit.")
        if index in indices:
            frames.append(SampledFrame(index=index, timestamp_seconds=timestamp,
                                       rgb=_prepare(frame, config.size)))
        previous = timestamp
    if not count or end <= first:
        raise ValueError("No decodable video with a positive duration.")
    seconds = end - first
    metadata = VideoMetadata(width=width, height=height, frame_count=count,
                             duration_seconds=seconds, fps=count / seconds)
    return metadata, frames


def process_video(path: str | Path, config: VideoConfig | None = None) -> ProcessedVideo | VideoFailure:
    """Return source metadata and uniformly spaced, presentation-order RGB frames."""
    start = perf_counter()
    config = config or VideoConfig()
    path = Path(path)
    try:
        if path.suffix.lower() not in CONTAINER_FORMATS:
            raise ValueError("Unsupported file extension. Supply MP4, MOV, AVI or MKV.")
        if not path.is_file() or not 0 < path.stat().st_size <= config.max_bytes:
            raise ValueError("Video is missing, empty or exceeds the upload limit.")
        with _open(path, config) as (container, stream):
            total = stream.frames
            if total:
                metadata, frames = _scan(container, stream, config, _indices(total, config.samples))
            else:
                metadata, _ = _scan(container, stream, config, set())
        if not total:
            # Count streams without a declared frame count before selecting indices.
            total = metadata.frame_count
            with _open(path, config) as (container, stream):
                metadata, frames = _scan(container, stream, config, _indices(total, config.samples))
        if metadata.frame_count != total:
            raise ValueError("Decoded frame count differs from the expected count.")
        return ProcessedVideo(metadata=metadata, frame_size=config.size, frames=frames,
                              processing_time_ms=(perf_counter() - start) * 1000)
    except (ValueError, OSError, av.FFmpegError, cv2.error) as exc:
        return VideoFailure(error=str(exc), processing_time_ms=(perf_counter() - start) * 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--size", type=int, default=224)
    args = parser.parse_args()
    try:
        config = VideoConfig(samples=args.samples, size=args.size)
    except ValueError as exc:
        parser.error(str(exc))
    result = process_video(args.video, config)
    print(result.model_dump_json(indent=2))
    return int(isinstance(result, VideoFailure))


if __name__ == "__main__":
    raise SystemExit(main())
