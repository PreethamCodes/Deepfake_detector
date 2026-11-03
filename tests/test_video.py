from fractions import Fraction

import pytest

av = pytest.importorskip("av")
import numpy as np

from truthscan.processing import video


def make_clip(path, *, width=96, height=64, count=12, ticks=None, fragmented=False, rotation=0):
    options = {"movflags": "frag_keyframe+empty_moov"} if fragmented else {}
    with av.open(str(path), "w", options=options) as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height = width, height
        stream.pix_fmt = "yuv420p"
        if rotation:
            stream.set_display_rotation(rotation)
        for i in range(count):
            pixels = np.zeros((height, width, 3), dtype=np.uint8)
            pixels[:, :, 0] = 160 + i % 80
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = ticks[i] if ticks else i
            frame.time_base = Fraction(1, 10)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


@pytest.mark.parametrize("ext,width,height", [
    ("mp4", 160, 90), ("avi", 64, 96), ("mov", 80, 80), ("mkv", 128, 72),
])
def test_formats_metadata_and_pixels(tmp_path, ext, width, height):
    path = tmp_path / f"clip.{ext}"
    make_clip(path, width=width, height=height)
    result = video.process_video(path, video.VideoConfig(samples=3, size=64))
    assert isinstance(result, video.ProcessedVideo), result
    meta = result.metadata
    assert (meta.width, meta.height, meta.frame_count) == (width, height, 12)
    assert meta.fps == pytest.approx(10)
    assert meta.duration_seconds == pytest.approx(1.2)
    assert [f.index for f in result.frames] == [0, 6, 11]
    assert [f.timestamp_seconds for f in result.frames] == pytest.approx([0, .6, 1.1])
    for frame in result.frames:
        assert frame.rgb.shape == (64, 64, 3) and frame.rgb.dtype == np.uint8
        red, green, blue = frame.rgb[32, 32]
        assert red > 150 and green < 10 and blue < 10
        if width != height:
            assert not frame.rgb[0, 0].any()
    assert "rgb" not in result.model_dump()["frames"][0]


def test_variable_rate_timestamps_and_short_clip(tmp_path):
    path = tmp_path / "irregular.mov"
    make_clip(path, count=4, ticks=[0, 1, 5, 9])
    result = video.process_video(path)
    assert [f.index for f in result.frames] == list(range(4))
    assert [f.timestamp_seconds for f in result.frames] == pytest.approx([0, .1, .5, .9])


def test_undeclared_count_and_bounded_rgb_storage(tmp_path, monkeypatch):
    path = tmp_path / "stream.mp4"
    make_clip(path, count=240, fragmented=True)
    with av.open(str(path)) as container:
        assert container.streams.video[0].frames == 0
    prepared = []
    original = video._prepare

    def record(frame, size):
        prepared.append(frame.pts)
        return original(frame, size)

    monkeypatch.setattr(video, "_prepare", record)
    result = video.process_video(path, video.VideoConfig(samples=4, size=64))
    assert result.metadata.frame_count == 240
    assert [f.index for f in result.frames] == [0, 80, 159, 239]
    assert len(prepared) == 4
    assert sum(f.rgb.nbytes for f in result.frames) == 4 * 64 * 64 * 3


def test_one_sample_uses_middle_frame(tmp_path):
    path = tmp_path / "short.mp4"
    make_clip(path, count=3)
    assert video.process_video(path, video.VideoConfig(samples=1)).frames[0].index == 1


def test_phone_display_rotation(tmp_path):
    path = tmp_path / "phone.mov"
    make_clip(path, width=96, height=48, count=1, rotation=90)
    result = video.process_video(path, video.VideoConfig(size=64))
    assert result.metadata.width == 96
    pixels = result.frames[0].rgb
    assert pixels[0, 32, 0] > 150
    assert not pixels[32, 0].any()


@pytest.mark.parametrize("case", ["missing", "empty", "unsupported", "garbage", "truncated",
                                  "mismatch", "renamed_mkv", "audio"])
def test_invalid_uploads(tmp_path, case):
    path = tmp_path / "input.mov"
    if case == "empty":
        path.touch()
    elif case == "unsupported":
        make_clip(path)
        path = path.rename(path.with_suffix(".webm"))
    elif case == "garbage":
        path.write_bytes(b"garbage")
    elif case == "truncated":
        make_clip(path)
        path.write_bytes(path.read_bytes()[:path.stat().st_size // 2])
    elif case in {"mismatch", "renamed_mkv"}:
        make_clip(path)
        path = path.rename(path.with_suffix(".avi" if case == "mismatch" else ".mkv"))
    elif case == "audio":
        with av.open(str(path), "w") as container:
            stream = container.add_stream("pcm_s16le", rate=8000)
            frame = av.AudioFrame(format="s16", layout="mono", samples=800)
            frame.sample_rate = 8000
            for packet in stream.encode(frame):
                container.mux(packet)
    result = video.process_video(path)
    assert isinstance(result, video.VideoFailure) and result.error
    assert "frames" not in result.model_dump()


@pytest.mark.parametrize("limit", [{"max_bytes": 10}, {"max_pixels": 100}, {"max_frames": 2},
                                  {"max_seconds": .5}])
def test_resource_limits(tmp_path, limit):
    path = tmp_path / "input.mp4"
    make_clip(path)
    assert isinstance(video.process_video(path, video.VideoConfig(**limit)), video.VideoFailure)
