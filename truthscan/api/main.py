import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from truthscan.api.analysis import router
from truthscan.schemas import ApiResponse, Health

app = FastAPI(title="SHODHA AI", version="0.1.0",
              description="Multimodal deepfake detection and digital forensics API.")
app.include_router(router)


@app.exception_handler(sqlite3.Error)
@app.exception_handler(OSError)
async def storage_error(request: Request, exc: Exception):
    return JSONResponse({"detail": "Local storage is unavailable."}, status_code=503)


@app.get("/health", response_model=ApiResponse[Health])
def health() -> ApiResponse[Health]:
    """Report API liveness independently of model checkpoint availability."""
    return ApiResponse(data=Health(status="ok"))
