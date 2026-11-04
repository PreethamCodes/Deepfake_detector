import json
import sys
from unittest.mock import Mock

import pytest

from truthscan.fusion import engine
from truthscan.fusion.__main__ import main


@pytest.fixture
def detectors(monkeypatch):
    pytest.importorskip("clip")
    pytest.importorskip("cv2")
    pytest.importorskip("av")
    from truthscan.models.audio.detector import AASISTDetector, Detection as Audio
    from truthscan.models.image.detector import D3Detector, Detection as Image
    from truthscan.models.video.detector import GenDDetector, VideoDetection

    image = Image(prediction="REAL", detection_score=.2, processing_time_ms=1)
    audio = Audio(prediction="REAL", raw_score=-2, spoof_logit=-4, processing_time_ms=2,
                  metadata=dict(format="wav", codec="pcm_s16le", sample_rate=16000,
                                channels=1, duration_seconds=8, analyzed_seconds=4.0375))
    video = VideoDetection(
        prediction="REAL", detection_score=.5, processing_time_ms=3,
        metadata=dict(width=320, height=240, frame_count=31, fps=10, duration_seconds=3.1),
        frames=[
            dict(index=0, timestamp_seconds=0, status="no_face", prediction=None, detection_score=None),
            dict(index=15, timestamp_seconds=1.5, status="scored", prediction="REAL", detection_score=.2),
            dict(index=30, timestamp_seconds=3, status="scored", prediction="AI-GENERATED", detection_score=.8),
        ],
    )
    mocks = {}
    for name, cls, result in [("image", D3Detector, image), ("audio", AASISTDetector, audio),
                              ("video", GenDDetector, video)]:
        mocks[name] = Mock(return_value=result)
        monkeypatch.setattr(cls, "detect", mocks[name])
    return mocks


@pytest.mark.parametrize("name", ["image", "video", "audio"])
def test_single_input_and_traceability(detectors, name):
    report = engine.analyze(**{name: "source file"})
    data = json.loads(report.model_dump_json())
    assert (data["assessment"], data["agreement"]) == ("REAL", "single")
    assert data["findings"] == {name: {"source": "source file",
                                      "result": detectors[name].return_value.model_dump(mode="json")}}
    assert set(data["not_supplied"]) == detectors.keys() - {name}
    detectors[name].assert_called_once_with("source file")
    for other in data["not_supplied"]:
        detectors[other].assert_not_called()
    assert engine.ForensicReport.model_validate(data) == report


def test_unanimous_including_mixed_video_frames(detectors):
    report = engine.analyze(image="x.jpg", video="y.mov", audio="z.flac")
    assert (report.assessment, report.agreement) == ("REAL", "agree")
    assert report.flagged_modalities == report.not_supplied == []
    frame, = report.flagged_video_frames
    original = report.findings["video"].result["frames"][2]
    assert frame.index == original["index"] == 30
    assert frame.timestamp_seconds == original["timestamp_seconds"] == 3
    assert report.findings["audio"].result["raw_score"] == -2


def test_conflict_even_against_a_majority(detectors):
    detectors["audio"].return_value = detectors["audio"].return_value.model_copy(
        update={"prediction": "AI-GENERATED", "raw_score": -20})
    report = engine.analyze(image="i", video="v", audio="a")
    assert (report.assessment, report.agreement) == ("INCONCLUSIVE", "conflict")
    assert report.flagged_modalities == ["audio"]
    assert "conflict" in report.reason
    detectors["image"].return_value = detectors["image"].return_value.model_copy(
        update={"prediction": "AI-GENERATED", "detection_score": .51})
    report = engine.analyze(image="i", audio="a")
    assert (report.assessment, report.agreement) == ("AI-GENERATED", "agree")
    assert report.flagged_modalities == ["image", "audio"]


def test_native_failure_preserves_partial_video_and_other_votes(detectors):
    from truthscan.models.video.detector import DetectionFailure
    video = detectors["video"].return_value
    failure = DetectionFailure(error_code="inference_failed", error="Stopped at next frame",
                               frames=video.frames, metadata=video.metadata, processing_time_ms=5)
    detectors["video"].return_value = failure
    report = engine.analyze(video="v", audio="a")
    assert (report.assessment, report.agreement) == ("INCONCLUSIVE", "single")
    assert "video" in report.reason
    assert report.findings["video"].result == failure.model_dump()
    assert report.findings["audio"].result["prediction"] == "REAL"
    assert report.flagged_video_frames[0].index == 30
    assert report.flagged_modalities == []


def test_missing_dependency_and_empty_case(monkeypatch):
    detector = Mock(side_effect=ImportError("missing dependency"))
    monkeypatch.setattr(engine, "_detect", detector)
    empty = engine.analyze()
    detector.assert_not_called()
    assert empty.assessment == "INCONCLUSIVE" and empty.agreement == "none"
    assert empty.not_supplied == ["image", "video", "audio"] and empty.findings == {}
    report = engine.analyze(audio="a")
    error = report.findings["audio"].result
    assert report.assessment == "INCONCLUSIVE" and report.agreement == "none"
    assert error["prediction"] is None and error["model_name"] == "AASIST"
    assert error["error_code"] == "detector_exception" and "missing dependency" in error["error"]


def test_agreement_cannot_mask_a_requested_failure(detectors):
    detectors["image"].side_effect = RuntimeError("image runtime failed")
    report = engine.analyze(image="i", video="v", audio="a")
    assert (report.assessment, report.agreement) == ("INCONCLUSIVE", "agree")
    assert "image" in report.reason and report.not_supplied == []
    assert report.findings["image"].result["error"] == "RuntimeError: image runtime failed"
    assert report.findings["video"].result["prediction"] == report.findings["audio"].result["prediction"] == "REAL"


def test_fuse_existing_results_without_rerunning(detectors):
    audio = detectors["audio"].return_value
    report = engine.fuse(audio=("speech.wav", audio))
    assert report.findings["audio"].result == audio.model_dump()
    detectors["audio"].assert_not_called()
    with pytest.raises(ValueError, match="Unexpected detector for video"):
        engine.fuse(video=("speech.wav", audio))


def test_cli_outputs_json_for_empty_case_and_success(detectors, monkeypatch, capsys):
    for args, code, label in [([], 1, "INCONCLUSIVE"), (["--audio", "clip.wav"], 0, "REAL")]:
        monkeypatch.setattr(sys, "argv", ["fusion", *args])
        assert main() == code
        assert json.loads(capsys.readouterr().out)["assessment"] == label
