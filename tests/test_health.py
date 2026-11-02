import asyncio

import httpx
import pytest
from pydantic import ValidationError

from truthscan.api.main import app
from truthscan.schemas import ApiResponse, Health


def test_health_contract():
    async def request_health():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"data": {"status": "ok"}}


def test_typed_response_rejects_invalid_health_status():
    with pytest.raises(ValidationError):
        ApiResponse[Health].model_validate({"data": {"status": "unknown"}})
