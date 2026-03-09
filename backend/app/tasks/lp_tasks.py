"""LP crawl & analysis Celery tasks."""

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import structlog
from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, normalize_lp_fetch_error_code
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

_LP_HTML_CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "media_cache", "lp_html")
)


def _save_lp_html_cache(ad_id: int | None, html_content: str | None) -> str | None:
    if not ad_id or not html_content:
        return None
    try:
        os.makedirs(_LP_HTML_CACHE_DIR, exist_ok=True)
        path = os.path.join(_LP_HTML_CACHE_DIR, f"{ad_id}.html")
        with open(path, "w", encoding="utf-8", errors="ignore") as fh:
            fh.write(html_content)
        return path
    except OSError as exc:
        logger.warning("lp_html_cache_save_failed", ad_id=ad_id, error=str(exc)[:200])
        return None


def _load_cached_lp_html_path(ad_id: int | None) -> str | None:
    if not ad_id:
        return None
    path = os.path.join(_LP_HTML_CACHE_DIR, f"{ad_id}.html")
    return path if os.path.exists(path) else None


def _load_lp_analysis_summary(session, lp_id: int):
    analysis = session.query(LPAnalysis).filter(LPAnalysis.landing_page_id == lp_id).first()
    if analysis is None:
        return None
    return SimpleNamespace(
        quality_score=analysis.overall_quality_score,
        conversion_potential=analysis.conversion_potential_score,
        trust_score=analysis.trust_score,
        urgency_score=analysis.urgency_score,
        page_flow=analysis.page_flow_pattern,
        structure_summary=analysis.structure_summary,
        primary_appeal=analysis.primary_appeal_axis,
        secondary_appeal=analysis.secondary_appeal_axis,
        cta_effectiveness=analysis.cta_effectiveness,
        headline_effectiveness=analysis.headline_effectiveness,
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        reusable_patterns=analysis.reusable_patterns,
        improvement_suggestions=analysis.improvement_suggestions,
    )


def reuse_existing_lp_for_ad(
    session,
    *,
    ad_id: int | None,
    url: str,
) -> bool:
    if not ad_id or not url:
        return False

    url_hash = hashlib.sha256(url.encode()).hexdigest()
    lp = (
        session.query(LandingPage)
        .filter(
            or_(
                LandingPage.url_hash == url_hash,
                LandingPage.url == url,
                LandingPage.final_url == url,
            )
        )
        .order_by(LandingPage.analyzed_at.desc(), LandingPage.crawled_at.desc(), LandingPage.id.desc())
        .first()
    )
    if lp is None or not lp.full_text_content:
        return False

    status_code = None
    redirect_chain: list[str] = []
    if isinstance(lp.lp_metadata, dict):
        raw_status = lp.lp_metadata.get("http_status")
        status_code = int(raw_status) if raw_status not in (None, "") else None
        redirect_chain = list(lp.lp_metadata.get("redirect_chain") or [])

    crawled = SimpleNamespace(
        final_url=lp.final_url or lp.url or url,
        status_code=status_code,
        redirect_chain=redirect_chain,
    )
    _sync_lp_success_to_ad(
        session,
        ad_id=ad_id,
        url=url,
        crawled=crawled,
        lp=lp,
        html_path=_load_cached_lp_html_path(lp.ad_id),
        analysis_result=_load_lp_analysis_summary(session, lp.id),
    )
    return True


def _sync_lp_failure_to_ad(
    session,
    *,
    ad_id: int | None,
    url: str,
    status: str,
    error_code: str,
    error_message: str,
) -> None:
    if not ad_id:
        return
    ad = session.query(Ad).filter(Ad.id == ad_id).first()
    if ad is None:
        return

    meta = dict(ad.ad_metadata or {})
    meta["lp_status"] = status
    meta["lp_fetch_status"] = status
    meta["lp_fetch_error_code"] = normalize_lp_fetch_error_code(error_code) or "unknown"
    meta["lp_fetch_reason"] = error_code
    meta["lp_checked_at"] = datetime.now(timezone.utc).isoformat()
    meta["last_lp_fetch_at"] = meta["lp_checked_at"]
    meta.setdefault("lp_info", {})
    meta["lp_info"] = {
        **(meta["lp_info"] if isinstance(meta.get("lp_info"), dict) else {}),
        "final_url": ad.destination_url or url,
    }
    if error_message:
        meta["lp_error_message"] = error_message[:500]
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")
    session.commit()


