import asyncio
from io import BytesIO
from unittest.mock import Mock
from uuid import UUID, uuid4
import wave

import httpx
import pytest

from truthscan.api import analysis, results, uploads
from truthscan.api.main import app
from truthscan.fusion import engine

POST = "/api/v1/analyze"
LIST = "/api/v1/results"


def request(method, url, **kwargs):
    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(send())


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "DATA_DIR", tmp_path / "private")


@pytest.fixture
def mock_detector(monkeypatch):
    def detect(modality, path):
        assert path.parent.parent == results.DATA_DIR and path.stem == modality and path.is_file()
        payload = dict(model_name=engine.MODELS[modality], processing_time_ms=1, prediction="REAL")
        if modality == "audio":
            payload.update(raw_score=2.0, spoof_logit=-1.0)
        else:
            payload["detection_score"] = .2
        if modality == "video":
            payload["frames"] = []
        return Mock(**payload, **{"model_dump.return_value": payload})
    mock = Mock(side_effect=detect)
    monkeypatch.setattr(engine, "_detect", mock)
    return mock


def file_data(modality, ext, tmp_path):
    if modality == "image":
        image = pytest.importorskip("PIL.Image")
        buffer = BytesIO()
        image.new("RGB", (8, 8)).save(buffer, "PNG" if ext == "png" else "JPEG")
        return buffer.getvalue()
    if modality == "video":
        from test_video import make_clip
        path = tmp_path / ("input." + ext)
        make_clip(path, count=2)
        return path.read_bytes()
    if ext == "wav":
        buffer = BytesIO()
        with wave.open(buffer, "wb") as stream:
            stream.setparams((1, 2, 16000, 0, "NONE", ""))
            stream.writeframes(b"\x01\x00" * 400)
        return buffer.getvalue()
    from test_audio import make_audio
    return make_audio(tmp_path, ext, 1).read_bytes()


@pytest.mark.parametrize("name,ext", [
    ("image", "png"), ("image", "jpg"), ("image", "jpeg"), ("video", "avi"),
    ("video", "mp4"), ("video", "mov"), ("video", "mkv"), ("audio", "mp3"),
    ("audio", "wav"), ("audio", "flac"),
])
def test_upload_formats_and_retrieval(tmp_path, mock_detector, name, ext):
    data = file_data(name, ext, tmp_path)
    response = request("POST", POST, files={name: ("../../private." + ext, data, "application/octet-stream")})
    assert response.status_code == 201, response.text
    record = response.json()["data"]
    location = LIST + "/" + str(UUID(record["analysis_id"]))
    assert response.headers["location"] == location
    assert record["status"] == "completed" and record["processing_time_ms"] > 0
    report = record["report"]
    assert report["assessment"] == "REAL" and report["agreement"] == "single"
    assert report["findings"][name]["source"] == name + "." + ext
    assert "private" not in response.text and ".." not in response.text
    assert request("GET", location).json() == response.json()
    mock_detector.assert_called_once()
    assert not mock_detector.call_args.args[1].parent.exists()


def test_multimodal_and_recent_retention(tmp_path, mock_detector, monkeypatch):
    monkeypatch.setattr(results, "HISTORY_LIMIT", 2)
    files = {name: ("file." + ext, file_data(name, ext, tmp_path))
             for name, ext in [("image", "jpg"), ("video", "mov"), ("audio", "wav")]}
    records = [request("POST", POST, files=files).json()["data"] for _ in range(3)]
    assert records[0]["report"]["agreement"] == "agree"
    assert set(records[0]["report"]["findings"]) == set(files)
    assert not records[0]["report"]["not_supplied"]
    assert len({record["analysis_id"] for record in records}) == 3
    recent = request("GET", LIST).json()["data"]
    assert [r["analysis_id"] for r in recent] == [r["analysis_id"] for r in records[:0:-1]]
    assert "report" not in recent[0]
    assert recent[0]["assessment"] == records[-1]["report"]["assessment"]
    assert set(recent[0]["modalities"]) == set(files)
    assert request("GET", LIST + "?limit=1").json()["data"] == recent[:1]
    assert request("GET", LIST + "/" + records[0]["analysis_id"]).status_code == 404


