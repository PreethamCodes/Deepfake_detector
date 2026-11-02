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
| `truthscan/processing/` | Future media decoding and preprocessing |
| `truthscan/models/{image,video,audio}/` | Future D³ image, GenD video, and AASIST audio engines |
| `truthscan/fusion/` | Future combination of modality-specific results |
| `truthscan/forensics/` | Future extraction of forensic indicators |
| `truthscan/reporting/` | Future explanations based on detector and forensic evidence |
| `truthscan/frontend/` | Future Streamlit client for the HTTP API |
| `tests/` | API contract and schema validation tests |
| `docs/` | Existing project planning documents |

The planned analysis flow runs from media preprocessing to independent detectors, then combines detector outputs with forensic evidence for reporting. The frontend will consume the FastAPI contract. Phase 1 runs on CPU and requires only the API and test stack.