def _sync_lp_success_to_ad(
    session,
    *,
    ad_id: int | None,
    url: str,
    crawled,
    lp: LandingPage,
    html_path: str | None,
    analysis_result=None,
) -> None:
    if not ad_id:
        return
    ad = session.query(Ad).filter(Ad.id == ad_id).first()
    if ad is None:
        return

    fetched_at = datetime.now(timezone.utc).isoformat()
    http_status = int(crawled.status_code) if getattr(crawled, "status_code", None) else None
    lp_info = {
        "final_url": lp.final_url or crawled.final_url or ad.destination_url or url,
        "http_status": http_status,
        "title": lp.title or "",
        "description": lp.meta_description or "",
        "canonical": ((lp.lp_metadata or {}).get("canonical") if isinstance(lp.lp_metadata, dict) else None),
        "og_image": lp.og_image_url or "",
        "lang": ((lp.lp_metadata or {}).get("lang") if isinstance(lp.lp_metadata, dict) else None),
        "fetched_at": fetched_at,
    }
    lp_info = {key: value for key, value in lp_info.items() if value not in (None, "", [])}
    lp_data = {
        "url": url,
        "final_url": lp.final_url or crawled.final_url or ad.destination_url or url,
        "title": lp.title or "",
        "meta_description": lp.meta_description or "",
        "description": lp.meta_description or "",
        "og_image": lp.og_image_url or "",
        "canonical": ((lp.lp_metadata or {}).get("canonical") if isinstance(lp.lp_metadata, dict) else None),
        "status_code": http_status,
        "crawled_at": fetched_at,
        "html_path": html_path,
        "word_count": lp.word_count,
        "image_count": lp.image_count,
        "video_embed_count": lp.video_embed_count,
        "form_count": lp.form_count,
        "cta_count": lp.cta_count,
        "testimonial_count": lp.testimonial_count,
        "total_sections": lp.total_sections,
        "full_text_content": lp.full_text_content or "",
        "hero_headline": lp.hero_headline or "",
        "hero_subheadline": lp.hero_subheadline or "",
        "primary_cta_text": lp.primary_cta_text or "",
        "price_text": lp.price_text or "",
        "has_pricing": bool(lp.has_pricing),
        "redirect_chain": list(getattr(crawled, "redirect_chain", []) or []),
    }
    lp_data = {key: value for key, value in lp_data.items() if value not in (None, "", [])}

    meta = dict(ad.ad_metadata or {})
    meta["lp_status"] = str(http_status or "alive")
    meta["lp_fetch_status"] = "success"
    meta["lp_checked_at"] = fetched_at
    meta["lp_snapshot_at"] = fetched_at
    meta["last_lp_fetch_at"] = fetched_at
    meta["lp_final_url"] = lp_data["final_url"]
    meta["lp_info"] = lp_info
    meta["lp_data"] = lp_data
    meta["destination_url"] = ad.destination_url or lp_data["final_url"]
    meta.setdefault("destination_type", "LP")
    meta.pop("lp_fetch_error_code", None)
    meta.pop("lp_fetch_reason", None)
    meta.pop("lp_error_message", None)
    if analysis_result is not None:
        meta["lp_score"] = analysis_result.quality_score
        meta["lp_score_source"] = "lp_analysis"
        meta["lp_analysis"] = {
            "final_url": lp_data["final_url"],
            "title": lp.title or "",
            "description": lp.meta_description or "",
            "og_image": lp.og_image_url or "",
            "fetched_at": fetched_at,
            "quality_score": analysis_result.quality_score,
            "conversion_potential_score": analysis_result.conversion_potential,
            "trust_score": analysis_result.trust_score,
            "urgency_score": analysis_result.urgency_score,
            "page_flow_pattern": analysis_result.page_flow,
            "structure_summary": analysis_result.structure_summary,
            "primary_appeal_axis": analysis_result.primary_appeal,
            "secondary_appeal_axis": analysis_result.secondary_appeal,
            "cta_effectiveness": analysis_result.cta_effectiveness,
            "headline_effectiveness": analysis_result.headline_effectiveness,
            "strengths": analysis_result.strengths,
            "weaknesses": analysis_result.weaknesses,
            "reusable_patterns": analysis_result.reusable_patterns,
            "improvement_suggestions": analysis_result.improvement_suggestions,
        }
    ad.destination_url = ad.destination_url or lp_data["final_url"]
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")
    session.commit()


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
        if reuse_existing_lp_for_ad(session, ad_id=ad_id, url=url):
            ad = session.query(Ad).filter(Ad.id == ad_id).first() if ad_id else None
            logger.info(
                "lp_reused_for_ad",
                url=url,
                ad_id=ad_id,
                final_url=(ad.destination_url if ad else url),
            )
            return {"status": "completed", "reused": True}

        # Phase 1: Crawl
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        crawler = LPCrawler()
        crawled = loop.run_until_complete(crawler.crawl_lp(url))
        loop.run_until_complete(crawler.close())

        if not crawled:
            logger.error("lp_crawl_failed", url=url)
            # Update DB status to FAILED so the user can see the failure
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            existing_lp = session.query(LandingPage).filter(
                LandingPage.url_hash == url_hash
            ).first()
            if existing_lp:
                existing_lp.status = LPStatusEnum.FAILED
                existing_lp.error_message = "クロールに失敗しました。URLが無効またはアクセスできません。"
                session.commit()
            else:
                failed_lp = LandingPage(
                    url=url,
                    url_hash=url_hash,
                    status=LPStatusEnum.FAILED,
                    error_message="クロールに失敗しました。URLが無効またはアクセスできません。",
                )
                session.add(failed_lp)
                session.commit()
            _sync_lp_failure_to_ad(
                session,
                ad_id=ad_id,
                url=url,
                status="unreachable",
                error_code="unknown",
                error_message="クロールに失敗しました。URLが無効またはアクセスできません。",
            )
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
        raw_text = crawler.extract_text_content(crawled.html_content)
        if len(raw_text) > 50000:
            logger.warning(
                "lp_content_truncated",
                url=url,
                original_length=len(raw_text),
                truncated_to=50000,
            )
        lp.full_text_content = raw_text[:50000]
        lp.lp_metadata = {
            **(lp.lp_metadata or {}),
            "canonical": crawler._extract_canonical(crawled.html_content),
            "lang": crawler._extract_html_lang(crawled.html_content),
            "http_status": crawled.status_code,
            "redirect_chain": list(crawled.redirect_chain or []),
            "headers": dict(crawled.headers or {}),
        }

        session.commit()
        session.refresh(lp)
        html_path = _save_lp_html_cache(ad_id, crawled.html_content)
        _sync_lp_success_to_ad(
            session,
            ad_id=ad_id,
            url=url,
            crawled=crawled,
            lp=lp,
            html_path=html_path,
        )

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
                _sync_lp_success_to_ad(
                    session,
                    ad_id=ad_id,
                    url=url,
                    crawled=crawled,
                    lp=lp,
                    html_path=html_path,
                    analysis_result=analysis_result,
                )

                logger.info(
                    "lp_analysis_completed",
                    lp_id=lp.id,
                    quality_score=analysis_result.quality_score,
                    usps=len(analysis_result.usps),
                    appeals=len(analysis_result.appeal_axes),
                )

            except Exception as e:
                logger.error("lp_analysis_failed", lp_id=lp.id, error=str(e))
                lp.status = LPStatusEnum.FAILED
                lp.error_message = f"分析エラー: {str(e)[:500]}"
                session.commit()
                _sync_lp_failure_to_ad(
                    session,
                    ad_id=ad_id,
                    url=url,
                    status="alive",
                    error_code="unknown",
                    error_message=f"分析エラー: {str(e)[:500]}",
                )
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="analysis")
def analyze_own_lp_content_task(
    self,
    lp_id: int,
    genre: str | None = None,
):
    """Analyze an already-imported own LP (text/HTML content, no crawl needed)."""
    logger.info("own_lp_analysis_started", lp_id=lp_id, task_id=self.request.id)

    session = SyncSessionLocal()
    try:
        lp = session.query(LandingPage).filter(LandingPage.id == lp_id).first()
        if not lp:
            return {"status": "failed", "error": f"LP {lp_id} not found"}

        if not lp.full_text_content:
            lp.status = LPStatusEnum.COMPLETED
            session.commit()
            return {"status": "completed", "lp_id": lp_id, "note": "No content to analyze"}

        lp.status = LPStatusEnum.ANALYZING
        session.commit()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analyzer = LPContentAnalyzer()
            analysis_result = loop.run_until_complete(
                analyzer.analyze_lp_full(
                    text_content=lp.full_text_content,
                    url=lp.url or "",
                    title=lp.title or lp.own_lp_label or "",
                    sections_summary="",
                    genre=genre or lp.genre or "",
                )
            )

            # Save USP patterns
            session.query(USPPattern).filter(USPPattern.landing_page_id == lp.id).delete()
            for usp in analysis_result.usps:
                session.add(USPPattern(
                    landing_page_id=lp.id,
                    usp_category=usp.category,
                    usp_text=usp.text,
                    usp_headline=usp.headline,
                    supporting_evidence=usp.evidence,
                    prominence_score=usp.prominence,
                    position_in_page=usp.position,
                    keywords=usp.keywords,
                ))

            # Save appeal axes
            session.query(AppealAxisAnalysis).filter(
                AppealAxisAnalysis.landing_page_id == lp.id
            ).delete()
            for appeal in analysis_result.appeal_axes:
                session.add(AppealAxisAnalysis(
                    landing_page_id=lp.id,
                    appeal_axis=appeal.axis,
                    strength_score=appeal.strength,
                    evidence_texts=appeal.evidence_texts,
                ))

            # Save analysis
            session.query(LPAnalysis).filter(LPAnalysis.landing_page_id == lp.id).delete()
            session.add(LPAnalysis(
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
            ))

            lp.status = LPStatusEnum.COMPLETED
            lp.analyzed_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("own_lp_analysis_completed", lp_id=lp.id)
            return {"status": "completed", "lp_id": lp.id}

        finally:
            loop.close()

    except Exception as e:
        logger.error("own_lp_analysis_failed", lp_id=lp_id, error=str(e))
        session.rollback()
        if self.request.retries >= self.max_retries:
            # Max retries reached — mark LP as FAILED
            try:
                fail_session = SyncSessionLocal()
                fail_lp = fail_session.query(LandingPage).filter(LandingPage.id == lp_id).first()
                if fail_lp:
                    fail_lp.status = LPStatusEnum.FAILED
                    fail_lp.error_message = f"分析が最大リトライ回数に達して失敗しました: {str(e)[:500]}"
                    fail_session.commit()
                fail_session.close()
            except Exception:
                pass
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

    from app.tasks.dispatcher import dispatch_task

    results = []
    for url in urls:
        try:
            result = dispatch_task(
                "crawl_and_analyze_lp",
                url=url,
                genre=genre,
                auto_analyze=auto_analyze,
            )
            results.append({"url": url, "task_id": result.id, "status": "queued"})
        except Exception as e:
            results.append({"url": url, "error": str(e), "status": "failed"})

    return {"status": "batch_queued", "results": results}
