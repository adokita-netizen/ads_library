"""Meta Marketing API endpoints — account connection, token management, and ad operations."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.core.database import get_async_session
from app.models.meta_ad_account import MetaAdAccount
from app.models.user import User
from app.schemas.meta_marketing import (
    MetaAdAccountListResponse,
    MetaAdAccountResponse,
    MetaAvailableAccount,
    MetaAvailableAccountsResponse,
    MetaConnectAccountRequest,
    MetaTokenStatus,
)
from app.schemas.meta_campaign_management import (
    CreateAdRequest,
    CreateAdSetRequest,
    CreateCampaignRequest,
    CreateCreativeRequest,
    MetaOperationResponse,
    UpdateCampaignStatusRequest,
)
from app.services.meta_marketing.client import (
    AuthenticationError,
    MetaMarketingAPIError,
    MetaMarketingClient,
    PermissionError as MetaPermissionError,
)
from app.services.meta_marketing.token_manager import MetaTokenManager

router = APIRouter(prefix="/meta-marketing", tags=["meta-marketing"])
logger = structlog.get_logger()


# ── Token Status ─────────────────────────────────────────────────

@router.get("/token-status", response_model=MetaTokenStatus)
async def get_token_status(
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Check the current Meta access token status, scopes, and expiry."""
    token = await MetaTokenManager.get_access_token(db)

    if not token:
        return MetaTokenStatus(has_token=False, error="アクセストークンが設定されていません")

    validation = await MetaTokenManager.validate_token(db, token)

    if not validation.get("is_valid"):
        return MetaTokenStatus(
            has_token=True,
            is_valid=False,
            error=validation.get("error", "トークンが無効です"),
        )

    scopes = validation.get("scopes", [])
    scope_check = MetaTokenManager.check_required_scopes(scopes, require_management=True)

    return MetaTokenStatus(
        has_token=True,
        is_valid=True,
        scopes=scopes,
        has_required_scopes=scope_check["has_required"],
        missing_scopes=scope_check["missing_scopes"],
        has_management=scope_check["has_management"],
        expires_at=validation.get("expires_at"),
        days_remaining=validation.get("days_remaining"),
        is_expiring=validation.get("is_expiring", False),
        user_id=validation.get("user_id"),
        user_name=validation.get("user_name"),
        app_id=validation.get("app_id"),
        token_type=validation.get("type"),
        note=validation.get("note"),
    )


# ── Available Accounts (from Meta API) ───────────────────────────

