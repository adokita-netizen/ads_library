"""LP Analysis API endpoints."""

import asyncio
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.core.database import SyncSessionLocal
from app.models.landing_page import (
    AppealAxisAnalysis,
    LandingPage,
    LPAnalysis,
    LPSection,
    USPPattern,
)
from app.schemas.lp_analysis import (
    AppealAxisResponse,
    CompetitorAppealPatternResponse,
    GenreInsightResponse,
    LPAnalysisDetailResponse,
    LPBatchCrawlRequest,
    LPCompetitorRequest,
    LPCrawlRequest,
    LPDetailResponse,
    LPListResponse,
    LPResponse,
    LPSectionResponse,
    LPTaskResponse,
    USPFlowRequest,
    USPFlowResponse,
    USPPatternResponse,
)
from app.services.lp_analysis.competitor_intelligence import CompetitorIntelligence
from app.tasks.lp_tasks import batch_crawl_lps_task, crawl_and_analyze_lp_task

logger = structlog.get_logger()
router = APIRouter(prefix="/lp-analysis", tags=["LP Analysis"])


@router.post("/crawl", response_model=LPTaskResponse)
async def crawl_lp(request: LPCrawlRequest):
    """Submit a landing page URL for crawling and analysis."""
    task = crawl_and_analyze_lp_task.delay(
        url=request.url,
        ad_id=request.ad_id,
        genre=request.genre,
        product_name=request.product_name,
        advertiser_name=request.advertiser_name,
        auto_analyze=request.auto_analyze,
    )
    return LPTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"LP分析タスクをキューに追加しました: {request.url}",
    )


@router.post("/batch-crawl", response_model=LPTaskResponse)
async def batch_crawl_lps(request: LPBatchCrawlRequest):
    """Submit multiple LP URLs for batch crawling."""
    task = batch_crawl_lps_task.delay(
        urls=request.urls,
        genre=request.genre,
        auto_analyze=request.auto_analyze,
    )
    return LPTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"{len(request.urls)}件のLP分析タスクをキューに追加しました",
    )