@pytest.mark.parametrize("files,code", [
    ({"image": ("a.svg", b"<svg/>")}, 415),
    ({"image": ("a.jpg", b"not a JPEG")}, 415),
    ({"audio": ("a.wav", b"")}, 422),
    ({"other": ("a.jpg", b"junk")}, 422),
    ([("audio", ("a.wav", b"a")), ("audio", ("b.wav", b"b"))], 422),
])
def test_reject_bad_uploads(files, code, mock_detector):
    assert request("POST", POST, files=files).status_code == code
    mock_detector.assert_not_called()
    assert request("GET", LIST).json()["data"] == []
    assert not list(results.DATA_DIR.glob("upload-*"))


def test_oversize_and_truncated_streams(monkeypatch, mock_detector):
    monkeypatch.setitem(uploads.LIMITS, "image", 8)
    assert request("POST", POST, files={"image": ("x.jpg", b"x" * 9)}).status_code == 413
    headers = {"content-type": "multipart/form-data; boundary=a"}
    payload = b'--a\r\nContent-Disposition: form-data; name="audio"; filename="a.wav"\r\n\r\nx'
    assert request("POST", POST, content=payload, headers=headers).status_code == 400
    monkeypatch.setattr(uploads, "BODY_LIMIT", 16)
    assert request("POST", POST, content=payload, headers=headers).status_code == 413

    async def chunks():
        yield payload[:12]
        yield payload[12:]
    assert request("POST", POST, content=chunks(), headers=headers).status_code == 413
    mock_detector.assert_not_called()


def test_corrupted_image_uses_real_decoder():
    pytest.importorskip("clip")
    response = request("POST", POST, files={"image": ("broken.jpg", b"\xff\xd8\xffbroken")})
    assert response.status_code == 422
    record = response.json()["data"]
    assert record["status"] == "failed" and record["report"]["assessment"] == "INCONCLUSIVE"
    assert record["report"]["findings"]["image"]["result"]["error_code"] == "invalid_image"
    assert request("GET", response.headers["location"]).json() == response.json()


@pytest.mark.parametrize("error_code,expected", [("model_unavailable", 503), ("inference_failed", 500)])
def test_sanitize_detector_failure_and_keep_partial_evidence(monkeypatch, tmp_path, mock_detector,
                                                             error_code, expected):
    success = mock_detector.side_effect

    def detect(name, path):
        if name == "audio":
            return success(name, path)
        payload = dict(model_name=engine.MODELS[name], prediction=None, detection_score=None,
                       processing_time_ms=1, error_code=error_code, error=str(tmp_path / "secret"))
        return Mock(**payload, **{"model_dump.return_value": payload})
    mock_detector.side_effect = detect
    files = {"image": ("x.jpg", b"\xff\xd8\xffx")}
    for partial in [False, True]:
        if partial:
            files["audio"] = ("a.wav", file_data("audio", "wav", tmp_path))
        response = request("POST", POST, files=files)
        assert response.status_code == (201 if partial else expected)
        data = response.json()["data"]
        assert data["status"] == ("partial" if partial else "failed")
        assert data["report"]["assessment"] == "INCONCLUSIVE"
        assert data["report"]["findings"]["image"]["result"]["error_code"] == error_code
        assert "secret" not in response.text and "upload-" not in response.text
        assert request("GET", response.headers["location"]).json() == response.json()


def test_routes_validation_and_busy_slot():
    assert request("GET", LIST + "/" + str(uuid4())).status_code == 404
    assert request("GET", LIST + "/invalid").status_code == 422
    assert request("GET", LIST + "?limit=101").status_code == 422
    assert request("POST", POST, json={}).status_code == 415
    assert request("POST", POST, content=b"--x--\r\n",
                   headers={"content-type": "multipart/form-data; boundary=x"}).status_code == 422
    with analysis.analysis_slot:
        assert request("POST", POST).status_code == 429
        assert request("GET", "/health").json()["data"]["status"] == "ok"
    spec = request("GET", "/openapi.json").json()
    body = spec["paths"][POST]["post"]["requestBody"]
    assert set(body["content"]["multipart/form-data"]["schema"]["properties"]) == {"image", "video", "audio"}


def test_storage_failure_is_safe_and_cleans_up(monkeypatch, mock_detector):
    import sqlite3
    def fail_save(record):
        raise sqlite3.OperationalError("internal storage secret")
    monkeypatch.setattr(results, "save", fail_save)
    response = request("POST", POST, files={"image": ("x.jpg", b"\xff\xd8\xffx")})
    assert response.status_code == 503 and "secret" not in response.text
    assert not list(results.DATA_DIR.glob("upload-*"))
    assert request("GET", LIST).json()["data"] == []
