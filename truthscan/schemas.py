from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

Payload = TypeVar("Payload")


class ApiResponse(BaseModel, Generic[Payload]):
    """Typed envelope for successful API responses."""

    data: Payload


class Health(BaseModel):
    status: Literal["ok"]
