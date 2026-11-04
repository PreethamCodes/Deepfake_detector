"""Upload, analysis and result retrieval routes for the local CPU service."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from truthscan.api import results
from truthscan.api.results import Analysis, HistoryEntry
from truthscan.api.uploads import EXTENSIONS, read_uploads, save_uploads
from truthscan.fusion.engine import analyze
from truthscan.schemas import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["Analysis"])
analysis_slot = Lock()
PUBLIC_ERRORS = {
    "invalid_image": "Image is damaged or outside the supported image limits.",
    "invalid_video": "Video is damaged or outside the supported video limits.",
    "invalid_audio": "Audio is damaged or outside the supported speech input limits.",
    "no_faces": "No face was detected in the sampled frames.",
    "model_unavailable": "The requested model could not be loaded.",
    "detector_exception": "The detector could not run.",
    "inference_failed": "The detector could not complete inference.",
}


def process(form: FormData, start: float) -> tuple[Analysis, int]:
    results.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=results.DATA_DIR, prefix="upload-") as directory:
        paths = save_uploads(form, Path(directory))
        report = analyze(**paths)
    errors = []
    for modality, finding in report.findings.items():
        finding.source = paths[modality].name
        code = finding.result.get("error_code")
        if code:
            errors.append(code)
            finding.result["error"] = PUBLIC_ERRORS.get(code, "Analysis failed.")

    status, http_status = "completed", 201
    if errors:
        status = "partial"
        if len(errors) == len(report.findings):
            status = "failed"
            if "inference_failed" in errors or "detector_exception" in errors:
                http_status = 500
            elif "model_unavailable" in errors:
                http_status = 503
            else:
                http_status = 422
    analysis = Analysis(analysis_id=uuid4(), created_at=datetime.now(timezone.utc), status=status,
                        processing_time_ms=(perf_counter() - start) * 1000, report=report)
    results.save(analysis)
    return analysis, http_status


UPLOAD_SCHEMA = {"type": "object", "minProperties": 1, "additionalProperties": False,
                 "properties": {name: {"type": "string", "format": "binary",
                                       "description": ", ".join(sorted(extensions))}
                                for name, extensions in EXTENSIONS.items()}}


class ErrorResponse(BaseModel):
    detail: str


@router.post("/analyze", status_code=201, response_model=ApiResponse[Analysis],
             openapi_extra={"requestBody": {"required": True, "content": {
                 "multipart/form-data": {"schema": UPLOAD_SCHEMA}}}},
             responses={400: {"model": ErrorResponse, "description": "Malformed multipart request"},
                        413: {"model": ErrorResponse, "description": "Upload too large"},
                        415: {"model": ErrorResponse, "description": "Unsupported media"},
                        422: {"model": ApiResponse[Analysis] | ErrorResponse,
                              "description": "Invalid input or no analyzable evidence"},
                        429: {"model": ErrorResponse, "description": "Analysis slot busy"},
                        500: {"model": ApiResponse[Analysis], "description": "Detector failed"},
                        503: {"model": ApiResponse[Analysis] | ErrorResponse,
                              "description": "Model or storage unavailable"}})
async def submit(request: Request, response: Response) -> ApiResponse[Analysis]:
    """Analyze up to one image, video and audio file together; wait for the forensic report."""
    if not analysis_slot.acquire(blocking=False):
        raise HTTPException(429, "Another analysis is running. Retry later.", headers={"Retry-After": "5"})
    try:
        start = perf_counter()
        form = await read_uploads(request)
        try:
            analysis, response.status_code = await run_in_threadpool(process, form, start)
        finally:
            await form.close()
    finally:
        analysis_slot.release()
    response.headers["Location"] = f"/api/v1/results/{analysis.analysis_id}"
    return ApiResponse(data=analysis)


@router.get("/results/{analysis_id}")
def result(analysis_id: UUID) -> ApiResponse[Analysis]:
    """Retrieve a saved report, including any partial findings or detector errors."""
    analysis = results.get(analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found.")
    return ApiResponse(data=analysis)


@router.get("/results")
def recent(limit: int = Query(20, ge=1, le=results.HISTORY_LIMIT)) -> ApiResponse[list[HistoryEntry]]:
    """List recent analyses, newest first."""
    return ApiResponse(data=results.recent(limit))
