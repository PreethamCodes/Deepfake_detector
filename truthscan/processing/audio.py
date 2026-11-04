"""Bounded decoding for the AASIST utterance-level evaluation protocol."""
from pathlib import Path

import av
import numpy as np
from pydantic import BaseModel

from truthscan.processing.limits import AUDIO_BYTES as MAX_BYTES

RATE = 16_000
WINDOW = 64_600
MAX_SECONDS = 300
FORMATS = {".wav": "wav", ".mp3": "mp3", ".flac": "flac"}


class AudioMetadata(BaseModel):
    format: str
    codec: str
    sample_rate: int
    channels: int
    duration_seconds: float
    analyzed_seconds: float


def preprocess(path: Path) -> tuple[np.ndarray, AudioMetadata]:
    expected = FORMATS.get(path.suffix.lower())
    if expected is None:
        raise ValueError("Supply a WAV, MP3 or FLAC audio file.")
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("File is missing, empty or exceeds 64 MiB.")
    if expected == "wav":
        # FFmpeg can salvage a partial RIFF as a shorter, apparently valid clip.
        with path.open("rb") as handle:
            header = handle.read(8)
        declared = int.from_bytes(header[4:], "little")
        if header[:4] == b"RIFF" and declared != 0xFFFFFFFF and declared + 8 > path.stat().st_size:
            raise ValueError("Truncated WAV container.")
    with av.open(str(path.resolve()), options={"format_whitelist": "wav,mp3,flac"}) as source:
        if source.format.name != expected or not source.streams.audio:
            raise ValueError("Audio container does not match its filename.")
        stream = source.streams.audio[0]
        codec = stream.codec_context
        channels, rate = codec.channels, codec.sample_rate
        if not (1 <= channels <= 8 and 1000 <= rate <= 192000):
            raise ValueError("Unsupported channel count or sample rate.")
        if stream.duration and stream.duration * stream.time_base > MAX_SECONDS:
            raise ValueError("Audio exceeds the five-minute limit.")
        codec.options = {"err_detect": "explode"}
        resampler = av.AudioResampler(format="fltp", layout=codec.layout, rate=RATE)
        waveform = np.empty(WINDOW, dtype=np.float32)
        used = total = 0

        def consume(frames):
            nonlocal used
            for frame in frames:
                samples = frame.to_ndarray()
                if not np.isfinite(samples).all():
                    raise ValueError("Non-finite audio samples.")
                n = min(WINDOW - used, frame.samples)
                waveform[used:used+n] = samples[:, :n].mean(axis=0)
                used += n

        for packet in source.demux(stream):
            if packet.is_corrupt:
                raise ValueError("Corrupted audio packet.")
            for frame in packet.decode():
                if frame.is_corrupt or frame.sample_rate != rate or len(frame.layout.channels) != channels:
                    raise ValueError("Corrupted or changing audio stream.")
                total += frame.samples
                if total > rate * MAX_SECONDS:
                    raise ValueError("Audio exceeds the five-minute limit.")
                consume(resampler.resample(frame))
        if total:
            consume(resampler.resample(None))
        if expected == "flac" and stream.duration and total != stream.duration * stream.time_base * rate:
            raise ValueError("Incomplete FLAC stream.")
        if not used or not np.any(waveform[:used]):
            raise ValueError("No non-silent audio in the analysis window.")
        if used < WINDOW:
            waveform = np.resize(waveform[:used], WINDOW)
        return waveform, AudioMetadata(format=expected, codec=codec.name, channels=channels,
                                      sample_rate=rate, duration_seconds=total / rate,
                                      analyzed_seconds=used / RATE)
