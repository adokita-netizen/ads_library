"""Campaign CRUD API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_async_session
from app.core.storage import get_storage_client
from app.models.ad import Ad
from app.models.campaign import Campaign, CampaignAd
from app.models.user import User
from app.schemas.campaign import (
    CampaignAdAdd,
    CampaignAdItem,
    CampaignCreate,
    CampaignDetailResponse,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List campaigns owned by the current user."""
    # Count ads per campaign with a subquery
    ad_count_sq = (
        select(CampaignAd.campaign_id, func.count(CampaignAd.id).label("ad_count"))
        .group_by(CampaignAd.campaign_id)
        .subquery()
    )
    result = await db.execute(
        select(Campaign, func.coalesce(ad_count_sq.c.ad_count, 0).label("ad_count"))
        .outerjoin(ad_count_sq, Campaign.id == ad_count_sq.c.campaign_id)
        .where(Campaign.user_id == user.id)
        .order_by(Campaign.updated_at.desc())
    )
    rows = result.all()
    campaigns = []
    for campaign, ad_count in rows:
        campaigns.append(
            CampaignResponse(
                id=campaign.id,
                name=campaign.name,
                description=campaign.description,
                user_id=campaign.user_id,
                ad_count=ad_count,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
            )
        )
    return CampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new campaign."""
    campaign = Campaign(name=body.name, description=body.description, user_id=user.id)
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    await db.commit()
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        user_id=campaign.user_id,
        ad_count=0,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get campaign detail with ads and presigned media URLs."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.ads).selectinload(CampaignAd.ad))
        .where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")

    storage = get_storage_client()
    ad_items: list[CampaignAdItem] = []
    for ca in campaign.ads:
        ad: Ad = ca.ad
        # Generate presigned URLs
        image_url = ad.image_url
        video_url = ad.video_url
        thumbnail_url = None
        if ad.image_s3_key:
            image_url = storage.get_presigned_url(ad.image_s3_key)
        if ad.s3_key:
            video_url = storage.get_presigned_url(ad.s3_key)
        if ad.thumbnail_s3_key:
            thumbnail_url = storage.get_presigned_url(ad.thumbnail_s3_key)

        ad_items.append(
            CampaignAdItem(
                id=ca.id,
                ad_id=ca.ad_id,
                notes=ca.notes,
                created_at=ca.created_at,
                title=ad.title,
                platform=ad.platform.value if hasattr(ad.platform, "value") else ad.platform,
                creative_type=ad.creative_type,
                advertiser_name=ad.advertiser_name,
                brand_name=ad.brand_name,
                duration_seconds=ad.duration_seconds,
                view_count=ad.view_count,
                image_url=image_url,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                snapshot_url=ad.snapshot_url,
            )
        )

    return CampaignDetailResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        user_id=campaign.user_id,
        ads=ad_items,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")

    if body.name is not None:
        campaign.name = body.name
    if body.description is not None:
        campaign.description = body.description

    await db.flush()
    await db.refresh(campaign)
    await db.commit()

    # Count ads
    count_result = await db.execute(
        select(func.count(CampaignAd.id)).where(CampaignAd.campaign_id == campaign_id)
    )
    ad_count = count_result.scalar() or 0

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        user_id=campaign.user_id,
        ad_count=ad_count,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")

    await db.delete(campaign)
    await db.commit()


@router.post("/{campaign_id}/ads", response_model=CampaignAdItem, status_code=201)
async def add_ad_to_campaign(
    campaign_id: int,
    body: CampaignAdAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Add an ad to a campaign."""
    # Verify campaign ownership
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")

    # Verify ad exists
    ad_result = await db.execute(select(Ad).where(Ad.id == body.ad_id))
    ad = ad_result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="広告が見つかりません")

    # Check duplicate
    dup_result = await db.execute(
        select(CampaignAd).where(
            CampaignAd.campaign_id == campaign_id, CampaignAd.ad_id == body.ad_id
        )
    )
    if dup_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="この広告は既にキャンペーンに追加されています")

    ca = CampaignAd(campaign_id=campaign_id, ad_id=body.ad_id, notes=body.notes)
    db.add(ca)
    await db.flush()
    await db.refresh(ca)
    await db.commit()

    # Generate presigned URLs
    storage = get_storage_client()
    image_url = ad.image_url
    video_url = ad.video_url
    thumbnail_url = None
    if ad.image_s3_key:
        image_url = storage.get_presigned_url(ad.image_s3_key)
    if ad.s3_key:
        video_url = storage.get_presigned_url(ad.s3_key)
    if ad.thumbnail_s3_key:
        thumbnail_url = storage.get_presigned_url(ad.thumbnail_s3_key)

    return CampaignAdItem(
        id=ca.id,
        ad_id=ca.ad_id,
        notes=ca.notes,
        created_at=ca.created_at,
        title=ad.title,
        platform=ad.platform.value if hasattr(ad.platform, "value") else ad.platform,
        creative_type=ad.creative_type,
        advertiser_name=ad.advertiser_name,
        brand_name=ad.brand_name,
        duration_seconds=ad.duration_seconds,
        view_count=ad.view_count,
        image_url=image_url,
        video_url=video_url,
        thumbnail_url=thumbnail_url,
        snapshot_url=ad.snapshot_url,
    )


@router.delete("/{campaign_id}/ads/{ad_id}", status_code=204)
async def remove_ad_from_campaign(
    campaign_id: int,
    ad_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Remove an ad from a campaign."""
    # Verify campaign ownership
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")

    ca_result = await db.execute(
        select(CampaignAd).where(
            CampaignAd.campaign_id == campaign_id, CampaignAd.ad_id == ad_id
        )
    )
    ca = ca_result.scalar_one_or_none()
    if not ca:
        raise HTTPException(status_code=404, detail="この広告はキャンペーンに含まれていません")

    await db.delete(ca)
    await db.commit()