@router.get("/available-accounts", response_model=MetaAvailableAccountsResponse)
async def get_available_accounts(
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Fetch all ad accounts accessible by the current token from Meta API."""
    token = await MetaTokenManager.get_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="Metaアクセストークンが設定されていません")

    # Get already connected account IDs
    result = await db.execute(
        select(MetaAdAccount.account_id).where(MetaAdAccount.is_active == True)
    )
    connected_ids = set(row[0] for row in result.all())

    client = MetaMarketingClient(token)
    try:
        raw_accounts = await client.get_ad_accounts()
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Metaトークンが無効または期限切れです。トークンを再設定してください。")
    except MetaPermissionError as e:
        raise HTTPException(status_code=403, detail=f"権限が不足しています: {e}")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"Meta APIエラー: {e}")
    finally:
        await client.close()

    accounts = []
    for raw in raw_accounts:
        # Meta returns account_id prefixed with "act_"
        acct_id = raw.get("account_id", raw.get("id", "").replace("act_", ""))
        accounts.append(MetaAvailableAccount(
            account_id=acct_id,
            name=raw.get("name"),
            business_name=raw.get("business_name"),
            currency=raw.get("currency"),
            timezone_name=raw.get("timezone_name"),
            account_status=raw.get("account_status"),
            amount_spent=raw.get("amount_spent"),
            is_connected=acct_id in connected_ids,
        ))

    return MetaAvailableAccountsResponse(accounts=accounts, total=len(accounts))


# ── Connect Account ──────────────────────────────────────────────

@router.post("/accounts/connect", response_model=MetaAdAccountResponse)
async def connect_account(
    request: MetaConnectAccountRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Connect a Meta ad account for data sync and management."""
    user_id = _user.id if _user else 0

    # Check if already connected
    result = await db.execute(
        select(MetaAdAccount).where(MetaAdAccount.account_id == request.account_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="このアカウントは既に接続されています")
        # Reactivate
        existing.is_active = True
        existing.user_id = user_id
        existing.account_name = request.account_name or existing.account_name
        existing.business_name = request.business_name or existing.business_name
        existing.currency = request.currency
        existing.timezone_name = request.timezone_name
        existing.sync_status = "pending"
        existing.sync_error = None
        await db.flush()
        await db.refresh(existing)
        logger.info("meta_account_reactivated", account_id=request.account_id)
        return MetaAdAccountResponse.model_validate(existing)

    # Verify account access via API
    token = await MetaTokenManager.get_access_token(db)
    if token:
        client = MetaMarketingClient(token)
        try:
            account_info = await client.get_account_info(request.account_id)
            # Update name/business from API if not provided
            if not request.account_name:
                request.account_name = account_info.get("name")
            if not request.business_name:
                request.business_name = account_info.get("business_name")
        except MetaMarketingAPIError as e:
            logger.warning("meta_account_verify_failed", account_id=request.account_id, error=str(e))
        finally:
            await client.close()

    account = MetaAdAccount(
        user_id=user_id,
        account_id=request.account_id,
        account_name=request.account_name,
        business_name=request.business_name,
        currency=request.currency,
        timezone_name=request.timezone_name,
        sync_status="pending",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    logger.info("meta_account_connected", account_id=request.account_id, user_id=user_id)
    return MetaAdAccountResponse.model_validate(account)


# ── Connected Accounts ───────────────────────────────────────────

@router.get("/accounts", response_model=MetaAdAccountListResponse)
async def list_connected_accounts(
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all connected Meta ad accounts."""
    query = select(MetaAdAccount).where(MetaAdAccount.is_active == True)
    if _user:
        query = query.where(MetaAdAccount.user_id == _user.id)
    query = query.order_by(MetaAdAccount.created_at.desc())

    result = await db.execute(query)
    accounts = result.scalars().all()

    return MetaAdAccountListResponse(
        accounts=[MetaAdAccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


# ── Disconnect Account ───────────────────────────────────────────

@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Disconnect a Meta ad account (soft delete)."""
    result = await db.execute(
        select(MetaAdAccount).where(
            MetaAdAccount.account_id == account_id,
            MetaAdAccount.is_active == True,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="アカウントが見つかりません")

    account.is_active = False
    logger.info("meta_account_disconnected", account_id=account_id)
    return {"status": "ok", "message": f"アカウント {account_id} を切断しました"}


# ── Sync Trigger ─────────────────────────────────────────────────

@router.post("/accounts/{account_id}/sync")
async def trigger_sync(
    account_id: str,
    insights_days: int = Query(7, ge=1, le=90),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger a manual data sync for a Meta ad account."""
    result = await db.execute(
        select(MetaAdAccount).where(
            MetaAdAccount.account_id == account_id,
            MetaAdAccount.is_active == True,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="アカウントが見つかりません")

    # Try dispatching to Celery
    try:
        from app.tasks.meta_sync_tasks import sync_meta_account_task
        task = sync_meta_account_task.delay(account_id, insights_days)
        return {"status": "started", "task_id": task.id, "message": "同期を開始しました"}
    except Exception as e:
        logger.warning("meta_sync_dispatch_failed", error=str(e))

    # Fallback: run inline
    token = await MetaTokenManager.get_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="Metaアクセストークンが設定されていません")

    from app.services.meta_marketing.sync_service import MetaSyncService

    client = MetaMarketingClient(token)
    try:
        service = MetaSyncService(client, db)
        summary = await service.full_sync(account_id, insights_days=insights_days)
        return {"status": "completed", **summary}
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Metaトークンが無効または期限切れです")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"Meta APIエラー: {e}")
    finally:
        await client.close()


# ── Campaign Listing ─────────────────────────────────────────────

@router.get("/campaigns")
async def list_campaigns(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List synced Meta campaigns."""
    from app.models.meta_campaign import MetaCampaign

    query = select(MetaCampaign)
    if account_id:
        query = query.where(MetaCampaign.account_id == account_id)
    if status:
        query = query.where(MetaCampaign.effective_status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(MetaCampaign.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    return {
        "campaigns": [
            {
                "id": c.id, "meta_id": c.meta_id, "account_id": c.account_id,
                "name": c.name, "status": c.status, "effective_status": c.effective_status,
                "objective": c.objective, "daily_budget": c.daily_budget,
                "lifetime_budget": c.lifetime_budget, "budget_remaining": c.budget_remaining,
                "start_time": c.start_time.isoformat() if c.start_time else None,
                "stop_time": c.stop_time.isoformat() if c.stop_time else None,
                "buying_type": c.buying_type,
                "special_ad_categories": c.special_ad_categories,
                "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
            }
            for c in campaigns
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Ad Set Listing ───────────────────────────────────────────────

@router.get("/ad-sets")
async def list_ad_sets(
    account_id: Optional[str] = None,
    campaign_meta_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List synced Meta ad sets."""
    from app.models.meta_campaign import MetaAdSet

    query = select(MetaAdSet)
    if account_id:
        query = query.where(MetaAdSet.account_id == account_id)
    if campaign_meta_id:
        query = query.where(MetaAdSet.campaign_meta_id == campaign_meta_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(MetaAdSet.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    ad_sets = result.scalars().all()

    return {
        "ad_sets": [
            {
                "id": a.id, "meta_id": a.meta_id, "campaign_meta_id": a.campaign_meta_id,
                "account_id": a.account_id, "name": a.name, "status": a.status,
                "effective_status": a.effective_status, "daily_budget": a.daily_budget,
                "lifetime_budget": a.lifetime_budget, "bid_strategy": a.bid_strategy,
                "bid_amount": a.bid_amount, "billing_event": a.billing_event,
                "optimization_goal": a.optimization_goal, "targeting": a.targeting,
                "start_time": a.start_time.isoformat() if a.start_time else None,
                "end_time": a.end_time.isoformat() if a.end_time else None,
                "created_at": a.created_at.isoformat(), "updated_at": a.updated_at.isoformat(),
            }
            for a in ad_sets
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Ad Listing ───────────────────────────────────────────────────

@router.get("/ads")
async def list_ads(
    account_id: Optional[str] = None,
    ad_set_meta_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List synced Meta ads with creative details."""
    from app.models.meta_campaign import MetaAd

    query = select(MetaAd)
    if account_id:
        query = query.where(MetaAd.account_id == account_id)
    if ad_set_meta_id:
        query = query.where(MetaAd.ad_set_meta_id == ad_set_meta_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(MetaAd.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    ads = result.scalars().all()

    return {
        "ads": [
            {
                "id": a.id, "meta_id": a.meta_id, "ad_set_meta_id": a.ad_set_meta_id,
                "account_id": a.account_id, "name": a.name, "status": a.status,
                "effective_status": a.effective_status,
                "creative_id": a.creative_id, "creative_thumbnail_url": a.creative_thumbnail_url,
                "creative_body": a.creative_body, "creative_title": a.creative_title,
                "creative_link_url": a.creative_link_url, "creative_image_url": a.creative_image_url,
                "creative_video_url": a.creative_video_url, "creative_type": a.creative_type,
                "linked_ad_id": a.linked_ad_id,
                "created_at": a.created_at.isoformat(), "updated_at": a.updated_at.isoformat(),
            }
            for a in ads
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Insights ─────────────────────────────────────────────────────

@router.get("/insights")
async def get_insights(
    account_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    level: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get synced performance insights."""
    from app.models.meta_campaign import MetaInsight

    query = select(MetaInsight).where(MetaInsight.account_id == account_id)

    if entity_type:
        query = query.where(MetaInsight.entity_type == entity_type)
    if entity_id:
        query = query.where(MetaInsight.entity_id == entity_id)
    if date_from:
        query = query.where(MetaInsight.date_start >= date_from)
    if date_to:
        query = query.where(MetaInsight.date_start <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(MetaInsight.date_start.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    insights = result.scalars().all()

    return {
        "insights": [
            {
                "id": i.id, "account_id": i.account_id,
                "entity_type": i.entity_type, "entity_id": i.entity_id,
                "date_start": i.date_start, "date_stop": i.date_stop,
                "impressions": i.impressions, "reach": i.reach, "clicks": i.clicks,
                "spend": i.spend, "ctr": i.ctr, "cpc": i.cpc, "cpm": i.cpm,
                "frequency": i.frequency,
                "conversions": i.conversions, "conversion_values": i.conversion_values,
                "cost_per_conversion": i.cost_per_conversion,
            }
            for i in insights
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ══════════════════════════════════════════════════════════════════
# Phase 3: Campaign Management (CRUD)
# ══════════════════════════════════════════════════════════════════

async def _get_campaign_manager(db: AsyncSession) -> "MetaCampaignManager":
    """Helper to get an authenticated campaign manager."""
    from app.services.meta_marketing.campaign_manager import MetaCampaignManager

    token = await MetaTokenManager.get_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="Metaアクセストークンが設定されていません")
    client = MetaMarketingClient(token)
    return MetaCampaignManager(client)


@router.post("/campaigns", response_model=MetaOperationResponse)
async def create_campaign(
    request: CreateCampaignRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new Meta campaign (always created as PAUSED)."""
    manager = await _get_campaign_manager(db)
    try:
        result = await manager.create_campaign(
            account_id=request.account_id,
            name=request.name,
            objective=request.objective,
            daily_budget=request.daily_budget,
            lifetime_budget=request.lifetime_budget,
            special_ad_categories=request.special_ad_categories,
        )
        return MetaOperationResponse(success=True, id=result.get("id"), message="キャンペーンを作成しました（PAUSED状態）")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"キャンペーン作成に失敗: {e}")
    finally:
        await manager.client.close()


@router.put("/campaigns/{campaign_meta_id}/status", response_model=MetaOperationResponse)
async def update_campaign_status(
    campaign_meta_id: str,
    request: UpdateCampaignStatusRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a campaign's status (ACTIVE/PAUSED/DELETED/ARCHIVED)."""
    manager = await _get_campaign_manager(db)
    try:
        await manager.update_campaign_status(campaign_meta_id, request.status)
        return MetaOperationResponse(success=True, id=campaign_meta_id, message=f"ステータスを{request.status}に変更しました")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"ステータス変更に失敗: {e}")
    finally:
        await manager.client.close()


@router.post("/ad-sets", response_model=MetaOperationResponse)
async def create_ad_set(
    request: CreateAdSetRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new Meta ad set (always created as PAUSED)."""
    manager = await _get_campaign_manager(db)
    try:
        result = await manager.create_ad_set(
            account_id=request.account_id,
            campaign_id=request.campaign_id,
            name=request.name,
            daily_budget=request.daily_budget,
            lifetime_budget=request.lifetime_budget,
            optimization_goal=request.optimization_goal,
            billing_event=request.billing_event,
            bid_strategy=request.bid_strategy,
            bid_amount=request.bid_amount,
            targeting=request.targeting,
            start_time=request.start_time,
            end_time=request.end_time,
        )
        return MetaOperationResponse(success=True, id=result.get("id"), message="広告セットを作成しました（PAUSED状態）")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"広告セット作成に失敗: {e}")
    finally:
        await manager.client.close()


@router.put("/ad-sets/{ad_set_meta_id}/status", response_model=MetaOperationResponse)
async def update_ad_set_status(
    ad_set_meta_id: str,
    request: UpdateCampaignStatusRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update an ad set's status."""
    manager = await _get_campaign_manager(db)
    try:
        await manager.update_ad_set_status(ad_set_meta_id, request.status)
        return MetaOperationResponse(success=True, id=ad_set_meta_id, message=f"ステータスを{request.status}に変更しました")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"ステータス変更に失敗: {e}")
    finally:
        await manager.client.close()


@router.post("/ads", response_model=MetaOperationResponse)
async def create_ad(
    request: CreateAdRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new Meta ad (always created as PAUSED)."""
    manager = await _get_campaign_manager(db)
    try:
        result = await manager.create_ad(
            account_id=request.account_id,
            ad_set_id=request.ad_set_id,
            name=request.name,
            creative_id=request.creative_id,
        )
        return MetaOperationResponse(success=True, id=result.get("id"), message="広告を作成しました（PAUSED状態）")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"広告作成に失敗: {e}")
    finally:
        await manager.client.close()


@router.put("/ads/{ad_meta_id}/status", response_model=MetaOperationResponse)
async def update_ad_status(
    ad_meta_id: str,
    request: UpdateCampaignStatusRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update an ad's status."""
    manager = await _get_campaign_manager(db)
    try:
        await manager.update_ad_status(ad_meta_id, request.status)
        return MetaOperationResponse(success=True, id=ad_meta_id, message=f"ステータスを{request.status}に変更しました")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"ステータス変更に失敗: {e}")
    finally:
        await manager.client.close()


@router.post("/creatives", response_model=MetaOperationResponse)
async def create_creative(
    request: CreateCreativeRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new ad creative."""
    manager = await _get_campaign_manager(db)
    try:
        result = await manager.create_creative(
            account_id=request.account_id,
            name=request.name,
            object_story_spec=request.object_story_spec,
        )
        return MetaOperationResponse(success=True, id=result.get("id"), message="クリエイティブを作成しました")
    except MetaMarketingAPIError as e:
        raise HTTPException(status_code=502, detail=f"クリエイティブ作成に失敗: {e}")
    finally:
        await manager.client.close()


@router.post("/accounts/{account_id}/image-upload")
async def upload_image(
    account_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload an image to a Meta ad account.

    Note: This endpoint expects multipart/form-data with a 'file' field.
    Handled separately due to file upload requirements.
    """
    from fastapi import UploadFile, File as FastAPIFile

    # This is a placeholder — actual file handling requires the UploadFile dependency
    # which needs to be in the function signature. We'll handle it via the request directly.
    raise HTTPException(status_code=501, detail="画像アップロードはまだ実装されていません")


# ══════════════════════════════════════════════════════════════════
# Phase 4: Creative Analysis & Competitor Comparison
# ══════════════════════════════════════════════════════════════════

@router.post("/ads/{meta_ad_id}/analyze")
async def analyze_meta_ad(
    meta_ad_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger AI analysis on a Meta ad by linking it to the internal analysis pipeline."""
    from app.services.meta_marketing.creative_analyzer import CreativeAnalyzer

    analyzer = CreativeAnalyzer(db)
    result = await analyzer.analyze_own_ad(meta_ad_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/ads/{meta_ad_id}/competitor-comparison")
async def get_competitor_comparison(
    meta_ad_id: str,
    category: Optional[str] = None,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Compare a Meta ad's analysis with competitor averages."""
    from app.services.meta_marketing.creative_analyzer import CreativeAnalyzer

    analyzer = CreativeAnalyzer(db)
    result = await analyzer.compare_with_competitors(meta_ad_id, category=category)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/accounts/{account_id}/creative-insights")
async def get_creative_insights(
    account_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get account-level creative performance insights."""
    from app.services.meta_marketing.creative_analyzer import CreativeAnalyzer

    analyzer = CreativeAnalyzer(db)
    return await analyzer.get_creative_insights_summary(account_id)


# ══════════════════════════════════════════════════════════════════
# Phase 5: A/B Test Management
# ══════════════════════════════════════════════════════════════════

@router.get("/ab-tests")
async def list_ab_tests(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List A/B test experiments."""
    from app.models.ab_test import ABTestExperiment, ABTestVariant
    from sqlalchemy.orm import selectinload

    query = select(ABTestExperiment).options(selectinload(ABTestExperiment.variants))
    if account_id:
        query = query.where(ABTestExperiment.account_id == account_id)
    if status:
        query = query.where(ABTestExperiment.status == status)
    query = query.order_by(ABTestExperiment.created_at.desc())

    result = await db.execute(query)
    experiments = result.scalars().all()

    return {
        "experiments": [
            {
                "id": e.id, "name": e.name, "status": e.status,
                "test_type": e.test_type, "primary_metric": e.primary_metric,
                "hypothesis": e.hypothesis, "account_id": e.account_id,
                "confidence_level": e.confidence_level,
                "winner_variant_id": e.winner_variant_id,
                "statistical_significance": e.statistical_significance,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "created_at": e.created_at.isoformat(),
                "variants": [
                    {
                        "id": v.id, "name": v.name, "variant_type": v.variant_type,
                        "impressions": v.impressions, "clicks": v.clicks,
                        "conversions": v.conversions, "spend": v.spend,
                        "ctr": v.ctr, "cvr": v.cvr, "cpa": v.cpa,
                        "is_winner": v.is_winner,
                        "variation_description": v.variation_description,
                    }
                    for v in e.variants
                ],
            }
            for e in experiments
        ],
        "total": len(experiments),
    }


@router.post("/ab-tests")
async def create_ab_test(
    data: dict,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new A/B test experiment."""
    from app.services.meta_marketing.ab_test_service import ABTestService

    user_id = _user.id if _user else 0
    service = ABTestService(db)
    experiment = await service.create_experiment(
        user_id=user_id,
        account_id=data.get("account_id", ""),
        name=data.get("name", ""),
        test_type=data.get("test_type", "creative"),
        hypothesis=data.get("hypothesis"),
        primary_metric=data.get("primary_metric", "ctr"),
        confidence_level=data.get("confidence_level", 0.95),
        min_sample_size=data.get("min_sample_size", 1000),
        variants=data.get("variants", []),
    )
    return {"id": experiment.id, "name": experiment.name, "status": experiment.status}


@router.get("/ab-tests/{experiment_id}")
async def get_ab_test(
    experiment_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a single A/B test experiment with variants."""
    from app.models.ab_test import ABTestExperiment
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(ABTestExperiment)
        .options(selectinload(ABTestExperiment.variants))
        .where(ABTestExperiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="実験が見つかりません")

    return {
        "id": experiment.id, "name": experiment.name, "status": experiment.status,
        "test_type": experiment.test_type, "primary_metric": experiment.primary_metric,
        "hypothesis": experiment.hypothesis, "account_id": experiment.account_id,
        "confidence_level": experiment.confidence_level,
        "min_sample_size": experiment.min_sample_size,
        "winner_variant_id": experiment.winner_variant_id,
        "statistical_significance": experiment.statistical_significance,
        "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
        "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
        "created_at": experiment.created_at.isoformat(),
        "variants": [
            {
                "id": v.id, "name": v.name, "variant_type": v.variant_type,
                "impressions": v.impressions, "clicks": v.clicks,
                "conversions": v.conversions, "spend": v.spend,
                "ctr": v.ctr, "cvr": v.cvr, "cpa": v.cpa,
                "is_winner": v.is_winner,
                "variation_description": v.variation_description,
                "ad_meta_id": v.ad_meta_id,
                "creative_meta_id": v.creative_meta_id,
            }
            for v in experiment.variants
        ],
    }


@router.post("/ab-tests/{experiment_id}/update-metrics")
async def update_ab_test_metrics(
    experiment_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update variant metrics from Meta insights."""
    from app.services.meta_marketing.ab_test_service import ABTestService

    service = ABTestService(db)
    result = await service.update_variant_metrics(experiment_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/ab-tests/{experiment_id}/complete")
async def complete_ab_test(
    experiment_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Complete an experiment — check significance and declare winner."""
    from app.services.meta_marketing.ab_test_service import ABTestService

    service = ABTestService(db)
    result = await service.complete_experiment(experiment_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ══════════════════════════════════════════════════════════════════
# Phase 6: Optimization Recommendations
# ══════════════════════════════════════════════════════════════════

@router.get("/recommendations")
async def list_recommendations(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List optimization recommendations."""
    from app.models.optimization import OptimizationRecommendation

    query = select(OptimizationRecommendation)
    if account_id:
        query = query.where(OptimizationRecommendation.account_id == account_id)
    if status:
        query = query.where(OptimizationRecommendation.status == status)
    if severity:
        query = query.where(OptimizationRecommendation.severity == severity)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(OptimizationRecommendation.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    recs = result.scalars().all()

    return {
        "recommendations": [
            {
                "id": r.id, "account_id": r.account_id,
                "entity_type": r.entity_type, "entity_id": r.entity_id,
                "entity_name": r.entity_name,
                "recommendation_type": r.recommendation_type,
                "severity": r.severity,
                "title": r.title, "description": r.description,
                "rationale": r.rationale,
                "predicted_impact": r.predicted_impact,
                "status": r.status,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                "user_feedback": r.user_feedback,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in recs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/recommendations/{recommendation_id}/accept")
async def accept_recommendation(
    recommendation_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Accept an optimization recommendation."""
    from app.models.optimization import OptimizationRecommendation

    result = await db.execute(
        select(OptimizationRecommendation).where(OptimizationRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="レコメンドが見つかりません")
    if rec.status != "pending":
        raise HTTPException(status_code=400, detail=f"レコメンドのステータスが{rec.status}です")

    rec.status = "accepted"
    return {"status": "ok", "message": "レコメンドを承認しました"}


@router.post("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Reject an optimization recommendation."""
    from app.models.optimization import OptimizationRecommendation

    result = await db.execute(
        select(OptimizationRecommendation).where(OptimizationRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="レコメンドが見つかりません")

    rec.status = "rejected"
    return {"status": "ok", "message": "レコメンドを却下しました"}


@router.post("/recommendations/{recommendation_id}/apply")
async def apply_recommendation(
    recommendation_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Apply an accepted recommendation to Meta API."""
    from app.services.meta_marketing.optimizer import MetaOptimizer

    optimizer = MetaOptimizer(db)

    # Get client for API calls
    token = await MetaTokenManager.get_access_token(db)
    client = None
    if token:
        client = MetaMarketingClient(token)

    try:
        result = await optimizer.apply_recommendation(recommendation_id, client=client)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    finally:
        if client:
            await client.close()


@router.get("/accounts/{account_id}/creative-health")
async def get_creative_health(
    account_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get creative health status for active ads in an account."""
    from app.models.optimization import OptimizationRecommendation

    # Get recent creative refresh recommendations
    result = await db.execute(
        select(OptimizationRecommendation)
        .where(
            OptimizationRecommendation.account_id == account_id,
            OptimizationRecommendation.recommendation_type == "creative_refresh",
            OptimizationRecommendation.status == "pending",
        )
        .order_by(OptimizationRecommendation.severity.desc())
    )
    fatigued = result.scalars().all()

    return {
        "account_id": account_id,
        "fatigued_ads": len(fatigued),
        "ads": [
            {
                "entity_id": r.entity_id,
                "severity": r.severity,
                "title": r.title,
                "rationale": r.rationale,
            }
            for r in fatigued
        ],
    }


# ══════════════════════════════════════════════════════════════════
# Smart Insights Engine — Performance Summary, Trends, Creative Performance
# ══════════════════════════════════════════════════════════════════

async def _validate_account(db: AsyncSession, account_id: str) -> None:
    """Raise 404 if account does not exist or is inactive."""
    result = await db.execute(
        select(MetaAdAccount).where(
            MetaAdAccount.account_id == account_id,
            MetaAdAccount.is_active == True,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="アカウントが見つかりません")


@router.get("/accounts/{account_id}/performance-summary")
async def get_performance_summary(
    account_id: str,
    days: int = Query(7, ge=1, le=90),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """KPI summary with period-over-period comparison."""
    from app.services.meta_marketing.insights_engine import InsightsEngine

    await _validate_account(db, account_id)
    try:
        engine = InsightsEngine(db)
        return await engine.get_performance_summary(account_id, days=days)
    except Exception as e:
        logger.error("performance_summary_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="パフォーマンスデータの取得に失敗しました")


@router.get("/accounts/{account_id}/daily-trends")
async def get_daily_trends(
    account_id: str,
    days: int = Query(30, ge=1, le=90),
    entity_type: Optional[str] = None,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Daily aggregated metrics for trend charts."""
    from app.services.meta_marketing.insights_engine import InsightsEngine

    await _validate_account(db, account_id)
    try:
        engine = InsightsEngine(db)
        return await engine.get_daily_trends(account_id, days=days, entity_type=entity_type)
    except Exception as e:
        logger.error("daily_trends_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="トレンドデータの取得に失敗しました")


@router.get("/accounts/{account_id}/creative-performance")
async def get_creative_performance(
    account_id: str,
    days: int = Query(7, ge=1, le=90),
    sort_by: str = Query("spend", pattern="^(spend|ctr|cpc|cpa|impressions|conversions|roas)$"),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Creative-level performance data — each ad with creative attributes AND metrics."""
    from app.services.meta_marketing.insights_engine import InsightsEngine

    await _validate_account(db, account_id)
    try:
        engine = InsightsEngine(db)
        return await engine.get_creative_performance(account_id, days=days, sort_by=sort_by)
    except Exception as e:
        logger.error("creative_performance_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="クリエイティブパフォーマンスの取得に失敗しました")


@router.get("/accounts/{account_id}/smart-insights")
async def get_smart_insights(
    account_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Auto-generated actionable insights (CTR trends, fatigue detection, etc.)."""
    from app.services.meta_marketing.insights_engine import InsightsEngine

    await _validate_account(db, account_id)
    try:
        engine = InsightsEngine(db)
        return await engine.generate_smart_insights(account_id)
    except Exception as e:
        logger.error("smart_insights_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="インサイトの生成に失敗しました")


@router.get("/campaigns/{campaign_meta_id}/budget-allocation")
async def get_budget_allocation(
    campaign_meta_id: str,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get budget allocation analysis for ad sets within a campaign."""
    from app.models.meta_campaign import MetaAdSet, MetaInsight

    # Get ad sets for this campaign
    result = await db.execute(
        select(MetaAdSet).where(MetaAdSet.campaign_meta_id == campaign_meta_id)
    )
    ad_sets = result.scalars().all()

    allocations = []
    for ad_set in ad_sets:
        # Get recent spend/performance
        result = await db.execute(
            select(
                func.sum(MetaInsight.spend).label("total_spend"),
                func.sum(MetaInsight.clicks).label("total_clicks"),
                func.sum(MetaInsight.conversions).label("total_conversions"),
                func.sum(MetaInsight.impressions).label("total_impressions"),
            )
            .where(
                MetaInsight.entity_type == "adset",
                MetaInsight.entity_id == ad_set.meta_id,
            )
        )
        row = result.one_or_none()

        spend = float(row.total_spend or 0) if row else 0
        clicks = int(row.total_clicks or 0) if row else 0
        conversions = int(row.total_conversions or 0) if row else 0
        impressions = int(row.total_impressions or 0) if row else 0

        allocations.append({
            "ad_set_meta_id": ad_set.meta_id,
            "ad_set_name": ad_set.name,
            "daily_budget": ad_set.daily_budget,
            "total_spend": spend,
            "total_clicks": clicks,
            "total_conversions": conversions,
            "total_impressions": impressions,
            "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            "cpa": round(spend / conversions, 2) if conversions > 0 else None,
        })

    return {
        "campaign_meta_id": campaign_meta_id,
        "ad_sets": allocations,
        "total_spend": sum(a["total_spend"] for a in allocations),
    }
