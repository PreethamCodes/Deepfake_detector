import wave

import pytest

av = pytest.importorskip("av")
torch = pytest.importorskip("torch")
import numpy as np

from truthscan.models.audio.detector import AASISTDetector, Detection, Failure
from truthscan.models.audio.weights import DEFAULT_DIR, NAME
from truthscan.processing import audio


def write_wav(path, channels=1, rate=16000, seconds=.25):
    samples = (np.sin(2 * np.pi * 220 * np.arange(int(rate * seconds)) / rate) * 8192).astype("<i2")
    if channels == 2:
        samples = np.column_stack((samples, np.zeros_like(samples)))
    with wave.open(str(path), "wb") as stream:
        stream.setparams((channels, 2, rate, 0, "NONE", ""))
        stream.writeframes(samples.tobytes())


def make_audio(tmp_path, fmt, channels):
    original = tmp_path / "input.wav"
    write_wav(original, channels, rate=44100)
    if fmt == "wav":
        return original
    path = tmp_path / f"encoded.{fmt}"
    with av.open(str(original)) as source, av.open(str(path), "w") as target:
        stream = target.add_stream("libmp3lame" if fmt == "mp3" else "flac", rate=44100)
        stream.layout = "stereo" if channels == 2 else "mono"
        for frame in source.decode(audio=0):
            for packet in stream.encode(frame):
                target.mux(packet)
        for packet in stream.encode():
            target.mux(packet)
    return path


@pytest.mark.parametrize("fmt,channels", [("wav", 1), ("wav", 2), ("mp3", 2), ("flac", 1)])
def test_decode_and_repeat(tmp_path, fmt, channels):
    path = make_audio(tmp_path, fmt, channels)
    samples, metadata = audio.preprocess(path)
    assert metadata.format == fmt and metadata.channels == channels and metadata.sample_rate == 44100
    assert metadata.duration_seconds == pytest.approx(.25, abs=.001)
    assert samples.dtype == np.float32 and samples.shape == (64600,)
    period = round(metadata.analyzed_seconds * audio.RATE)
    np.testing.assert_array_equal(samples[:period], samples[period:2*period])
    if fmt == "wav":
        assert samples.max() == pytest.approx(.25 / channels, abs=.002)


@pytest.fixture(scope="module")
def detector():
    if not (DEFAULT_DIR / NAME).exists():
        pytest.skip("Install the official AASIST checkpoint for live inference")
    return AASISTDetector()


@pytest.mark.parametrize("fmt,channels", [("wav", 1), ("flac", 2), ("mp3", 1)])
def test_live_cpu_inference(detector, tmp_path, fmt, channels):
    result = detector.detect(make_audio(tmp_path, fmt, channels))
    assert isinstance(result, Detection), result
    assert result.prediction == ("REAL" if result.raw_score > result.spoof_logit else "AI-GENERATED")
    assert result.metadata.channels == channels and result.processing_time_ms > 0
    assert next(detector._model.parameters()).device.type == "cpu"


def test_reference_logits(detector, tmp_path):
    path = tmp_path / "tone.wav"
    write_wav(path)
    result = detector.detect(path)
    # Official CPU model, native 16 kHz PCM, upstream repeat-padding.
    assert result.spoof_logit == pytest.approx(4.569144, abs=1e-4)
    assert result.raw_score == pytest.approx(-5.288917, abs=1e-4)


def test_long_clip_uses_reference_prefix(tmp_path):
    path = tmp_path / "long.wav"
    write_wav(path, seconds=6)
    samples, metadata = audio.preprocess(path)
    with wave.open(str(path), "rb") as stream:
        reference = np.frombuffer(stream.readframes(64600), dtype="<i2") / 32768
    np.testing.assert_array_equal(samples, reference)
    assert metadata.duration_seconds == 6 and metadata.analyzed_seconds == 4.0375


def test_inference_failure_keeps_metadata(tmp_path):
    path = tmp_path / "valid.wav"
    write_wav(path)
    detector = AASISTDetector()

    def fail(_):
        raise RuntimeError("test model failure")

    detector._model = fail
    result = detector.detect(path)
    assert result.error_code == "inference_failed" and result.raw_score is None
    assert result.metadata.sample_rate == 16000


@pytest.mark.parametrize("case", ["missing", "empty", "corrupt", "truncated", "unsupported",
                                  "mismatch", "oversize", "duration", "silent"])
def test_invalid_input(tmp_path, case, monkeypatch):
    path = tmp_path / "input.wav"
    if case == "empty":
        path.touch()
    elif case == "corrupt":
        path.write_bytes(b"not audio")
    elif case != "missing":
        write_wav(path)
        if case == "truncated":
            path.write_bytes(path.read_bytes()[:-100])
        elif case in {"mismatch", "unsupported"}:
            path = path.rename(path.with_suffix(".mp3" if case == "mismatch" else ".ogg"))
        elif case == "oversize":
            monkeypatch.setattr(audio, "MAX_BYTES", 100)
        elif case == "silent":
            with wave.open(str(path), "wb") as out:
                out.setparams((1, 2, 16000, 0, "NONE", ""))
                out.writeframes(bytes(32000))
        else:
            monkeypatch.setattr(audio, "MAX_SECONDS", .1)
    result = AASISTDetector(tmp_path).detect(path)
    assert isinstance(result, Failure) and result.error_code == "invalid_audio"
    assert result.prediction is None and result.raw_score is None


@pytest.mark.parametrize("bad_hash", [False, True])
def test_model_unavailable(tmp_path, bad_hash):
    path = tmp_path / "valid.wav"
    write_wav(path)
    if bad_hash:
        (tmp_path / NAME).write_bytes(b"wrong model")
    result = AASISTDetector(tmp_path).detect(path)
    assert result.error_code == "model_unavailable" and result.raw_score is None
