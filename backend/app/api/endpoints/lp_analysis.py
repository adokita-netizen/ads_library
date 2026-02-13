"""LP Analysis API endpoints."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user_sync
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
    LPCompareAxisItem,
    LPCompareRequest,
    LPCompareResponse,
    LPCompetitorRequest,
    LPCrawlRequest,
    LPDetailResponse,
    LPListResponse,
    LPResponse,
    LPSectionResponse,
    LPTaskResponse,
    OwnLPImportRequest,
    OwnLPListResponse,
    OwnLPResponse,
    OwnLPUpdateRequest,
    USPFlowRequest,
    USPFlowResponse,
    USPPatternResponse,
)
from app.services.lp_analysis.competitor_intelligence import CompetitorIntelligence
from app.services.lp_analysis.lp_comparator import LPComparator
from app.tasks.lp_tasks import (
    analyze_own_lp_content_task,
    batch_crawl_lps_task,
    crawl_and_analyze_lp_task,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/lp-analysis", tags=["LP Analysis"])


@router.post("/crawl", response_model=LPTaskResponse)
async def crawl_lp(
    request: LPCrawlRequest,
    current_user: dict = Depends(get_current_user_sync),
):
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
async def batch_crawl_lps(
    request: LPBatchCrawlRequest,
    current_user: dict = Depends(get_current_user_sync),
):
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
async def get_competitor_insight(
    request: LPCompetitorRequest,
    current_user: dict = Depends(get_current_user_sync),
):
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

        # Gather analysis data (bulk fetch to avoid N+1)
        lp_ids = [lp.id for lp in lps]

        analyses_by_lp = {}
        if lp_ids:
            all_analyses = session.query(LPAnalysis).filter(
                LPAnalysis.landing_page_id.in_(lp_ids)
            ).all()
            analyses_by_lp = {a.landing_page_id: a for a in all_analyses}

        usps_by_lp: dict[int, list] = {lid: [] for lid in lp_ids}
        all_usps = session.query(USPPattern).filter(
            USPPattern.landing_page_id.in_(lp_ids)
        ).all()
        for u in all_usps:
            usps_by_lp[u.landing_page_id].append(u)

        appeals_by_lp: dict[int, list] = {lid: [] for lid in lp_ids}
        all_appeals = session.query(AppealAxisAnalysis).filter(
            AppealAxisAnalysis.landing_page_id.in_(lp_ids)
        ).all()
        for a in all_appeals:
            appeals_by_lp[a.landing_page_id].append(a)

        lp_analyses = []
        for lp in lps:
            analysis = analyses_by_lp.get(lp.id)
            if not analysis:
                continue

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
                    for u in usps_by_lp.get(lp.id, [])
                ],
                "appeal_axes": [
                    {
                        "axis": a.appeal_axis,
                        "strength": a.strength_score,
                        "evidence_texts": a.evidence_texts,
                    }
                    for a in appeals_by_lp.get(lp.id, [])
                ],
            })

        ci = CompetitorIntelligence()
        insight = await ci.generate_genre_insight(request.genre, lp_analyses)

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
async def generate_usp_flow(
    request: USPFlowRequest,
    current_user: dict = Depends(get_current_user_sync),
):
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

        # Bulk fetch analysis data to avoid N+1 queries
        lp_ids = [lp.id for lp in lps]

        analyses_map = {}
        if lp_ids:
            all_analyses = session.query(LPAnalysis).filter(
                LPAnalysis.landing_page_id.in_(lp_ids)
            ).all()
            analyses_map = {a.landing_page_id: a for a in all_analyses}

        usps_map: dict[int, list] = {lid: [] for lid in lp_ids}
        for u in session.query(USPPattern).filter(USPPattern.landing_page_id.in_(lp_ids)).all():
            usps_map[u.landing_page_id].append(u)

        appeals_map: dict[int, list] = {lid: [] for lid in lp_ids}
        for a in session.query(AppealAxisAnalysis).filter(AppealAxisAnalysis.landing_page_id.in_(lp_ids)).all():
            appeals_map[a.landing_page_id].append(a)

        competitor_analyses = []
        for lp in lps:
            analysis = analyses_map.get(lp.id)
            if not analysis:
                continue

            competitor_analyses.append({
                "quality_score": analysis.overall_quality_score,
                "page_flow": analysis.page_flow_pattern,
                "usps": [
                    {"category": u.usp_category, "text": u.usp_text, "prominence": u.prominence_score, "keywords": u.keywords}
                    for u in usps_map.get(lp.id, [])
                ],
                "appeal_axes": [
                    {"axis": a.appeal_axis, "strength": a.strength_score, "evidence_texts": a.evidence_texts}
                    for a in appeals_map.get(lp.id, [])
                ],
            })

        ci = CompetitorIntelligence()
        try:
            recommendation = await ci.generate_usp_flow_recommendation(
                product_name=request.product_name,
                product_description=request.product_description,
                target_audience=request.target_audience,
                genre=request.genre,
                competitor_analyses=competitor_analyses,
            )
        except Exception as e:
            logger.error("usp_flow_generation_failed", error=str(e))
            raise HTTPException(status_code=500, detail="USPフロー推奨の生成に失敗しました")

        if not recommendation:
            raise HTTPException(status_code=500, detail="USPフロー推奨の生成に失敗しました")

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


# ==================== Own LP Management ====================


@router.post("/own/import", response_model=LPResponse)
async def import_own_lp(
    request: OwnLPImportRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Import own LP for analysis and comparison against competitors."""
    if not request.url and not request.html_content and not request.text_content:
        raise HTTPException(
            status_code=400,
            detail="url, html_content, text_content のいずれかを指定してください",
        )

    session = SyncSessionLocal()
    try:
        import hashlib
        from datetime import datetime, timezone

        # Build URL hash
        source = request.url or f"own-lp-{request.label}"
        url_hash = hashlib.sha256(source.encode()).hexdigest()

        # Check for existing own LP with same hash
        existing = session.query(LandingPage).filter(
            LandingPage.url_hash == url_hash,
            LandingPage.is_own == True,  # noqa: E712
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"同じURLまたはラベルの自社LPが既に登録されています (ID: {existing.id})",
            )

        lp = LandingPage(
            url=request.url or f"own://{request.label}",
            url_hash=url_hash,
            is_own=True,
            own_lp_label=request.label,
            own_lp_version=request.version or 1,
            genre=request.genre,
            product_name=request.product_name,
            advertiser_name=request.advertiser_name,
            lp_type="article",
            status="pending",
        )

        # If text/html content provided directly, store it
        if request.text_content:
            lp.full_text_content = request.text_content
            lp.word_count = len(request.text_content)
            lp.status = "completed" if not request.auto_analyze else "analyzing"
        elif request.html_content:
            lp.full_text_content = request.html_content
            lp.word_count = len(request.html_content)
            lp.status = "completed" if not request.auto_analyze else "analyzing"

        session.add(lp)
        session.commit()
        session.refresh(lp)

        # If URL provided, queue crawl + analysis task
        if request.url:
            crawl_and_analyze_lp_task.delay(
                url=request.url,
                genre=request.genre,
                product_name=request.product_name,
                advertiser_name=request.advertiser_name,
                auto_analyze=request.auto_analyze,
                is_own=True,
                own_lp_id=lp.id,
            )
        elif request.auto_analyze and (request.text_content or request.html_content):
            # For non-URL imports, trigger analysis on the provided content
            analyze_own_lp_content_task.delay(
                lp_id=lp.id,
                genre=request.genre,
            )

        logger.info("own_lp_imported", lp_id=lp.id, label=request.label)
        return LPResponse.model_validate(lp)
    finally:
        session.close()


