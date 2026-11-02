from fastapi import FastAPI

from truthscan.schemas import ApiResponse, Health

app = FastAPI(title="TRUTHSCAN", version="0.1.0")


@app.get("/health", response_model=ApiResponse[Health])
def health() -> ApiResponse[Health]:
    """Report API liveness independently of future detection engines."""
    return ApiResponse(data=Health(status="ok"))
