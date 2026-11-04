# SHODHA AI

**Uncovering the Truth Behind Digital Media.**

SHODHA AI is a multimodal deepfake detection and digital-forensics platform. It analyzes images, sampled faces in video, and speech for signs of synthetic media. A local FastAPI service runs three pretrained detectors (D³, GenD and AASIST), combines their findings into a single explainable forensic report, and serves a React investigation workspace.

> The project was previously named TRUTHSCAN. The internal Python package (`truthscan`), API routes and the `TRUTHSCAN_BACKEND_URL` variable keep the original name for compatibility.

Media authenticity and factual truth are different questions. A detector label describes the examined media and does not establish whether a claim or event is true.

## Local setup

Install uv and run commands from the repository root. The project selects Python 3.11. For media uploads and inference, follow the [Phase 6 analysis API setup](#phase-6-analysis-api). For a lightweight health check with only the base dependencies, use the commands below.

```powershell
uv sync --locked
uv run --locked python -m uvicorn truthscan.api.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, check the running service.

```powershell
curl.exe http://127.0.0.1:8000/health
```

A healthy API returns HTTP 200 with `{"data":{"status":"ok"}}`. This endpoint checks API liveness. Interactive API documentation is available at [localhost on port 8000](http://127.0.0.1:8000/docs). Stop the server with Ctrl+C.

## Base tests

For the complete detector and API suite, use the all-extras test command in the Phase 6 section.

```powershell
uv run --locked python -m pytest -q
```

## Phase 6 analysis API

Run the following from the project root. The three weight setup commands are needed on first installation. The licensing and input requirements for each detector appear below.

```powershell
uv sync --locked --all-extras
uv run --locked --all-extras python -m truthscan.models.image.weights
uv run --locked --all-extras python -m truthscan.models.video.weights
uv run --locked --all-extras python -m truthscan.models.audio.weights
uv run --locked --all-extras python -m uvicorn truthscan.api.main:app --host 127.0.0.1 --port 8000
```

| Method and path | Behavior |
| --- | --- |
| `GET /health` | API liveness. Returns `{"data":{"status":"ok"}}` independently of checkpoint readiness. |
| `POST /api/v1/analyze` | Submit multipart files named `image`, `video`, or `audio`. Wait for the finished report. |
| `GET /api/v1/results/{analysis_id}` | Fetch the saved report. An unknown or expired UUID returns 404. |
| `GET /api/v1/results?limit=20` | Newest-first summaries including ID, status, creation time in UTC, and processing time. Limit is 1–100. |

Open [Swagger UI](http://127.0.0.1:8000/docs) for file pickers and response schemas or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) for the machine-readable contract. In a second PowerShell window, use real paths for the media you want to submit.

```powershell
$base = "http://127.0.0.1:8000"
$case = curl.exe -sS -F "image=@uploads/real photo 2.jpg" "$base/api/v1/analyze" | ConvertFrom-Json
$case.data.report
curl.exe "$base/api/v1/results/$($case.data.analysis_id)"
curl.exe "$base/api/v1/results?limit=5"
# Example for three related input files
curl.exe -F "image=@uploads/still.jpg" -F "video=@uploads/clip.mp4" -F "audio=@uploads/speech.wav" "$base/api/v1/analyze"
uv run --locked --all-extras python -m pytest -q tests/test_health.py tests/test_api.py
uv run --locked --all-extras python -m pytest -q
```

**Response contract.** A created analysis includes `data.analysis_id`, `created_at`, `status`, `processing_time_ms`, and `report`. The report has the same [evidence structure as the fusion CLI](docs/fusion-example.json). The API uses public source labels such as `video.mp4` and removes internal detector error messages. Processing time includes reading the request, validation, and CPU analysis. A saved result has a relative `Location` header on the POST response.

| POST outcome | HTTP result |
| --- | --- |
| All requested detectors return labels, even if labels conflict | 201, `completed` |
| Some detectors fail and others return labels | 201, `partial`, overall `INCONCLUSIVE`, individual errors preserved |
| All requested detectors fail after dispatch | Saved `failed` report, 422 for unusable media/no faces, 503 for unavailable weights, 500 for inference/runtime errors |
| Malformed multipart body, size limit, unsupported type/signature, or invalid selection | 400, 413, 415, or 422 with a `detail` message. No report is created. |
| Analysis slot occupied, or storage unavailable | 429 with `Retry-After`, or 503 with a `detail` message |

**Upload handling.** Supply one file per named modality. Images accept JPG/JPEG and PNG up to 20 MiB, video accepts MP4/AVI/MOV/MKV up to 256 MiB, and speech accepts WAV/MP3/FLAC up to 64 MiB. Incoming byte counts cap each file and the combined request (340 MiB plus 64 KiB for multipart framing), including chunked transfers. The API checks allowlisted extensions and common file signatures, then the existing processors decode the content and apply their own limits. A browser's MIME declaration alone is insufficient. Files use generated private case directories and server-chosen names, and are closed and deleted after processing. Only the sanitized report is saved in the Git-ignored SQLite database at `data/api/results.sqlite3`. The latest 100 reports survive a service restart.

**Operating scope.** Run one server worker on localhost for a single trusted user. The API has shared local history and no login. Each POST uses one CPU analysis slot and waits for completion. Large videos and cold model loads can take time. Supply speech separately to analyze a video's audio. A model prediction assesses the examined media and cannot establish factual truth.

## Phase 7 web workspace

The React workspace in `frontend/` talks to the FastAPI service through `/api` and `/health`. Vite forwards those paths to `TRUTHSCAN_BACKEND_URL` (default `http://127.0.0.1:8000`, see `frontend/.env.example`). Node.js 20 or later is required. Start the backend first using the Phase 6 commands, then in a second PowerShell window:

```powershell
cd frontend
npm ci
npm run dev
```

Open [localhost on port 5173](http://127.0.0.1:5173). `npm run build` type-checks and writes a production bundle to `frontend/dist/`, and `npm run preview` serves it with the same backend forwarding.

| Section | Contents |
| --- | --- |
| Dashboard | Stored analysis count, REAL / AI-GENERATED / INCONCLUSIVE counts from the archive, recent investigations |
| Media analysis | Drag-and-drop or browse for one image, video and/or audio file, previews, client-side type and size checks, processing state |
| Forensic report | Overall assessment, agreement, case status, each detector's label, original scores and processing time, failed modalities, scope note |
| Video forensics | Flagged frames, per-frame GenD score chart with the 0.5 decision line, frame ledger, seeking and still capture from the local video |
| Audio forensics | Playback, AASIST label, bona fide and spoof logits, decoded audio metadata |
| Investigation history | The latest 100 reports with search by ID and assessment filter |
| About | Problem, objective, detectors, architecture, limitations and responsible use |

Every figure shown comes from a backend response. The browser runs no inference. Source media is deleted after analysis, so playback on a reopened report asks you to select the original file locally.

The browser smoke test drives the real UI against an isolated backend and temporary database, and writes screenshots. It needs FFmpeg on `PATH`, Microsoft Edge and a short clip with a detectable face and an audio track:

```powershell
uv run --locked --all-extras --with playwright python frontend/tests/browser_smoke.py --video "uploads\real video.mp4" --screenshots docs/screenshots
```

## Run with Docker

Docker runs the whole stack without installing Python, uv, Node.js or the model weights yourself. You need Docker Desktop (or Docker Engine with Compose v2), about 12 GB of free disk space and internet access for the first build. From the repository root:

```powershell
docker compose up --build
```

Open the workspace at [localhost on port 8080](http://127.0.0.1:8080). The API and Swagger UI are also available at [localhost on port 8000](http://127.0.0.1:8000/docs). Stop the stack with Ctrl+C, or with `docker compose down` if it runs in the background (`docker compose up -d`).

| Service | Image | Role |
| --- | --- | --- |
| `backend` | Root `Dockerfile` | FastAPI with D³, GenD and AASIST on CPU. Downloads and hash-verifies the official weights at build time (about 2.2 GB) |
| `frontend` | `frontend/Dockerfile` | Production Vite build served by nginx, which forwards `/api` and `/health` to the backend so the browser stays same-origin |

The first build takes roughly 10–20 minutes, depending on bandwidth. Later builds reuse cached layers, and editing application code does not re-download the weights. Report history is kept in the `shodha-history` volume, so it survives restarts and rebuilds. `docker compose down -v` deletes it. Both ports bind to 127.0.0.1 only, matching the single-user, no-login design. To remove the images afterwards, run `docker compose down --rmi local -v`.

The same backend `Dockerfile` is used by the Hugging Face Space below.

## Deployment: Hugging Face Spaces (backend) and Vercel (frontend)

Vercel serves only the static React build. The backend needs a long-running process with about 3 GB of RAM and 2.2 GB of model weights, so it runs in a Hugging Face Docker Space. Local development needs none of this.

**1. Backend Space**

1. On huggingface.co, create a Space with SDK **Docker** (Blank), hardware **CPU basic** and visibility **Public**. Create a **Write** access token under Settings → Access Tokens.
2. Clone the empty Space next to this repository and copy the backend into it:

```powershell
git clone https://huggingface.co/spaces/<user>/shodha-ai ..\shodha-ai
powershell -ExecutionPolicy Bypass -File deploy\huggingface\prepare_space.ps1 -Destination ..\shodha-ai
cd ..\shodha-ai
git add .
git commit -m "Deploy SHODHA AI backend"
git push
```

Git asks for your Hugging Face username, with the token as the password. The script copies only `truthscan/`, the dependency files, the model notices, the root `Dockerfile` and the Space `README.md`. The image downloads and hash-verifies the official weights during the build, which takes about 10–20 minutes the first time. When the Space shows **Running**, check `https://<user>-shodha-ai.hf.space/health`.

**2. Frontend on Vercel**

1. Import this GitHub repository in Vercel and set **Root Directory** to `frontend`. Vercel detects Vite (`npm run build`, output `dist`). No rewrites are needed because the app uses hash routes.
2. Add the environment variable `VITE_API_BASE_URL` = `https://<user>-shodha-ai.hf.space`, then deploy.

**3. Connect them**

In the Space, go to Settings → Variables and secrets and add `SHODHA_ALLOWED_ORIGINS` = your Vercel URL, for example `https://shodha-ai.vercel.app`. List several origins separated by commas. The Space restarts with the new value. Without this variable the API sends no CORS headers, and browsers block calls from other origins.

**Operating notes.**
- Free Spaces sleep when idle, so open the Space before a demo.
- Free storage is not persistent, so report history resets on restart.
- The 2-vCPU tier is considerably slower than a multi-core laptop.
- The service has no login and all visitors share one history, so keep it public only while needed.
- The D³ classifier weights have no explicit licence. The Space downloads them from the official source and does not redistribute them.

## Architecture

| Location | Responsibility |
| --- | --- |
| `truthscan/api/` | FastAPI entry point and HTTP routes |
| `truthscan/schemas.py` | Generic Pydantic success envelope and typed health payload |
| `truthscan/processing/` | Bounded image preprocessing and timestamped video frame sampling |
| `truthscan/models/{image,video,audio}/` | D³ image, GenD facial video, and AASIST speech detection |
| `truthscan/fusion/` | Case-level decisions and JSON forensic reports from detector evidence |
| `truthscan/forensics/` | Future extraction of forensic indicators |
| `truthscan/reporting/` | Future explanations based on detector and forensic evidence |
| `frontend/` | React, TypeScript and Vite investigation workspace for the HTTP API |
| `tests/` | API contract and schema validation tests |
| `docs/` | Existing project planning documents |

The planned analysis flow runs from media preprocessing to independent detectors, then combines detector outputs with forensic evidence for reporting. The React workspace consumes the FastAPI contract. All inference runs on CPU.

## Phase 5 multimodal fusion and forensics

Pass one, two, or three related files in a single case. The caller chooses which files belong together. A video input runs GenD on sampled faces. Supply its speech separately with `--audio` to include AASIST. An image input runs D³ on that image.

```powershell
uv sync --locked --all-extras
uv run --locked --all-extras python -m truthscan.models.image.weights
uv run --locked --all-extras python -m truthscan.models.video.weights
uv run --locked --all-extras python -m truthscan.models.audio.weights
uv run --locked --all-extras python -m truthscan.fusion --image "uploads\real photo 2.jpg"
uv run --locked --all-extras python -m truthscan.fusion --image "uploads\still.jpg" --video "uploads\clip.mp4" --audio "uploads\speech.wav"
uv run --locked --all-extras python -m pytest -q tests/test_fusion.py
uv run --locked --all-extras python -m pytest -q
```

Substitute the actual filenames. The checkpoint commands are for initial setup. Each analysis runs only the requested detectors, sequentially on CPU. The CLI prints JSON and exits with 0 for a label, 1 for an inconclusive report, or 2 for invalid command syntax.

**Decision policy.** D³ scores whole images, GenD averages scores from sampled faces, and AASIST compares speech logits. These scores have different meanings and no shared probability calibration. Fusion therefore uses the detectors' final labels without averaging scores, assigning weights, or counting a majority.

| Evidence from the requested inputs | Overall assessment |
| --- | --- |
| One input and a successful prediction | That detector's label, marked `single` |
| Two or three successful predictions, all the same | The shared label, marked `agree` |
| Successful predictions contradict one another | `INCONCLUSIVE`, marked `conflict` |
| Any requested detector fails, or no inputs are supplied | `INCONCLUSIVE`; agreement still describes the available verdicts |

**Reading the evidence.** `findings` maps each requested modality to its supplied source path and the full native result, including scores, processing time, warnings, errors and available metadata. `not_supplied` lists omitted modalities. `flagged_modalities` lists detector-level AI-GENERATED verdicts. `flagged_video_frames` gives the original indices and source timestamps of individual GenD flags, including those in a video labeled REAL or a partially failed run. Look up the matching index in `findings.video.result.frames` for its score. An unscored frame supplies no vote. AASIST's `metadata.analyzed_seconds` is the duration examined from the start of the recording. Its label cannot locate a manipulation within that window. The overall label applies to the examined evidence and does not establish the factual truth of a scene or statement.

For a Python caller, `truthscan.fusion.engine.analyze(image=..., video=..., audio=...)` runs detection and returns a Pydantic `ForensicReport`. To reuse existing detector outputs, call `fuse(video=(source_path, video_result), audio=(source_path_for_audio, audio_result))` from the same module. Both support omitted inputs. Call `report.model_dump(mode="json")` for a JSON-compatible dictionary. No overall confidence score is calculated.

The [example forensic report](docs/fusion-example.json) records one local CPU run on a video, its first frame, and its separately extracted soundtrack. Source paths are shortened to filenames. D³ labeled the still REAL, while GenD and AASIST flagged their respective inputs. GenD scored five of eight frames and flagged two. The conflicting verdicts produced an INCONCLUSIVE assessment. This example illustrates the decision rule and supplies no accuracy estimate.

## Phase 2 image detection

Run these commands from the repository root. The optional image stack adds CPU PyTorch, torchvision, Pillow, and OpenAI CLIP. First-time setup requires Git, internet access, and room for the packages and both weight files (about 902 MiB combined).

```powershell
uv sync --locked --extra image
uv run --locked --extra image python -m truthscan.models.image.weights
uv run --locked --extra image python -m truthscan.models.image "C:\path\to\image.jpg"
uv run --locked --extra image python -m pytest -q
```

The setup command downloads the authors' attention head (`classifier.pth`) and OpenAI CLIP ViT-L/14 (`ViT-L-14.pt`) into the Git-ignored `checkpoints/d3/` directory. Both commands accept `--weights DIRECTORY`. For offline setup, copy both official files there. Their pinned URLs and SHA-256 hashes are in `truthscan/models/image/weights.py`. A hash mismatch is an error. Inference runs locally after setup. The live checkpoint test skips when weights are absent.

The CLI writes a JSON result and exits with status 0 for a prediction or 1 for a processing error. Successful results include the model name, prediction, sigmoid detection score, warning, and elapsed milliseconds. Errors carry a code and message and return null for the prediction and score. For repeated requests, reuse a detector in Python so that only the first valid image incurs model verification and loading time.

```python
from truthscan.models.image.detector import D3Detector

detector = D3Detector()
result = detector.detect("sample.png")
print(result.model_dump())
```

Input type is determined from file contents. Single-frame JPEG and PNG inputs up to 20 MiB and 24 million pixels are decoded to RGB, resized to 224 × 224 with bilinear interpolation, and normalized with CLIP channel statistics. D³ encodes the original image and a 14 × 14 patch shuffle, then classifies their pre-projection CLS features. SHODHA AI uses a local shuffle seed of 418 per image for repeatability. Upstream validation advances the random generator across batches, so individual scores can differ. The release's decision rule labels scores strictly above 0.5 as AI-GENERATED. Scores have no established probability calibration for a particular upload.

### Model attribution and usage terms

D³ is the work of Yongqi Yang, Zhihao Qian, Ye Zhu, Olga Russakovsky, and Yu Wu (CVPR 2025). The setup uses their published checkpoint at revision `14f21ad3797ef1e42f2f6090aa8ad4fabf07896c`. That release provides no explicit license for the classifier weights. They are downloaded separately for local evaluation. Obtain permission from the rights holders before redistributing them or using them commercially. [D³ paper](https://openaccess.thecvf.com/content/CVPR2025/html/Yang_D3_Scaling_Up_Deepfake_Detection_by_Learning_from_Discrepancy_CVPR_2025_paper.html) · [Official release](https://github.com/BigAandSmallq/D3/tree/14f21ad3797ef1e42f2f6090aa8ad4fabf07896c)

The frozen visual backbone and its Python implementation come from OpenAI CLIP. [OpenAI CLIP repository and MIT license](https://github.com/openai/CLIP/tree/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6)

**Checkpoint review.** The file under review is `ckpt/classifier.pth` in `BigAandSmallq/D3` at the revision above. Its commercial-use and redistribution permissions remain unresolved. CLIP's license applies separately. [Pinned classifier source](https://github.com/BigAandSmallq/D3/blob/14f21ad3797ef1e42f2f6090aa8ad4fabf07896c/ckpt/classifier.pth)

**PyTorch compatibility.** PyTorch 2.15 warns about `torch.jit.load` when opening the official CLIP TorchScript archive. `torch.export.load` expects an exported program saved in a different format. The detector retains the hash-verified TorchScript loader for this backbone. The warning can appear once during live inference and tests. The separate D³ classifier uses `torch.load(..., weights_only=True)`.

## Phase 3 video processing

The processor accepts local MP4, MOV, AVI and Matroska (`.mkv`) files, including files saved by an upload handler. PyAV uses its FFmpeg libraries to identify the container and decode the first video track other than cover art. OpenCV resizes selected frames on CPU. The Python wheels include the necessary native libraries on the tested Windows machine.

```powershell
uv sync --locked --extra image --extra video
uv run --locked --extra image --extra video python -m truthscan.processing.video "C:\path\to\video.mp4" --samples 4 --size 224
uv run --locked --extra image --extra video python -m pytest -q tests/test_video.py
uv run --locked --extra image --extra video python -m pytest -q
```

**Expected CLI behavior.** Success exits with code 0 and prints a JSON manifest with `status="processed"`, coded resolution, decoded frame count, presentation duration, average FPS, sample size, processing time, and a list of zero-based indices and source timestamps (seconds). Duration spans the first presentation timestamp to the end of the last frame. Average FPS is decoded frame count divided by that duration. A rejected file exits with code 1 and prints `status="error"` with a reason. Invalid command options exit with code 2. The command produces no media files or authenticity verdict.

A 5-second, 640 × 360, 12 FPS fixture has 60 frames. With four samples the manifest contains indices `[0, 20, 39, 59]` at roughly `[0.0, 1.667, 3.250, 4.917]` seconds. The processor spaces samples by presentation-order index, includes both endpoints for two or more samples, selects the middle frame for one sample, and returns every frame when a clip is shorter than the request. Variable-rate timestamps come from decoded frames and may be unevenly spaced.

```python
from truthscan.processing.video import ProcessedVideo, VideoConfig, process_video

result = process_video("sample.mov", VideoConfig(samples=4, size=224))
if isinstance(result, ProcessedVideo):
    for frame in result.frames:
        print(frame.index, frame.timestamp_seconds, frame.rgb.shape)
else:
    print(result.error)
```

Each sampled frame holds a contiguous RGB uint8 array with shape `(size, size, 3)`. Right-angle display rotation is applied before resizing. Black padding preserves the coded pixel proportions. Arrays stay in the Python result and are excluded from JSON. This leaves model-specific normalization to the future detector.

**Resource limits.** Defaults are 256 MiB per upload, 600 seconds, 36,000 frames, and 8,294,400 pixels per frame. Set limits with `VideoConfig`. Sampling defaults to eight frames at 224 pixels square and permits 1–64 samples at 32–512 pixels square. Decoding proceeds sequentially so corruption later in the stream can be detected. Only selected RGB arrays are retained. Streams without a declared frame count require a counting pass before sampling. Runtime depends on the full video's length, resolution, and codec.

**Expected test behavior.** The video tests create local fixtures and exercise decoding, failure results, variable timestamps, display rotation and bounded sample storage. The full suite also runs the API and image tests. Install both extras and the Phase 2 checkpoints to include live image inference. The documented PyTorch archive warning may appear.

## GenD video detection

Use the video **detector** to obtain predictions. The Phase 3 processing command above remains available for sampling alone. GenD analyzes facial manipulations in the visible frames. It has no audio input, temporal motion model, or established accuracy for general AI-generated scenery.

```powershell
uv sync --locked --extra image --extra video --extra gend
uv run --locked --extra image --extra video --extra gend python -m truthscan.models.video.weights
uv run --locked --extra image --extra video --extra gend python -m truthscan.models.video "uploads\real video.mp4" --samples 8
uv run --locked --extra image --extra video --extra gend python -m pytest -q
```

Setup downloads the official 1.22 GB GenD safetensors checkpoint (including the trained vision encoder and classifier), OpenAI's CLIP-L/14 vision and processor configurations, and the YuNet ONNX face localizer. GenD's checkpoint contains all learned parameters. A second CLIP backbone download is unnecessary. Both commands accept `--weights DIRECTORY`; the default is `checkpoints/gend/`. URLs, immutable revisions and SHA-256 hashes are recorded in `truthscan/models/video/weights.py`. After setup the detector verifies and reads only local assets. Dependencies on this CPU machine include Transformers 4.56.2 and safetensors 0.8.0 plus the existing video and CPU PyTorch stack.

By default, the detector asks the Phase 3 processor for eight 512-pixel-square RGB frames. OpenCV YuNet locates faces and five landmarks. The largest detected face in each sample is aligned to 224 × 224 with GenD's 1.3 context scale, then passed through the CLIP image processor. YuNet replaces upstream RetinaFace for CPU localization only. The classifier uses GenD's trained CLIP vision features, L2 normalization, two-class head and softmax column 1. Small faces, profiles, multiple people and short manipulations between sample points can limit coverage. Increase `--samples` for denser sampling at greater CPU cost.

**Output.** Each sampled frame retains its index and source timestamp. Scored frames have a prediction and score. Frames without a detected face have `status="no_face"` and null values. The video score is the arithmetic mean over scored frames, each weighted equally. A score strictly above 0.5 yields `AI-GENERATED`; all other finite scores yield `REAL`. Scores are uncalibrated. A video can contain real and manipulated segments or receive an incorrect prediction.

The CLI emits JSON with model name, source metadata, total wall time in milliseconds, frame results and the video result. Successful inference exits with code 0. An invalid video, unavailable checkpoint, inference failure, or no detected face exits with code 1 and a specific error code. A partial inference failure never produces a video score. The frame list on such a failure contains only the completed samples. Reuse a detector to avoid repeated model loading:

```python
from truthscan.models.video.detector import GenDDetector

detector = GenDDetector()
result = detector.detect("sample.mkv")
print(result.model_dump_json(indent=2))
```

**Attribution.** GenD is by Andrii Yermakov, Jan Cech, Jiri Matas, and Mario Fritz (WACV 2026). The authors' model card identifies the CLIP-L/14 checkpoint as MIT licensed. The pinned model revision is `891ce014a0308386c4d7d25b3dcf436a22db5504`. The adapter follows their MIT-licensed inference implementation. [Official checkpoint](https://huggingface.co/yermandy/GenD_CLIP_L_14/tree/891ce014a0308386c4d7d25b3dcf436a22db5504) · [Reference implementation](https://github.com/yermandy/GenD/tree/387a42266dd385fbe8f7626c5d3aa03eea3bfaab) · [Paper](https://openaccess.thecvf.com/content/WACV2026/papers/Yermakov_Deepfake_Detection_that_Generalizes_Across_Benchmarks_WACV_2026_paper.pdf)

The vision configuration is from OpenAI CLIP. YuNet is distributed by OpenCV Zoo under the MIT license. The GenD and YuNet copyright notices are included locally. [CLIP configuration](https://huggingface.co/openai/clip-vit-large-patch14/tree/32bd64288804d66eefd0ccbe215aa642df71cc41) · [YuNet source and license](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet) · [Notices](docs/GenD-NOTICES.md)

## Phase 4 audio detection

AASIST accepts standalone speech recordings in WAV, MP3 or FLAC. Install the audio extra, download the hash-verified official AASIST checkpoint, and run the detector from the project root. Use all extras to keep image and video dependencies installed in the same environment.

```powershell
uv sync --locked --all-extras
uv run --locked --all-extras python -m truthscan.models.audio.weights
uv run --locked --all-extras python -m truthscan.models.audio "uploads\speech.wav"
uv run --locked --all-extras python -m pytest -q tests/test_audio.py
uv run --locked --all-extras python -m pytest -q
```

For audio alone, substitute `--extra audio` for `--all-extras`. The audio extra uses PyAV/FFmpeg, NumPy and CPU PyTorch. Both audio commands accept `--weights DIRECTORY` (default `checkpoints/aasist/`). After initial setup, inference runs offline. Set up D³ and GenD weights as described above to include their live tests. Reuse a single `AASISTDetector` from `truthscan.models.audio.detector` for repeated calls to `.detect(path)`.

**Input and scope.** The processor checks the container, decodes the first audio stream, resamples to 16 kHz floating-point PCM and averages the channels. It scans the stream through the end for decode errors and duration limits, retaining only the first 64,600 samples (4.0375 seconds). Short utterances repeat to fill this window, following upstream evaluation. A change later in the recording can be missed. Metadata gives source rate, channels, codec, decoded duration and the amount of original audio analyzed before repeat-padding. Defaults are 64 MiB, five minutes, 1–8 channels and source rates of 1–192 kHz. A silent analysis window returns an error. Supply speech; there is no speech/music classifier.

**Output.** The CLI returns JSON with prediction, raw score, spoof logit, model name, elapsed time in milliseconds and metadata. The official evaluation score (`raw_score`) is the bona fide class logit, which can be negative or positive. SHODHA AI predicts REAL if that logit exceeds the spoof logit and AI-GENERATED otherwise. Neither number is a calibrated probability. Invalid input, model loading or inference errors produce a specific error code, null prediction and null raw score, and exit status 1. Success exits with status 0.

**Attribution.** SHODHA AI uses the full pretrained AASIST by Jee-weon Jung and colleagues, including the reference architecture, evaluation configuration and weights from NAVER's CLOVA repository at commit `a04c9863f63d44471dde8a6abcb3b082b07cd1d1`. The model was trained for ASVspoof 2019 logical-access speech spoofing. The repository has an MIT license requiring preservation of its notice. The checkpoint is distributed in that repository without a separate checkpoint-specific license identified. The upstream NOTICE also lists third-party terms, including CC BY-NC-SA 4.0 for the min t-DCF evaluation code, which this adapter does not use. [Official checkpoint](https://github.com/clovaai/aasist/blob/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/models/weights/AASIST.pth) · [Official license](https://github.com/clovaai/aasist/blob/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/LICENSE) · [Notices](docs/AASIST-NOTICE.txt)
