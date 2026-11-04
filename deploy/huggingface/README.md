---
title: SHODHA AI
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: Multimodal deepfake detection API (D³, GenD, AASIST)
---

# SHODHA AI backend

**Uncovering the Truth Behind Digital Media.**

FastAPI service for multimodal deepfake detection and digital forensics on CPU. It runs D³ on images, GenD on faces in sampled video frames and AASIST on speech, then combines their labels into an explainable forensic report.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness |
| `POST /api/v1/analyze` | Multipart upload with fields `image`, `video` and/or `audio` |
| `GET /api/v1/results/{analysis_id}` | Stored report |
| `GET /api/v1/results?limit=20` | Recent report summaries |

Interactive documentation is at `/docs`.

## Configuration

Set this under **Settings → Variables and secrets** to let a separately hosted frontend call the API:

| Variable | Example |
| --- | --- |
| `SHODHA_ALLOWED_ORIGINS` | `https://shodha-ai.vercel.app` (comma-separated, exact origins) |

## Operating notes

- One analysis runs at a time. A second request during an analysis receives HTTP 429.
- The service has no login, and all visitors share one report history. Do not upload sensitive media.
- Storage on the free tier is not persistent. Report history resets when the Space restarts.
- Uploaded media is deleted after analysis. Only the sanitized report is stored.

## Models and licensing

Weights are downloaded and hash-verified from their official sources when the image is built. They are not redistributed in this repository.

- **D³** (Yang et al., CVPR 2025): the classifier release has no explicit licence. Research and evaluation use only; obtain permission from the authors before any other use. Uses OpenAI CLIP ViT-L/14 (MIT).
- **GenD** (Yermakov et al., WACV 2026): MIT-licensed reference implementation and CLIP-L/14 checkpoint. Face localisation uses OpenCV Zoo YuNet (MIT). See `docs/GenD-NOTICES.md`.
- **AASIST** (Jung et al., NAVER CLOVA): MIT licence; see `docs/AASIST-NOTICE.txt`.

## Responsible use

Scores are uncalibrated model outputs. GenD examines faces only and is unreliable on fully generated video. A label describes the examined media and does not establish whether a claim or event is true.