@router.get("/own/list", response_model=OwnLPListResponse)
async def list_own_lps(
    genre: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user_sync),
):
    """List all own (self-managed) LPs."""
    session = SyncSessionLocal()
    try:
        query = session.query(LandingPage).filter(
            LandingPage.is_own == True,  # noqa: E712
        )

        if genre:
            query = query.filter(LandingPage.genre == genre)
        if search:
            query = query.filter(
                (LandingPage.own_lp_label.ilike(f"%{search}%"))
                | (LandingPage.product_name.ilike(f"%{search}%"))
            )

        lps = query.order_by(LandingPage.created_at.desc()).all()

        # Pre-fetch competitor counts and avg quality per genre in bulk (avoid N+1)
        genres = list({lp.genre for lp in lps if lp.genre})
        genre_comp_counts: dict[str, int] = {}
        genre_avg_quality: dict[str, float | None] = {}
        if genres:
            from sqlalchemy import func as sqla_func
            # Count competitors per genre
            count_results = session.query(
                LandingPage.genre,
                sqla_func.count(LandingPage.id),
            ).filter(
                LandingPage.genre.in_(genres),
                LandingPage.is_own == False,  # noqa: E712
                LandingPage.status == "completed",
            ).group_by(LandingPage.genre).all()
            for g, c in count_results:
                genre_comp_counts[g] = c

            # Avg quality per genre
            quality_results = session.query(
                LandingPage.genre,
                sqla_func.avg(LPAnalysis.overall_quality_score),
            ).join(LPAnalysis, LPAnalysis.landing_page_id == LandingPage.id).filter(
                LandingPage.genre.in_(genres),
                LandingPage.is_own == False,  # noqa: E712
                LandingPage.status == "completed",
                LPAnalysis.overall_quality_score.isnot(None),
            ).group_by(LandingPage.genre).all()
            for g, avg_q in quality_results:
                genre_avg_quality[g] = round(float(avg_q), 1) if avg_q else None

        own_responses = []
        for lp in lps:
            resp = OwnLPResponse.model_validate(lp)
            resp.competitor_count_in_genre = genre_comp_counts.get(lp.genre, 0) if lp.genre else 0
            resp.avg_competitor_quality = genre_avg_quality.get(lp.genre) if lp.genre else None
            own_responses.append(resp)

        return OwnLPListResponse(own_lps=own_responses, total=len(own_responses))
    finally:
        session.close()