@router.get("/list", response_model=LPListResponse)
async def list_landing_pages(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    genre: Optional[str] = None,
    lp_type: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    search: Optional[str] = None,
):
    """List analyzed landing pages with filters."""
    session = SyncSessionLocal()
    try:
        query = session.query(LandingPage)

        if genre:
            query = query.filter(LandingPage.genre == genre)
        if lp_type:
            query = query.filter(LandingPage.lp_type == lp_type)
        if status:
            query = query.filter(LandingPage.status == status)
        if domain:
            query = query.filter(LandingPage.domain.ilike(f"%{domain}%"))
        if search:
            query = query.filter(
                (LandingPage.title.ilike(f"%{search}%"))
                | (LandingPage.product_name.ilike(f"%{search}%"))
                | (LandingPage.advertiser_name.ilike(f"%{search}%"))
            )

        total = query.count()
        lps = query.order_by(LandingPage.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return LPListResponse(
            landing_pages=[LPResponse.model_validate(lp) for lp in lps],
            total=total,
            page=page,
            page_size=page_size,
        )
    finally:
        session.close()


@router.get("/{lp_id}", response_model=LPDetailResponse)
async def get_lp_detail(lp_id: int):
    """Get full LP detail with sections, USPs, appeal axes, and analysis."""
    session = SyncSessionLocal()
    try:
        lp = session.query(LandingPage).filter(LandingPage.id == lp_id).first()
        if not lp:
            raise HTTPException(status_code=404, detail="Landing page not found")

        sections = session.query(LPSection).filter(
            LPSection.landing_page_id == lp_id
        ).order_by(LPSection.section_order).all()

        usps = session.query(USPPattern).filter(
            USPPattern.landing_page_id == lp_id
        ).order_by(USPPattern.prominence_score.desc()).all()

        appeals = session.query(AppealAxisAnalysis).filter(
            AppealAxisAnalysis.landing_page_id == lp_id
        ).order_by(AppealAxisAnalysis.strength_score.desc()).all()

        analysis = session.query(LPAnalysis).filter(
            LPAnalysis.landing_page_id == lp_id
        ).first()

        response = LPDetailResponse.model_validate(lp)
        response.sections = [LPSectionResponse.model_validate(s) for s in sections]
        response.usp_patterns = [USPPatternResponse.model_validate(u) for u in usps]
        response.appeal_axes = [AppealAxisResponse.model_validate(a) for a in appeals]
        if analysis:
            response.analysis = LPAnalysisDetailResponse.model_validate(analysis)

        return response
    finally:
        session.close()


@router.get("/{lp_id}/usps", response_model=list[USPPatternResponse])
async def get_lp_usps(lp_id: int):
    """Get USP patterns for a specific LP."""
    session = SyncSessionLocal()
    try:
        usps = session.query(USPPattern).filter(
            USPPattern.landing_page_id == lp_id
        ).order_by(USPPattern.prominence_score.desc()).all()
        return [USPPatternResponse.model_validate(u) for u in usps]
    finally:
        session.close()


@router.get("/{lp_id}/appeal-axes", response_model=list[AppealAxisResponse])
async def get_lp_appeal_axes(lp_id: int):
    """Get appeal axis analysis for a specific LP."""
    session = SyncSessionLocal()
    try:
        appeals = session.query(AppealAxisAnalysis).filter(
            AppealAxisAnalysis.landing_page_id == lp_id
        ).order_by(AppealAxisAnalysis.strength_score.desc()).all()
        return [AppealAxisResponse.model_validate(a) for a in appeals]
    finally:
        session.close()


@router.post("/competitor-insight", response_model=GenreInsightResponse)
async def get_competitor_insight(request: LPCompetitorRequest):
    """Get competitor intelligence for a genre."""
    session = SyncSessionLocal()
    try:
        # Get all analyzed LPs in this genre
        lps = session.query(LandingPage).filter(
            LandingPage.genre == request.genre,
            LandingPage.status == "completed",
        ).limit(request.limit).all()

        if not lps:
            raise HTTPException(
                status_code=404,
                detail=f"ジャンル '{request.genre}' の分析済みLPが見つかりません",
            )

        # Gather analysis data
        lp_analyses = []
        for lp in lps:
            analysis = session.query(LPAnalysis).filter(
                LPAnalysis.landing_page_id == lp.id
            ).first()
            if not analysis:
                continue

            usps = session.query(USPPattern).filter(
                USPPattern.landing_page_id == lp.id
            ).all()
            appeals = session.query(AppealAxisAnalysis).filter(
                AppealAxisAnalysis.landing_page_id == lp.id
            ).all()

            lp_analyses.append({
                "quality_score": analysis.overall_quality_score,
                "page_flow": analysis.page_flow_pattern,
                "target_gender": analysis.inferred_target_gender,
                "target_age_range": analysis.inferred_target_age_range,
                "target_concerns": analysis.inferred_target_concerns,
                "usps": [
                    {
                        "category": u.usp_category,
                        "text": u.usp_text,
                        "prominence": u.prominence_score,
                        "keywords": u.keywords,
                    }
                    for u in usps
                ],
                "appeal_axes": [
                    {
                        "axis": a.appeal_axis,
                        "strength": a.strength_score,
                        "evidence_texts": a.evidence_texts,
                    }
                    for a in appeals
                ],
            })

        ci = CompetitorIntelligence()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            insight = loop.run_until_complete(
                ci.generate_genre_insight(request.genre, lp_analyses)
            )
        finally:
            loop.close()

        return GenreInsightResponse(
            genre=insight.genre,
            total_lps_analyzed=insight.total_lps_analyzed,
            dominant_appeal=insight.dominant_appeal,
            appeal_distribution=[
                CompetitorAppealPatternResponse(
                    appeal_axis=p.appeal_axis,
                    avg_strength=p.avg_strength,
                    usage_count=p.usage_count,
                    sample_texts=p.sample_texts,
                )
                for p in insight.appeal_distribution
            ],
            common_usps=insight.common_usps,
            avg_quality_score=insight.avg_quality_score,
            common_structures=insight.common_structures,
            target_personas=insight.target_personas,
            recommendations=insight.recommendations,
        )
    finally:
        session.close()


@router.post("/usp-flow", response_model=USPFlowResponse)
async def generate_usp_flow(request: USPFlowRequest):
    """Generate USP → Article LP flow recommendation."""
    session = SyncSessionLocal()
    try:
        # Gather competitor analysis data
        if request.competitor_lp_ids:
            lps = session.query(LandingPage).filter(
                LandingPage.id.in_(request.competitor_lp_ids),
                LandingPage.status == "completed",
            ).all()
        else:
            # Auto-select by genre
            lps = session.query(LandingPage).filter(
                LandingPage.genre == request.genre,
                LandingPage.status == "completed",
            ).limit(20).all()

        competitor_analyses = []
        for lp in lps:
            analysis = session.query(LPAnalysis).filter(
                LPAnalysis.landing_page_id == lp.id
            ).first()
            if not analysis:
                continue

            usps = session.query(USPPattern).filter(
                USPPattern.landing_page_id == lp.id
            ).all()
            appeals = session.query(AppealAxisAnalysis).filter(
                AppealAxisAnalysis.landing_page_id == lp.id
            ).all()

            competitor_analyses.append({
                "quality_score": analysis.overall_quality_score,
                "page_flow": analysis.page_flow_pattern,
                "usps": [
                    {"category": u.usp_category, "text": u.usp_text, "prominence": u.prominence_score, "keywords": u.keywords}
                    for u in usps
                ],
                "appeal_axes": [
                    {"axis": a.appeal_axis, "strength": a.strength_score, "evidence_texts": a.evidence_texts}
                    for a in appeals
                ],
            })

        ci = CompetitorIntelligence()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            recommendation = loop.run_until_complete(
                ci.generate_usp_flow_recommendation(
                    product_name=request.product_name,
                    product_description=request.product_description,
                    target_audience=request.target_audience,
                    genre=request.genre,
                    competitor_analyses=competitor_analyses,
                )
            )
        finally:
            loop.close()

        return USPFlowResponse(
            recommended_primary_usp=recommendation.recommended_primary_usp,
            recommended_appeal_axis=recommendation.recommended_appeal_axis,
            article_lp_structure=recommendation.article_lp_structure,
            headline_suggestions=recommendation.headline_suggestions,
            differentiation_opportunities=recommendation.differentiation_opportunities,
            competitor_gaps=recommendation.competitor_gaps,
            estimated_effectiveness=recommendation.estimated_effectiveness,
            reasoning=recommendation.reasoning,
        )
    finally:
        session.close()
