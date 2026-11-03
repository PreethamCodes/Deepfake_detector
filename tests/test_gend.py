from unittest.mock import Mock

import pytest

pytest.importorskip("av")
from truthscan.models.video.detector import DetectionFailure, GenDDetector, VideoDetection
from truthscan.models.video.weights import ASSETS, DEFAULT_DIR
from test_video import make_clip


@pytest.fixture
def video_path(tmp_path):
    path = tmp_path / "input.mp4"
    make_clip(path, count=3)
    return path


@pytest.mark.parametrize("scores,label,average", [
    ([.1, None, .9], "REAL", .5),
    ([.4, .7, None], "AI-GENERATED", .55),
])
def test_frame_results_and_aggregation(video_path, monkeypatch, scores, label, average):
    scorer = Mock()
    scorer.score.side_effect = scores
    detector = GenDDetector()
    monkeypatch.setattr(detector, "_load", lambda: scorer)
    result = detector.detect(video_path)
    assert isinstance(result, VideoDetection)
    assert result.metadata.frame_count == 3
    assert [frame.index for frame in result.frames] == [0, 1, 2]
    assert [frame.timestamp_seconds for frame in result.frames] == pytest.approx([0, .1, .2])
    assert [frame.detection_score for frame in result.frames] == scores
    for frame in result.frames:
        if frame.detection_score is None:
            assert frame.status == "no_face" and frame.prediction is None
        else:
            assert frame.prediction == ("AI-GENERATED" if frame.detection_score > .5 else "REAL")
    assert result.prediction == label and result.detection_score == pytest.approx(average)


@pytest.mark.parametrize("case", ["missing", "corrupt"])
def test_invalid_video_never_loads_model(tmp_path, case, monkeypatch):
    path = tmp_path / "bad.mp4"
    if case == "corrupt":
        make_clip(path)
        path.write_bytes(path.read_bytes()[:100])
    detector = GenDDetector()
    monkeypatch.setattr(detector, "_load", lambda: pytest.fail("Unexpected model load"))
    result = detector.detect(path)
    assert result.error_code == "invalid_video" and result.detection_score is None


@pytest.mark.parametrize("case", ["missing_assets", "bad_checksum", "no_faces", "inference_failed"])
def test_failures_return_no_verdict(tmp_path, video_path, case, monkeypatch):
    detector = GenDDetector(tmp_path)
    if case == "bad_checksum":
        (tmp_path / "model.safetensors").write_bytes(b"wrong checkpoint")
    if case in {"no_faces", "inference_failed"}:
        scorer = Mock()
        scorer.score.side_effect = [None, None, None] if case == "no_faces" else RuntimeError("test failure")
        monkeypatch.setattr(detector, "_load", lambda: scorer)
    result = detector.detect(video_path)
    expected = "model_unavailable" if case in {"bad_checksum", "missing_assets"} else case
    assert isinstance(result, DetectionFailure) and result.error_code == expected
    assert result.prediction is None and result.detection_score is None
    if case == "no_faces":
        assert len(result.frames) == 3 and all(f.status == "no_face" for f in result.frames)


@pytest.mark.skipif(not all((DEFAULT_DIR / name).is_file() for name in ASSETS),
                    reason="Install verified GenD assets for live inference")
def test_live_checkpoint_matches_upstream_and_skips_faceless_video(video_path):
    pytest.importorskip("transformers")
    import torch
    from PIL import Image

    detector = GenDDetector()
    result = detector.detect(video_path)
    assert result.error_code == "no_faces", result
    scorer = detector._scorer
    gradient = Image.linear_gradient("L").convert("RGB")
    pixels = scorer.processor(images=gradient, return_tensors="pt").pixel_values
    with torch.inference_mode():
        score = scorer.model(pixels).softmax(-1)[0, 1].item()
    # Official GenD.forward with the same pinned weights and processor.
    assert score == pytest.approx(0.31527996, abs=1e-4)
