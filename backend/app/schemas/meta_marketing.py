"""Pydantic schemas for Meta Marketing API endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MetaTokenStatus(BaseModel):
    """Token validation status response."""
    has_token: bool
    is_valid: bool = False
    scopes: list[str] = []
    has_required_scopes: bool = False
    missing_scopes: list[str] = []
    has_management: bool = False
    expires_at: Optional[int] = None
    days_remaining: Optional[int] = None
    is_expiring: bool = False
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    app_id: Optional[str] = None
    token_type: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


class MetaTokenHealthResponse(BaseModel):
    """Settings API contract for Meta token runtime health."""
    has_token: bool
    token_source: str = "missing"
    source_priority: list[str] = ["db", "env", "missing"]
    runtime_source: str = "missing"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    is_valid: bool = False
    app_id: Optional[str] = None
    type: Optional[str] = None
    expires_at: Optional[int] = None
    days_remaining: Optional[int] = None
    is_expiring: bool = False
    scopes: list[str] = []
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    last_validation_error: Optional[str] = None
    message: Optional[str] = None


class MetaTokenExchangeResponse(BaseModel):
    """Settings API contract for short-lived to long-lived token exchange."""
    status: str
    message: str
    token_type: Optional[str] = None
    token_source: str = "db"
    saved_to: str = "db"
    source_priority: list[str] = ["db", "env", "missing"]
    exchanged: bool = True
    expires_in_seconds: Optional[int] = None


class MetaAdAccountResponse(BaseModel):
    """Response for a single Meta ad account."""
    id: int
    user_id: int
    account_id: str
    account_name: Optional[str] = None
    business_name: Optional[str] = None
    currency: str = "JPY"
    timezone_name: str = "Asia/Tokyo"
    account_status: Optional[int] = None
    last_synced_at: Optional[datetime] = None
    sync_status: str = "pending"
    sync_error: Optional[str] = None
    amount_spent: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MetaAdAccountListResponse(BaseModel):
    """Response for list of connected accounts."""
    accounts: list[MetaAdAccountResponse]
    total: int


class MetaAvailableAccount(BaseModel):
    """An ad account available from Meta API (not yet connected)."""
    account_id: str
    name: Optional[str] = None
    business_name: Optional[str] = None
    currency: Optional[str] = None
    timezone_name: Optional[str] = None
    account_status: Optional[int] = None
    amount_spent: Optional[str] = None
    is_connected: bool = False


class MetaAvailableAccountsResponse(BaseModel):
    """Response for available accounts from Meta API."""
    accounts: list[MetaAvailableAccount]
    total: int


class MetaConnectAccountRequest(BaseModel):
    """Request to connect a Meta ad account."""
    account_id: str
    account_name: Optional[str] = None
    business_name: Optional[str] = None
    currency: str = "JPY"
    timezone_name: str = "Asia/Tokyo"
