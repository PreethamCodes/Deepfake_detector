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


def test_cors_is_off_by_default_and_limited_to_configured_origins(monkeypatch):
    import importlib

    from truthscan.api import main

    async def get(target, origin):
        transport = httpx.ASGITransport(app=target)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health", headers={"Origin": origin})

    assert "access-control-allow-origin" not in asyncio.run(get(app, "https://app.example")).headers
    monkeypatch.setenv("SHODHA_ALLOWED_ORIGINS", "https://app.example/, https://other.example")
    try:
        configured = importlib.reload(main).app
        allowed = asyncio.run(get(configured, "https://app.example"))
        assert allowed.headers["access-control-allow-origin"] == "https://app.example"
        assert "location" in allowed.headers["access-control-expose-headers"].lower()
        denied = asyncio.run(get(configured, "https://evil.example"))
        assert "access-control-allow-origin" not in denied.headers
    finally:
        monkeypatch.delenv("SHODHA_ALLOWED_ORIGINS")
        importlib.reload(main)


def test_typed_response_rejects_invalid_health_status():
    with pytest.raises(ValidationError):
        ApiResponse[Health].model_validate({"data": {"status": "unknown"}})
