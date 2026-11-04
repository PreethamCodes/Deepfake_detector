"""Run the real browser flow against isolated local services and temporary report storage."""
import argparse
from contextlib import ExitStack, closing
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_url(url):
    for _ in range(150):
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.2)
    raise RuntimeError("Local service did not start")


def spawn(stack, args, cwd, env):
    proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    def stop():
        proc.terminate()
        proc.wait(timeout=20)
    stack.callback(stop)
    return proc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="Short clip with a detectable face and non-silent audio")
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as pw, ExitStack() as services:
        work = Path(temp)
        still, video, audio = (work / n for n in ("frame.jpg", "source.mp4", "speech.wav"))
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(args.video), "-map", "0:v:0",
                        "-frames:v", "1", str(still), "-map", "0:v:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-an", str(video), "-map", "0:a:0", "-c:a", "pcm_s16le", str(audio)], check=True)
        port = free_port()
        backend = f"http://127.0.0.1:{port}"
        env = dict(os.environ, SMOKE_DATA=str(work / "db"), TRUTHSCAN_BACKEND_URL=backend)
        python = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        service = spawn(services, [str(python), "-c",
                    "import os,sys,uvicorn; from pathlib import Path; from truthscan.api import results; "
                    "results.DATA_DIR=Path(os.environ['SMOKE_DATA']); "
                    "uvicorn.run('truthscan.api.main:app',host='127.0.0.1',port=int(sys.argv[1]))", str(port)], ROOT, env)
        wait_url(backend + "/health")
        webport = free_port()
        front = f"http://127.0.0.1:{webport}"
        spawn(services, ["node", "node_modules/vite/bin/vite.js", "--port", str(webport), "--strictPort"],
              ROOT / "frontend", env)
        wait_url(front)
        browser = pw.chromium.launch(channel="msedge" if sys.platform == "win32" else None)
        services.callback(browser.close)
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        def shot(name):
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(args.screenshots / (name + ".png")), full_page=True, animations="disabled")
        page.goto(front)
        expect(page.get_by_text("API online")).to_be_visible()
        expect(page.get_by_text("No investigations found", exact=False)).to_be_visible()
        page.get_by_role("link", name="New analysis").click()
        field = page.get_by_label("Evidence files")
        field.set_input_files({"name":"invalid.txt","mimeType":"text/plain","buffer":b"invalid"})
        expect(page.get_by_role("alert")).to_contain_text("Unsupported")
        expect(page.get_by_role("button", name="Run analysis")).to_be_disabled()
        page.reload()
        expect(page.get_by_role("heading", name="Media analysis")).to_be_visible()
        shot("media-analysis")
        multi_id = None
        for name, inputs in [("image",[still]), ("video",[video]), ("audio",[audio]), ("multimodal",[still,video,audio])]:
            page.goto(front + "/#/analyze")
            field.set_input_files(inputs)
            with page.expect_response(lambda r: r.url.endswith("/api/v1/analyze") and r.request.method=="POST",timeout=240000) as pending:
                page.get_by_role("button", name="Run analysis").click()
                expect(page.get_by_role("button", name="Analyzing…")).to_be_disabled()
            res = pending.value
            assert res.status == 201, res.text()
            record = res.json()["data"]
            assert record["status"] == "completed", record
            expect(page.get_by_role("heading",name="Forensic report")).to_be_visible()
            expect(page.locator(".assessment .badge")).to_have_text(record["report"]["assessment"])
            print(name, record["analysis_id"], record["report"]["assessment"], flush=True)
            if name == "multimodal":
                multi_id = record["analysis_id"]
                shot("analysis-results")
                page.get_by_role("link", name="Video forensics",exact=True).click()
                v = page.locator("video")
                page.wait_for_function("document.querySelector('video')?.readyState >= 1")
                flags = record["report"]["flagged_video_frames"]
                assert flags, "Test clip needs at least one flagged sample for seek verification"
                target = flags[0]
                page.get_by_role("button",name=f"Inspect {target['index']}",exact=True).click()
                assert abs(v.evaluate("v=>v.currentTime") - target["timestamp_seconds"]) < .1
                page.get_by_role("link",name="Audio forensics",exact=True).click()
                page.wait_for_function("document.querySelector('audio')?.readyState >= 1")
                shot("audio-forensics")
                page.goto(front + "/#/report/" + multi_id + "/video")
                page.reload()
                expect(page.get_by_text("Source media was removed",exact=False)).to_be_visible()
                shot("video-forensics")
                page.get_by_label("Choose local video").set_input_files(video)
                expect(page.locator("video")).to_be_visible()
        page.goto(front + "/#/history")
        expect(page.locator("tbody tr")).to_have_count(4)
        shot("history")
        page.get_by_label("Search by analysis ID").fill(multi_id)
        expect(page.locator("tbody tr")).to_have_count(1)
        page.get_by_role("link", name="Open report "+multi_id).click()
        expect(page.get_by_role("heading",name="Forensic report")).to_be_visible()
        page.goto(front + "/#/about")
        shot("about")
        page.goto(front + "/#/dashboard")
        expect(page.locator("tbody tr")).to_have_count(4)
        shot("dashboard")
        page.set_viewport_size({"width":390,"height":844})
        shot("mobile-dashboard")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("button",name="Open navigation").click()
        page.get_by_role("link",name="Media analysis",exact=True).click()
        expect(page.get_by_role("heading",name="Media analysis")).to_be_visible()
        shot("mobile-analysis")
        assert not errors, errors
        service.terminate()
        service.wait(timeout=20)
        page.get_by_role("button",name="Refresh workspace").click()
        expect(page.get_by_text("API offline",exact=True)).to_be_visible()
        expect(page.get_by_role("alert")).to_contain_text("Backend offline")
        print("PASS: upload, reports, playback, frame seeking, archive, invalid input, mobile, offline and browser console",flush=True)


if __name__ == "__main__":
    main()
