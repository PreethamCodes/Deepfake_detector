import pytest

# Phase 1 remains independently installable.
pytest.importorskip("torch")
pytest.importorskip("clip")
from PIL import Image

from truthscan.models.image.detector import D3Detector, Detection, Failure
from truthscan.models.image.weights import ASSETS, DEFAULT_DIR
from truthscan.processing import image as processing


@pytest.mark.parametrize("suffix,mode", [("jpg", "RGB"), ("jpeg", "L"), ("png", "RGBA")])
def test_preprocess(suffix, mode, tmp_path):
    path = tmp_path / f"input.{suffix}"
    Image.new(mode, (131, 83)).save(path)
    tensor = processing.preprocess(path)
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor[0, 0, 0, 0].item() == pytest.approx(-0.48145466 / 0.26862954)


@pytest.mark.parametrize("case", ["missing", "text", "gif", "truncated", "bytes", "pixels", "animation"])
def test_invalid_input_returns_no_score(case, tmp_path, monkeypatch):
    path = tmp_path / "input.png"
    if case == "text":
        path.write_bytes(b"not an image")
    elif case == "gif":
        Image.new("RGB", (32, 32)).save(path, format="GIF")
    elif case == "animation":
        Image.new("RGB", (32, 32)).save(path, save_all=True,
            append_images=[Image.new("RGB", (32, 32), "red")])
    elif case != "missing":
        Image.new("RGB", (80, 80)).save(path)
        if case == "truncated":
            path.write_bytes(path.read_bytes()[:45])
        elif case == "bytes":
            monkeypatch.setattr(processing, "MAX_BYTES", path.stat().st_size - 1)
        elif case == "pixels":
            monkeypatch.setattr(processing, "MAX_PIXELS", 6399)
    result = D3Detector(tmp_path).detect(path)
    assert isinstance(result, Failure)
    assert result.error_code == "invalid_image"
    assert result.error and result.detection_score is None and result.prediction is None


@pytest.mark.parametrize("bad_hash", [False, True])
def test_unavailable_checkpoint(tmp_path, bad_hash):
    path = tmp_path / "sample.png"
    Image.new("RGB", (32, 32)).save(path)
    if bad_hash:
        (tmp_path / "classifier.pth").write_bytes(b"wrong weights")
    result = D3Detector(tmp_path).detect(path)
    assert result.error_code == "model_unavailable"
    assert result.detection_score is None


@pytest.mark.skipif(not all((DEFAULT_DIR / name).exists() for name in ASSETS),
                    reason="Install the official D³ checkpoints for live inference")
def test_checkpoint_inference(tmp_path):
    detector = D3Detector()
    image = Image.linear_gradient("L").convert("RGB")
    for suffix in ("png", "jpg"):
        path = tmp_path / f"gradient.{suffix}"
        image.save(path)
        result = detector.detect(path)
        assert isinstance(result, Detection), result
        if suffix == "png":
            # Official visual encoder and attention head, separate forwards, seed 418.
            assert result.detection_score == pytest.approx(0.51807445, abs=1e-4)
        assert result.prediction == ("AI-GENERATED" if result.detection_score > 0.5 else "REAL")
        assert result.processing_time_ms > 0
    assert detector.detect(path).detection_score == pytest.approx(result.detection_score)
