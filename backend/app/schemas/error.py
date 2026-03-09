"""Shared error response schemas for OpenAPI documentation."""

from typing import Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str = ""
    type: Optional[str] = None


class ErrorBody(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    request_id: str = Field(..., description="Unique request identifier for tracing")
    details: list[ErrorDetail] = Field(default_factory=list)
    category: Optional[str] = Field(None, description="Error category: user | external | system")


class ErrorResponse(BaseModel):
    error: ErrorBody
