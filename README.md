# TRUTHSCAN

TRUTHSCAN is a Python platform for analyzing image, video, and audio evidence of synthetic media. Phase 1 provides an isolated environment, a FastAPI liveness endpoint, a shared response schema, and automated tests.

## Local setup

Install uv and run the following from the repository root. The project selects Python 3.11. uv can download the interpreter if needed. The lockfile records the runtime and development dependencies.

```powershell
uv sync --locked
uv run --locked python -m uvicorn truthscan.api.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, check the running service.

```powershell
curl.exe http://127.0.0.1:8000/health
```

A healthy API returns HTTP 200 with `{"data":{"status":"ok"}}`. This endpoint checks API liveness. Interactive API documentation is available at [localhost on port 8000](http://127.0.0.1:8000/docs). Stop the server with Ctrl+C.

## Tests

```powershell
uv run --locked python -m pytest -q
```

## Architecture

| Location | Responsibility |
| --- | --- |
| `truthscan/api/` | FastAPI entry point and HTTP routes |
| `truthscan/schemas.py` | Generic Pydantic success envelope and typed health payload |
| `truthscan/processing/` | Bounded image preprocessing and timestamped video frame sampling |
| `truthscan/models/{image,video,audio}/` | D³ image detection, GenD facial video detection, and a placeholder for audio |
| `truthscan/fusion/` | Future combination of modality-specific results |
| `truthscan/forensics/` | Future extraction of forensic indicators |
| `truthscan/reporting/` | Future explanations based on detector and forensic evidence |
| `truthscan/frontend/` | Future Streamlit client for the HTTP API |
| `tests/` | API contract and schema validation tests |
| `docs/` | Existing project planning documents |

The planned analysis flow runs from media preprocessing to independent detectors, then combines detector outputs with forensic evidence for reporting. The frontend will consume the FastAPI contract. Phase 1 runs on CPU and requires only the API and test stack.

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

Input type is determined from file contents. Single-frame JPEG and PNG inputs up to 20 MiB and 24 million pixels are decoded to RGB, resized to 224 × 224 with bilinear interpolation, and normalized with CLIP channel statistics. D³ encodes the original image and a 14 × 14 patch shuffle, then classifies their pre-projection CLS features. TRUTHSCAN uses a local shuffle seed of 418 per image for repeatability. Upstream validation advances the random generator across batches, so individual scores can differ. The release's decision rule labels scores strictly above 0.5 as AI-GENERATED. Scores have no established probability calibration for a particular upload.

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
