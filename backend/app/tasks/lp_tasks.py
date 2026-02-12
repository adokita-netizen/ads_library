"""LP crawl & analysis Celery tasks."""

import asyncio
from datetime import datetime, timezone

import structlog

from app.core.database import SyncSessionLocal
from app.models.landing_page import (
    AppealAxisAnalysis,
    LandingPage,
    LPAnalysis,
    LPSection,
    LPStatusEnum,
    USPPattern,
)
from app.services.lp_analysis.lp_content_analyzer import LPContentAnalyzer
from app.services.lp_analysis.lp_crawler import LPCrawler
from app.tasks.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="analysis")
def crawl_and_analyze_lp_task(
    self,
    url: str,
    ad_id: int | None = None,
    genre: str | None = None,
    product_name: str | None = None,
    advertiser_name: str | None = None,
    auto_analyze: bool = True,
):
    """Crawl a landing page and optionally run full analysis."""
    logger.info("lp_task_started", url=url, task_id=self.request.id)

    session = SyncSessionLocal()
    try:
        # Phase 1: Crawl
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        crawler = LPCrawler()
        crawled = loop.run_until_complete(crawler.crawl_lp(url))
        loop.run_until_complete(crawler.close())

        if not crawled:
            logger.error("lp_crawl_failed", url=url)
            return {"status": "failed", "error": "Crawl failed"}

        # Check for existing LP with same URL hash
        existing = session.query(LandingPage).filter(
            LandingPage.url_hash == crawled.url_hash
        ).first()

        if existing:
            lp = existing
            lp.status = LPStatusEnum.CRAWLING
        else:
            lp = LandingPage(
                url=url,
                url_hash=crawled.url_hash,
                status=LPStatusEnum.CRAWLING,
            )
            session.add(lp)

        # Populate from crawl
        lp.final_url = crawled.final_url
        lp.domain = crawled.domain
        lp.title = crawled.title
        lp.meta_description = crawled.meta_description
        lp.og_image_url = crawled.og_image
        lp.ad_id = ad_id
        lp.genre = genre
        lp.product_name = product_name
        lp.advertiser_name = advertiser_name
        lp.crawled_at = datetime.now(timezone.utc)

        # Extract page metrics
        metrics = crawler.extract_page_metrics(crawled.html_content)
        lp.word_count = metrics["word_count"]
        lp.image_count = metrics["image_count"]
        lp.video_embed_count = metrics["video_embed_count"]
        lp.form_count = metrics["form_count"]
        lp.cta_count = metrics["cta_count"]
        lp.testimonial_count = metrics["testimonial_count"]
        lp.estimated_read_time_seconds = metrics["estimated_read_time_seconds"]

        # Extract sections
        sections = crawler.extract_sections(crawled.html_content)

        # Extract hero content
        if sections:
            hero = sections[0]
            lp.hero_headline = hero.heading
            lp.hero_subheadline = hero.body_text[:200] if hero.body_text else None

        # Extract primary CTA
        for sec in sections:
            if sec.cta_text:
                lp.primary_cta_text = sec.cta_text
                break

        # Extract pricing
        prices = crawler.extract_prices(crawled.html_content)
        lp.has_pricing = len(prices) > 0
        if prices:
            lp.price_text = prices[0]["matched_text"]

        lp.total_sections = len(sections)
        lp.full_text_content = crawler.extract_text_content(crawled.html_content)[:50000]

        session.commit()
        session.refresh(lp)

        # Save sections (clear old ones first)
        session.query(LPSection).filter(LPSection.landing_page_id == lp.id).delete()
        for sec in sections:
            db_section = LPSection(
                landing_page_id=lp.id,
                section_order=sec.order,
                section_type=sec.section_type,
                heading=sec.heading,
                body_text=sec.body_text[:3000] if sec.body_text else None,
                has_image=sec.has_image,
                has_video=sec.has_video,
                has_cta=sec.has_cta,
                cta_text=sec.cta_text,
            )
            session.add(db_section)

        session.commit()
        logger.info("lp_crawl_completed", url=url, lp_id=lp.id, sections=len(sections))

        # Phase 2: Analyze (if auto_analyze)
        if auto_analyze:
            lp.status = LPStatusEnum.ANALYZING
            session.commit()

            try:
                analyzer = LPContentAnalyzer()
                sections_summary = " → ".join(s.section_type for s in sections)

                analysis_result = loop.run_until_complete(
                    analyzer.analyze_lp_full(
                        text_content=lp.full_text_content or "",
                        url=url,
                        title=lp.title or "",
                        sections_summary=sections_summary,
                        genre=genre or "",
                    )
                )

                # Save USP patterns
                session.query(USPPattern).filter(USPPattern.landing_page_id == lp.id).delete()
                for usp in analysis_result.usps:
                    db_usp = USPPattern(
                        landing_page_id=lp.id,
                        usp_category=usp.category,
                        usp_text=usp.text,
                        usp_headline=usp.headline,
                        supporting_evidence=usp.evidence,
                        prominence_score=usp.prominence,
                        position_in_page=usp.position,
                        keywords=usp.keywords,
                    )
                    session.add(db_usp)

                # Save appeal axes
                session.query(AppealAxisAnalysis).filter(
                    AppealAxisAnalysis.landing_page_id == lp.id
                ).delete()
                for appeal in analysis_result.appeal_axes:
                    db_appeal = AppealAxisAnalysis(
                        landing_page_id=lp.id,
                        appeal_axis=appeal.axis,
                        strength_score=appeal.strength,
                        evidence_texts=appeal.evidence_texts,
                    )
                    session.add(db_appeal)

                # Save LP analysis
                session.query(LPAnalysis).filter(LPAnalysis.landing_page_id == lp.id).delete()
                db_analysis = LPAnalysis(
                    landing_page_id=lp.id,
                    overall_quality_score=analysis_result.quality_score,
                    conversion_potential_score=analysis_result.conversion_potential,
                    trust_score=analysis_result.trust_score,
                    urgency_score=analysis_result.urgency_score,
                    page_flow_pattern=analysis_result.page_flow,
                    structure_summary=analysis_result.structure_summary,
                    inferred_target_gender=analysis_result.target_gender,
                    inferred_target_age_range=analysis_result.target_age_range,
                    inferred_target_concerns=analysis_result.target_concerns,
                    target_persona_summary=analysis_result.persona_summary,
                    primary_appeal_axis=analysis_result.primary_appeal,
                    secondary_appeal_axis=analysis_result.secondary_appeal,
                    appeal_strategy_summary=analysis_result.appeal_summary,
                    competitive_positioning=analysis_result.positioning,
                    differentiation_points=analysis_result.differentiation,
                    headline_effectiveness=analysis_result.headline_effectiveness,
                    cta_effectiveness=analysis_result.cta_effectiveness,
                    emotional_triggers=analysis_result.emotional_triggers,
                    power_words=analysis_result.power_words,
                    strengths=analysis_result.strengths,
                    weaknesses=analysis_result.weaknesses,
                    reusable_patterns=analysis_result.reusable_patterns,
                    improvement_suggestions=analysis_result.improvement_suggestions,
                    full_analysis_text=analysis_result.full_analysis,
                )
                session.add(db_analysis)

                lp.status = LPStatusEnum.COMPLETED
                lp.analyzed_at = datetime.now(timezone.utc)
                session.commit()

                logger.info(
                    "lp_analysis_completed",
                    lp_id=lp.id,
                    quality_score=analysis_result.quality_score,
                    usps=len(analysis_result.usps),
                    appeals=len(analysis_result.appeal_axes),
                )

            except Exception as e:
                logger.error("lp_analysis_failed", lp_id=lp.id, error=str(e))
                lp.status = LPStatusEnum.COMPLETED  # Crawl succeeded, analysis failed
                session.commit()
        else:
            lp.status = LPStatusEnum.COMPLETED
            session.commit()

        loop.close()
        return {"status": "completed", "lp_id": lp.id}

    except Exception as e:
        logger.error("lp_task_failed", url=url, error=str(e))
        session.rollback()
        raise self.retry(exc=e)
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60, queue="analysis")
def batch_crawl_lps_task(
    self,
    urls: list[str],
    genre: str | None = None,
    auto_analyze: bool = True,
):
    """Crawl multiple LPs in batch."""
    logger.info("batch_lp_task_started", url_count=len(urls), task_id=self.request.id)

    results = []
    for url in urls:
        try:
            result = crawl_and_analyze_lp_task.delay(
                url=url,
                genre=genre,
                auto_analyze=auto_analyze,
            )
            results.append({"url": url, "task_id": result.id, "status": "queued"})
        except Exception as e:
            results.append({"url": url, "error": str(e), "status": "failed"})

    return {"status": "batch_queued", "results": results}
