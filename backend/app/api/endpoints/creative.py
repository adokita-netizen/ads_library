"""Creative generation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.ad import Ad
from app.models.analysis import AdAnalysis
from app.schemas.creative import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    CopyGenerationRequest,
    CopyGenerationResponse,
    LPCopyRequest,
    LPCopyResponse,
    StoryboardRequest,
    ImprovementRequest,
    ABTestPlanRequest,
    WinningPatternRequest,
)
from app.services.generative.creative_engine import CreativeEngine
from app.services.generative.script_generator import ScriptGenerator
from app.services.generative.copy_generator import CopyGenerator

router = APIRouter(prefix="/creative", tags=["creative"])


def get_creative_engine() -> CreativeEngine:
    return CreativeEngine()


@router.post("/script", response_model=ScriptGenerationResponse)
async def generate_script(
    request: ScriptGenerationRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Generate a video ad script."""
    reference_analysis = None
    if request.reference_ad_id:
        result = await db.execute(
            select(AdAnalysis).where(AdAnalysis.ad_id == request.reference_ad_id)
        )
        analysis = result.scalar_one_or_none()
        if analysis:
            reference_analysis = {
                "sentiment": analysis.overall_sentiment,
                "keywords": analysis.keywords,
                "cta": analysis.cta_text,
                "hook_type": analysis.hook_type,
            }

    generator = ScriptGenerator()
    script = await generator.generate_script(
        product_name=request.product_name,
        product_description=request.product_description,
        target_audience=request.target_audience,
        duration_seconds=request.duration_seconds,
        structure=request.structure,
        appeal_axis=request.appeal_axis,
        platform=request.platform,
        tone=request.tone,
        reference_analysis=reference_analysis,
        language=request.language,
    )

    return ScriptGenerationResponse(**script.to_dict())


@router.post("/copy", response_model=CopyGenerationResponse)
async def generate_ad_copy(request: CopyGenerationRequest):
    """Generate ad copy variations."""
    generator = CopyGenerator()
    copies = await generator.generate_ad_copy(
        product_name=request.product_name,
        product_description=request.product_description,
        target_audience=request.target_audience,
        platform=request.platform,
        appeal_axis=request.appeal_axis,
        tone=request.tone,
        num_variations=request.num_variations,
        reference_keywords=request.reference_keywords,
    )

    return CopyGenerationResponse(copies=[c.to_dict() for c in copies])


@router.post("/lp-copy", response_model=LPCopyResponse)
async def generate_lp_copy(
    request: LPCopyRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Generate landing page copy."""
    reference_analysis = None
    if request.reference_ad_id:
        result = await db.execute(
            select(AdAnalysis).where(AdAnalysis.ad_id == request.reference_ad_id)
        )
        analysis = result.scalar_one_or_none()
        if analysis and analysis.raw_analysis:
            reference_analysis = analysis.raw_analysis

    generator = CopyGenerator()
    lp_copy = await generator.generate_lp_copy(
        product_name=request.product_name,
        product_description=request.product_description,
        target_audience=request.target_audience,
        appeal_axis=request.appeal_axis,
        reference_analysis=reference_analysis,
    )

    return LPCopyResponse(**lp_copy.to_dict())


@router.post("/storyboard")
async def generate_storyboard(request: StoryboardRequest):
    """Generate a video storyboard."""
    engine = get_creative_engine()
    storyboard = await engine.generate_storyboard(
        product_name=request.product_name,
        product_description=request.product_description,
        target_audience=request.target_audience,
        duration_seconds=request.duration_seconds,
        platform=request.platform,
        style=request.style,
    )

    return storyboard.to_dict()


@router.post("/improvements")
async def suggest_improvements(
    request: ImprovementRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Get improvement suggestions for an ad."""
    result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id == request.ad_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found for this ad")

    engine = get_creative_engine()
    suggestions = await engine.suggest_improvements(
        ad_analysis=analysis.raw_analysis or {},
        current_metrics=request.current_metrics,
    )

    return {
        "ad_id": request.ad_id,
        "suggestions": [
            {
                "category": s.category,
                "current_state": s.current_state,
                "suggestion": s.suggestion,
                "priority": s.priority,
                "expected_impact": s.expected_impact,
            }
            for s in suggestions
        ],
    }


@router.post("/ab-test-plan")
async def generate_ab_test_plan(
    request: ABTestPlanRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Generate an A/B test plan."""
    result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id == request.ad_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found for this ad")

    engine = get_creative_engine()
    plan = await engine.generate_ab_test_plan(
        base_creative=analysis.raw_analysis or {},
        test_variables=request.test_variables,
        num_variations=request.num_variations,
    )

    return {"ad_id": request.ad_id, **plan}


@router.post("/winning-pattern")
async def rewrite_winning_pattern(
    request: WinningPatternRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Rewrite using a winning ad's pattern."""
    result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id == request.winning_ad_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Winning ad analysis not found")

    winning_text = analysis.full_transcript or ""
    if not winning_text:
        raise HTTPException(status_code=400, detail="Winning ad has no transcript")

    generator = CopyGenerator()
    copies = await generator.rewrite_winning_pattern(
        winning_ad_text=winning_text,
        new_product_name=request.new_product_name,
        new_product_description=request.new_product_description,
        platform=request.platform,
    )

    return {"copies": [c.to_dict() for c in copies]}


@router.get("/structures")
async def list_script_structures():
    """List available script structures."""
    generator = ScriptGenerator()
    return {"structures": generator.get_available_structures()}