@router.put("/own/{lp_id}", response_model=LPResponse)
async def update_own_lp(
    lp_id: int,
    request: OwnLPUpdateRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Update an own LP (e.g., upload new version)."""
    session = SyncSessionLocal()
    try:
        lp = session.query(LandingPage).filter(
            LandingPage.id == lp_id,
            LandingPage.is_own == True,  # noqa: E712
        ).first()
        if not lp:
            raise HTTPException(status_code=404, detail="自社LPが見つかりません")

        if request.label:
            lp.own_lp_label = request.label
        if request.version is not None:
            lp.own_lp_version = request.version
        elif request.url or request.html_content or request.text_content:
            lp.own_lp_version = (lp.own_lp_version or 1) + 1

        if request.text_content:
            lp.full_text_content = request.text_content
            lp.word_count = len(request.text_content)
        elif request.html_content:
            lp.full_text_content = request.html_content
            lp.word_count = len(request.html_content)

        if request.url:
            lp.url = request.url
            import hashlib
            lp.url_hash = hashlib.sha256(request.url.encode()).hexdigest()
            crawl_and_analyze_lp_task.delay(
                url=request.url,
                genre=lp.genre,
                product_name=lp.product_name,
                advertiser_name=lp.advertiser_name,
                auto_analyze=request.auto_analyze,
                is_own=True,
                own_lp_id=lp.id,
            )

        session.commit()
        session.refresh(lp)
        logger.info("own_lp_updated", lp_id=lp.id, version=lp.own_lp_version)
        return LPResponse.model_validate(lp)
    finally:
        session.close()


@router.delete("/own/{lp_id}")
async def delete_own_lp(
    lp_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    """Delete an own LP."""
    session = SyncSessionLocal()
    try:
        lp = session.query(LandingPage).filter(
            LandingPage.id == lp_id,
            LandingPage.is_own == True,  # noqa: E712
        ).first()
        if not lp:
            raise HTTPException(status_code=404, detail="自社LPが見つかりません")

        session.delete(lp)
        session.commit()
        logger.info("own_lp_deleted", lp_id=lp_id)
        return {"message": f"自社LP (ID: {lp_id}) を削除しました"}
    finally:
        session.close()


@router.post("/own/compare", response_model=LPCompareResponse)
async def compare_own_lp(
    request: LPCompareRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Compare own LP against competitor LPs in the same genre."""
    session = SyncSessionLocal()
    try:
        # Get own LP
        own_lp = session.query(LandingPage).filter(
            LandingPage.id == request.own_lp_id,
            LandingPage.is_own == True,  # noqa: E712
        ).first()
        if not own_lp:
            raise HTTPException(status_code=404, detail="自社LPが見つかりません")

        genre = request.genre or own_lp.genre
        if not genre:
            raise HTTPException(status_code=400, detail="ジャンルが指定されていません")

        # Get own LP analysis
        own_analysis_obj = session.query(LPAnalysis).filter(
            LPAnalysis.landing_page_id == own_lp.id
        ).first()
        own_usps = session.query(USPPattern).filter(
            USPPattern.landing_page_id == own_lp.id
        ).all()
        own_appeals = session.query(AppealAxisAnalysis).filter(
            AppealAxisAnalysis.landing_page_id == own_lp.id
        ).all()

        own_analysis_dict = {
            "quality_score": own_analysis_obj.overall_quality_score if own_analysis_obj else 0,
            "conversion_potential": own_analysis_obj.conversion_potential_score if own_analysis_obj else 0,
            "trust_score": own_analysis_obj.trust_score if own_analysis_obj else 0,
            "page_flow": own_analysis_obj.page_flow_pattern if own_analysis_obj else "",
            "usps": [
                {"category": u.usp_category, "text": u.usp_text}
                for u in own_usps
            ],
            "appeal_axes": [
                {"axis": a.appeal_axis, "strength": a.strength_score}
                for a in own_appeals
            ],
        }

        # Get competitor LPs
        if request.competitor_lp_ids:
            comp_lps = session.query(LandingPage).filter(
                LandingPage.id.in_(request.competitor_lp_ids),
                LandingPage.status == "completed",
            ).all()
        else:
            comp_lps = session.query(LandingPage).filter(
                LandingPage.genre == genre,
                LandingPage.is_own == False,  # noqa: E712
                LandingPage.status == "completed",
            ).limit(30).all()

        # Build competitor analysis dicts (bulk fetch to avoid N+1)
        comp_lp_ids = [clp.id for clp in comp_lps]

        comp_analyses_map = {}
        if comp_lp_ids:
            all_ca = session.query(LPAnalysis).filter(LPAnalysis.landing_page_id.in_(comp_lp_ids)).all()
            comp_analyses_map = {ca.landing_page_id: ca for ca in all_ca}

        comp_usps_map: dict[int, list] = {lid: [] for lid in comp_lp_ids}
        for u in session.query(USPPattern).filter(USPPattern.landing_page_id.in_(comp_lp_ids)).all():
            comp_usps_map[u.landing_page_id].append(u)

        comp_appeals_map: dict[int, list] = {lid: [] for lid in comp_lp_ids}
        for a in session.query(AppealAxisAnalysis).filter(AppealAxisAnalysis.landing_page_id.in_(comp_lp_ids)).all():
            comp_appeals_map[a.landing_page_id].append(a)

        competitor_analyses = []
        for clp in comp_lps:
            ca = comp_analyses_map.get(clp.id)
            if not ca:
                continue
            competitor_analyses.append({
                "quality_score": ca.overall_quality_score or 0,
                "conversion_potential": ca.conversion_potential_score or 0,
                "trust_score": ca.trust_score or 0,
                "page_flow": ca.page_flow_pattern or "",
                "usps": [{"category": u.usp_category, "text": u.usp_text} for u in comp_usps_map.get(clp.id, [])],
                "appeal_axes": [{"axis": a.appeal_axis, "strength": a.strength_score} for a in comp_appeals_map.get(clp.id, [])],
            })

        # Run comparison
        comparator = LPComparator()
        try:
            result = await comparator.generate_comparison_insights(
                own_analysis=own_analysis_dict,
                competitor_analyses=competitor_analyses,
                product_name=own_lp.product_name or "",
                genre=genre,
            )
        except Exception:
            result = comparator.compare_scores(own_analysis_dict, competitor_analyses)

        return LPCompareResponse(
            own_lp=LPResponse.model_validate(own_lp),
            competitor_count=len(competitor_analyses),
            own_quality=result.own_quality,
            competitor_avg_quality=result.competitor_avg_quality,
            own_conversion=result.own_conversion,
            competitor_avg_conversion=result.competitor_avg_conversion,
            own_trust=result.own_trust,
            competitor_avg_trust=result.competitor_avg_trust,
            appeal_comparison=[
                LPCompareAxisItem(
                    axis=ac.axis,
                    own_strength=ac.own_strength,
                    competitor_avg=ac.competitor_avg,
                    gap=ac.gap,
                )
                for ac in result.appeal_comparison
            ],
            own_usps=[USPPatternResponse.model_validate(u) for u in own_usps],
            missing_usp_categories=result.missing_usp_categories,
            own_flow=result.own_flow,
            common_competitor_flows=result.common_competitor_flows,
            strengths_vs_competitors=result.strengths_vs_competitors,
            improvement_opportunities=result.improvement_opportunities,
            quick_wins=result.quick_wins,
        )
    finally:
        session.close()
