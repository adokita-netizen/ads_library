"""Ad crawling Celery tasks."""

import asyncio
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy import text

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, MediaExtractionStatus
from app.services.crawling.crawler_manager import CrawlerManager

try:
    from app.tasks.worker import celery_app
except ImportError:
    # Celery not installed — provide a no-op decorator so the module still loads
    class _FakeCelery:
        def task(self, *a, **kw):
            def decorator(fn):
                fn.delay = lambda *a2, **kw2: None
                fn.apply_async = lambda *a2, **kw2: None
                return fn
            return decorator
    celery_app = _FakeCelery()

logger = structlog.get_logger()


_DOMAIN_ONLY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}(/.*)?$")


def _normalize_destination_url(raw: str | None) -> str | None:
    """Normalize destination URL and unwrap common redirectors."""
    if not raw:
        return None
    url = str(raw).strip()
    if not url:
        return None

    # Decode repeatedly (at most 2 passes) for nested URL encoding.
    for _ in range(2):
        dec = urllib.parse.unquote(url)
        if dec == url:
            break
        url = dec

    # Handle domain-only strings (e.g. example.com/path).
    if not url.startswith(("http://", "https://")):
        if _DOMAIN_ONLY_RE.match(url):
            url = f"https://{url}"
        else:
            return None

    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()

    # Unwrap Meta redirect links like l.facebook.com/l.php?u=<real_url>.
    if "facebook.com" in host and parsed.path.startswith("/l.php"):
        qs = urllib.parse.parse_qs(parsed.query)
        inner = qs.get("u", [None])[0] or qs.get("url", [None])[0]
        if inner:
            return _normalize_destination_url(inner)

    # Exclude internal social URLs; keep external LP only.
    internal_hosts = ("facebook.com", "fb.com")
    if any(host == h or host.endswith(f".{h}") for h in internal_hosts):
        return None

    return url


def _extract_destination_url(crawled_ad) -> str | None:
    """Extract best-effort destination URL from fields and metadata."""
    meta = crawled_ad.metadata or {}
    candidates: list[str] = []
    for key in ("destination_url", "link_url", "website_url", "display_url"):
        v = meta.get(key)
        if isinstance(v, str) and v.strip():
            candidates.append(v)
    if isinstance(meta.get("all_external_links"), list):
        candidates.extend([x for x in meta["all_external_links"] if isinstance(x, str)])
    if crawled_ad.destination_url:
        candidates.insert(0, crawled_ad.destination_url)

    for raw in candidates:
        normalized = _normalize_destination_url(raw)
        if normalized:
            return normalized
    return None


def validate_crawled_ad(crawled_ad) -> list[str]:
    """CI-131: Validate crawled ad data before DB insert.

    Returns list of validation errors. Empty list means valid.
    """
    errors = []

    # Required: external_id
    if not crawled_ad.external_id or not str(crawled_ad.external_id).strip():
        errors.append("missing_external_id")

    # URL validation
    for url_attr in ("video_url", "thumbnail_url", "snapshot_url", "destination_url"):
        url = getattr(crawled_ad, url_attr, None)
        if url and not str(url).startswith(("http://", "https://")):
            errors.append(f"invalid_url_{url_attr}")

    for img_url in (crawled_ad.image_urls or []):
        if img_url and not str(img_url).startswith(("http://", "https://")):
            errors.append("invalid_image_url")
            break

    # Numeric range checks
    if crawled_ad.view_count is not None and crawled_ad.view_count < 0:
        errors.append("negative_view_count")
    if crawled_ad.like_count is not None and crawled_ad.like_count < 0:
        errors.append("negative_like_count")
    if crawled_ad.duration_seconds is not None and crawled_ad.duration_seconds < 0:
        errors.append("negative_duration")

    # Title/description length sanity
    if crawled_ad.title and len(crawled_ad.title) > 5000:
        errors.append("title_too_long")
    if crawled_ad.description and len(crawled_ad.description) > 50000:
        errors.append("description_too_long")

    return errors


def _extract_text_fallback(crawled_ad) -> tuple[str | None, str | None]:
    """Fill title/description from metadata if crawler fields are empty."""
    title = crawled_ad.title
    description = crawled_ad.description
    meta = crawled_ad.metadata or {}

    if not description:
        desc_candidates = (
            meta.get("ad_creative_bodies"),
            meta.get("original_ad_creative_bodies"),
            meta.get("link_descriptions"),
        )
        for item in desc_candidates:
            if isinstance(item, list) and item:
                val = str(item[0]).strip()
                if val:
                    description = val
                    break
            elif isinstance(item, str) and item.strip():
                description = item.strip()
                break

    if not title:
        title_candidates = (
            meta.get("ad_creative_link_titles"),
            meta.get("link_titles"),
        )
        for item in title_candidates:
            if isinstance(item, list) and item:
                val = str(item[0]).strip()
                if val:
                    title = val
                    break
            elif isinstance(item, str) and item.strip():
                title = item.strip()
                break

    if not title and description:
        title = description.split("\n")[0].strip()[:80] or None

    return title, description


# ── Genre Rotation for Scheduled Crawls ──────────────────────

GENRE_KEYWORDS = {
    "diet": ["ダイエット", "痩せる", "GLP-1", "医療ダイエット", "メディカルダイエット", "減量"],
    "fitness": ["ジム", "パーソナルジム", "パーソナルトレーニング", "フィットネス"],
    "meo": ["MEO対策", "MEO", "Googleマップ 集客", "Google口コミ"],
    "glass": ["窓ガラスフィルム", "窓ガラス", "ガラスコーティング", "窓 断熱"],
}


def get_today_keywords() -> list[str]:
    """Return all keyword list — all genres every day."""
    all_keywords = []
    for kws in GENRE_KEYWORDS.values():
        all_keywords.extend(kws)
    return all_keywords


def is_duplicate_crawl(session, keyword: str, hours: int = 6) -> bool:
    """Check if the same keyword was crawled within the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    try:
        recent = session.execute(
            text(
                "SELECT COUNT(*) FROM ads "
                "WHERE ad_metadata->>'last_crawl_keyword' = :keyword "
                "AND updated_at > :cutoff"
            ),
            {"keyword": keyword, "cutoff": cutoff},
        ).scalar()
        return recent > 0
    except Exception:
        # SQLite doesn't support ->> operator; skip guard
        return False


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def crawl_ads_task(
    self,
    query: str,
    platforms: list[str],
    category: str | None = None,
    limit_per_platform: int = 20,
    auto_analyze: bool = False,
    country: str = "JP",
):
    """Crawl ads from multiple platforms."""
    # CI-046: Generate run_id for end-to-end traceability
    run_id = str(uuid.uuid4())[:8]

    # CI-038: Prevent duplicate concurrent crawl jobs
    from app.core.database import acquire_job_lock, release_job_lock
    lock_name = f"crawl:{query}"
    if not acquire_job_lock(lock_name, ttl=600):
        logger.warning("crawl_task_skipped_duplicate", query=query, run_id=run_id)
        return {"status": "skipped", "reason": "duplicate_job_running"}

    logger.info(
        "crawl_task_started",
        run_id=run_id,
        query=query,
        platforms=platforms,
        task_id=self.request.id,
    )

    # Create or update CrawlJob for progress tracking
    job_id = self.request.id or str(uuid.uuid4())
    progress_session = SyncSessionLocal()
    try:
        from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
        crawl_job = CrawlJob(
            job_id=job_id,
            status=CrawlJobStatusEnum.RUNNING,
            query=query,
            platforms=platforms,
            total_platforms=len(platforms),
            completed_platforms=0,
            total_ads_found=0,
        )
        progress_session.add(crawl_job)
        progress_session.commit()
    except Exception as pex:
        logger.warning("crawl_job_create_failed", error=str(pex))
    finally:
        progress_session.close()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            _crawl_platforms(query, platforms, category, limit_per_platform, country)
        )
        loop.close()

        # Save results to database
        session = SyncSessionLocal()
        saved_count = 0

        try:
            for platform, crawled_ads in results.items():
                for crawled_ad in crawled_ads:
                    # CI-131: Schema validation before DB insert
                    validation_errors = validate_crawled_ad(crawled_ad)
                    if validation_errors:
                        logger.warning("crawled_ad_validation_failed",
                                       external_id=crawled_ad.external_id,
                                       errors=validation_errors)
                        continue

                    # Check for duplicates — merge new data into existing
                    if crawled_ad.external_id:
                        existing = session.query(Ad).filter(
                            Ad.external_id == crawled_ad.external_id
                        ).first()
                        if existing:
                            _merge_crawled_data(existing, crawled_ad, session)
                            continue

                    platform_enum = _map_platform(platform)

                    # Warn on ads with no media or title
                    has_media = bool(crawled_ad.image_urls or crawled_ad.video_url or crawled_ad.snapshot_url)
                    if not crawled_ad.title and not has_media:
                        logger.warning(
                            "ad_missing_title_and_media",
                            platform=platform,
                            external_id=crawled_ad.external_id,
                            advertiser=crawled_ad.advertiser_name,
                        )

                    # Determine media extraction status:
                    # Skip extraction if crawler already provided direct media URLs
                    has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                    if has_direct_media:
                        extraction_status = MediaExtractionStatus.SKIPPED
                    elif crawled_ad.snapshot_url:
                        extraction_status = MediaExtractionStatus.PENDING
                    else:
                        extraction_status = MediaExtractionStatus.SKIPPED

                    # Extract destination_url robustly from direct field + metadata candidates
                    dest_url = _extract_destination_url(crawled_ad)
                    title, description = _extract_text_fallback(crawled_ad)
                    meta = dict(crawled_ad.metadata or {})
                    if dest_url:
                        meta["destination_url"] = dest_url
                        meta.setdefault("destination_type", "LP")

                    # Map category string to enum (best effort)
                    ad_category = None
                    if crawled_ad.category:
                        from app.models.ad import AdCategoryEnum
                        try:
                            ad_category = AdCategoryEnum(crawled_ad.category)
                        except ValueError:
                            ad_category = AdCategoryEnum.OTHER

                    ad = Ad(
                        external_id=crawled_ad.external_id,
                        title=title,
                        description=description,
                        platform=platform_enum,
                        creative_type=crawled_ad.creative_type,
                        video_url=crawled_ad.video_url,
                        snapshot_url=crawled_ad.snapshot_url,
                        thumbnail_url=crawled_ad.thumbnail_url,
                        image_url=crawled_ad.image_urls[0] if crawled_ad.image_urls else None,
                        image_s3_keys={"urls": crawled_ad.image_urls} if len(crawled_ad.image_urls) > 1 else None,
                        destination_url=dest_url,
                        category=ad_category,
                        media_extraction_status=extraction_status,
                        advertiser_name=crawled_ad.advertiser_name,
                        advertiser_url=crawled_ad.advertiser_url,
                        brand_name=crawled_ad.brand_name,
                        duration_seconds=crawled_ad.duration_seconds,
                        view_count=crawled_ad.view_count,
                        like_count=crawled_ad.like_count,
                        spend=crawled_ad.spend,
                        impressions=crawled_ad.impressions,
                        reach=crawled_ad.reach,
                        cpc=crawled_ad.cpc,
                        cpm=crawled_ad.cpm,
                        frequency=crawled_ad.frequency,
                        first_seen_at=crawled_ad.first_seen_at,
                        last_seen_at=crawled_ad.last_seen_at,
                        tags=crawled_ad.tags,
                        ad_metadata=meta,
                        status=AdStatusEnum.PENDING,
                    )
                    session.add(ad)
                    saved_count += 1

            session.commit()

            # Dispatch lightweight enrichment for ads that need it
            # enrich_ad_creative (LIGHT → Lambda) tries HTTP+BS4 first,
            # then escalates to extract_media (HEAVY → ECS+Playwright) on failure.
            from app.tasks.dispatcher import dispatch_task
            ads_with_snapshot = session.query(Ad).filter(
                Ad.media_extraction_status == MediaExtractionStatus.PENDING,
                Ad.snapshot_url.isnot(None),
            ).order_by(Ad.created_at.desc()).limit(saved_count).all()
            for ad_to_extract in ads_with_snapshot:
                try:
                    dispatch_task("enrich_ad_creative", ad_id=ad_to_extract.id)
                except Exception as e:
                    logger.warning(
                        "enrich_dispatch_failed_trying_inline",
                        ad_id=ad_to_extract.id, error=str(e),
                    )
                    # Inline fallback: try HTTP+BS4 enrichment directly
                    _inline_enrich(ad_to_extract, session)

            # Dispatch thumbnail download for ads that have thumbnail_url but skipped extraction
            ads_needing_thumb = session.query(Ad).filter(
                Ad.media_extraction_status == MediaExtractionStatus.SKIPPED,
                Ad.thumbnail_url.isnot(None),
                Ad.thumbnail_s3_key.is_(None),
            ).order_by(Ad.created_at.desc()).limit(saved_count).all()
            for ad_thumb in ads_needing_thumb:
                try:
                    dispatch_task("download_thumbnail", ad_id=ad_thumb.id)
                except Exception as e:
                    logger.warning("thumbnail_dispatch_failed", ad_id=ad_thumb.id, error=str(e))

            # Inline video download for ads with video_url
            _inline_download_videos(session, saved_count)

            # Auto-analyze if requested
            if auto_analyze:
                ads_to_analyze = session.query(Ad).filter(
                    Ad.status == AdStatusEnum.PENDING,
                    Ad.video_url.isnot(None),
                ).order_by(Ad.created_at.desc()).limit(limit_per_platform * len(platforms)).all()

                for ad in ads_to_analyze:
                    dispatch_task("analyze_ad", ad_id=ad.id)
                    ad.status = AdStatusEnum.PROCESSING

                session.commit()

            logger.info("crawl_task_completed", run_id=run_id, query=query, saved_count=saved_count)

            # Update CrawlJob to COMPLETED
            pses = SyncSessionLocal()
            try:
                from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
                cj = pses.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()
                if cj:
                    cj.status = CrawlJobStatusEnum.COMPLETED
                    cj.completed_platforms = len(platforms)
                    cj.total_ads_found = saved_count
                    cj.current_platform = None
                    pses.commit()
            except Exception:
                pass
            finally:
                pses.close()

            release_job_lock(lock_name)
            return {"status": "completed", "saved_count": saved_count, "job_id": job_id, "run_id": run_id}

        finally:
            session.close()

    except Exception as e:
        release_job_lock(lock_name)
        logger.error("crawl_task_failed", run_id=run_id, query=query, error=str(e))
        # CI-004: Classify failure reason
        from app.models.crawl_job import CrawlFailureReason
        err_str = str(e).lower()
        if "timeout" in err_str:
            failure_reason = CrawlFailureReason.TIMEOUT
        elif "429" in err_str or "rate" in err_str:
            failure_reason = CrawlFailureReason.RATE_LIMIT
        elif "401" in err_str or "token" in err_str or "auth" in err_str:
            failure_reason = CrawlFailureReason.AUTH_EXPIRED
        elif "parse" in err_str or "json" in err_str or "decode" in err_str:
            failure_reason = CrawlFailureReason.PARSE_ERROR
        elif "connect" in err_str or "network" in err_str or "dns" in err_str:
            failure_reason = CrawlFailureReason.NETWORK_ERROR
        elif "browser" in err_str or "chromium" in err_str or "playwright" in err_str:
            failure_reason = CrawlFailureReason.BROWSER_CRASH
        else:
            failure_reason = CrawlFailureReason.UNKNOWN
        # Update CrawlJob to FAILED
        fses = SyncSessionLocal()
        try:
            from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
            cj = fses.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()
            if cj:
                cj.status = CrawlJobStatusEnum.FAILED
                cj.error_message = str(e)[:500]
                cj.failure_reason = failure_reason.value
                fses.commit()
        except Exception:
            pass
        finally:
            fses.close()
        raise self.retry(exc=e)


def get_connected_platforms() -> list[str]:
    """Return list of platform names that have at least one API key configured."""
    from app.core.config import get_settings
    settings = get_settings()

    db_keys: dict[str, dict[str, str]] = {}
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        db_keys = load_api_keys_from_db()
    except Exception:
        pass

    def _has(platform: str, key_name: str, env_fallback: str | None) -> bool:
        val = db_keys.get(platform, {}).get(key_name) or env_fallback
        return bool(val and val.strip())

    connected = []
    # Meta covers both facebook and instagram
    if _has("meta", "access_token", settings.meta_access_token):
        connected.extend(["facebook", "instagram"])
    if _has("youtube", "api_key", settings.youtube_api_key):
        connected.append("youtube")
    if _has("tiktok", "access_token", settings.tiktok_access_token):
        connected.append("tiktok")
    if _has("x_twitter", "bearer_token", settings.x_twitter_bearer_token):
        connected.append("x_twitter")
    if _has("line", "access_token", settings.line_api_access_token):
        connected.append("line")
    if _has("yahoo", "api_key", settings.yahoo_ads_api_key):
        connected.append("yahoo")
    if _has("pinterest", "access_token", settings.pinterest_access_token):
        connected.append("pinterest")
    if _has("smartnews", "api_key", settings.smartnews_ads_api_key):
        connected.append("smartnews")
    if _has("google_ads", "developer_token", settings.google_ads_developer_token):
        connected.append("google_ads")
    if _has("gunosy", "api_key", settings.gunosy_ads_api_key):
        connected.append("gunosy")

    return connected


async def _crawl_platforms(
    query: str,
    platforms: list[str],
    category: str | None,
    limit_per_platform: int,
    country: str = "JP",
) -> dict:
    """Run async crawling with API keys from DB (fallback to env vars)."""
    from app.core.config import get_settings
    from app.services.crawling.base_crawler import BaseCrawler
    settings = get_settings()

    # CI-064: Log source health scores before crawling
    health_scores = BaseCrawler.get_all_source_health()
    if health_scores:
        logger.info("pre_crawl_health_scores", scores=health_scores)

    # Load UI-configured keys from DB, fall back to env vars
    db_keys: dict[str, dict[str, str]] = {}
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        db_keys = load_api_keys_from_db()
    except Exception:
        logger.warning("db_keys_load_failed_using_env_vars", exc_info=True)

    def _get(platform: str, key_name: str, env_fallback: str | None) -> str | None:
        """Get key from DB first, then from env."""
        return (db_keys.get(platform, {}).get(key_name) or env_fallback) or None

    manager = CrawlerManager.create_default(
        meta_token=_get("meta", "access_token", settings.meta_access_token),
        tiktok_token=_get("tiktok", "access_token", settings.tiktok_access_token),
        youtube_api_key=_get("youtube", "api_key", settings.youtube_api_key),
        x_twitter_bearer=_get("x_twitter", "bearer_token", settings.x_twitter_bearer_token),
        line_token=_get("line", "access_token", settings.line_api_access_token),
        yahoo_api_key=_get("yahoo", "api_key", settings.yahoo_ads_api_key),
        yahoo_api_secret=_get("yahoo", "api_secret", settings.yahoo_ads_api_secret),
        pinterest_token=_get("pinterest", "access_token", settings.pinterest_access_token),
        smartnews_api_key=_get("smartnews", "api_key", settings.smartnews_ads_api_key),
        google_ads_developer_token=_get("google_ads", "developer_token", settings.google_ads_developer_token),
        google_ads_client_id=_get("google_ads", "client_id", settings.google_ads_client_id),
        google_ads_client_secret=_get("google_ads", "client_secret", settings.google_ads_client_secret),
        google_ads_refresh_token=_get("google_ads", "refresh_token", settings.google_ads_refresh_token),
        gunosy_api_key=_get("gunosy", "api_key", settings.gunosy_ads_api_key),
    )
    try:
        # ── Keyword expansion for short/English-only queries ──
        from app.services.crawling.keyword_expander import should_expand, expand_query

        expanded_queries: list[str] = []
        if should_expand(query):
            expanded_queries = expand_query(query, category)
            logger.info(
                "keyword_expansion_applied",
                original_query=query,
                expanded=expanded_queries,
            )

        # Primary search with original query (full limit)
        results = await manager.search_all_platforms(
            query=query,
            platforms=platforms,
            category=category,
            limit_per_platform=limit_per_platform,
            country=country,
        )

        # Expanded queries: run concurrently for speed, deduplicate by external_id
        if expanded_queries:
            import asyncio as _aio
            import random as _rand

            # Shuffle for variety across sessions, cap at 2 for speed
            if len(expanded_queries) > 2:
                _rand.shuffle(expanded_queries)
                expanded_queries = expanded_queries[:2]

            seen_ids: set[str] = set()
            for platform_ads in results.values():
                for ad in platform_ads:
                    if hasattr(ad, "external_id") and ad.external_id:
                        seen_ids.add(ad.external_id)

            logger.info(
                "expanded_crawl_starting",
                total_queries=len(expanded_queries),
                queries=expanded_queries,
            )

            # Run all expanded queries concurrently
            async def _run_expanded(eq: str):
                return eq, await manager.search_all_platforms(
                    query=eq,
                    platforms=platforms,
                    category=category,
                    limit_per_platform=10,
                    country=country,
                )

            expanded_results = await _aio.gather(
                *[_run_expanded(eq) for eq in expanded_queries],
                return_exceptions=True,
            )

            for result_or_err in expanded_results:
                if isinstance(result_or_err, Exception):
                    logger.warning("expanded_query_failed", error=str(result_or_err))
                    continue
                eq, extra = result_or_err
                added = 0
                for platform, ads in extra.items():
                    for ad in ads:
                        eid = getattr(ad, "external_id", None)
                        if eid and eid in seen_ids:
                            continue
                        if eid:
                            seen_ids.add(eid)
                        # Tag with expansion metadata
                        if hasattr(ad, "metadata") and isinstance(ad.metadata, dict):
                            ad.metadata["crawl_query"] = eq
                            ad.metadata["expanded_from"] = query
                        results.setdefault(platform, []).append(ad)
                        added += 1
                logger.info(
                    "expanded_query_result",
                    query=eq,
                    new_ads=added,
                )

        # ── Post-merge: Japanese language filter (country=JP) ──
        if country == "JP":
            for platform, ads in results.items():
                # Ensure japanese_ratio is set for all ads
                for ad in ads:
                    meta = getattr(ad, "metadata", None) or {}
                    if "japanese_ratio" not in meta:
                        text = (getattr(ad, "title", "") or "") + " " + (getattr(ad, "description", "") or "")
                        jp_chars = sum(1 for c in text if "\u3000" <= c <= "\u9fff" or "\u30a0" <= c <= "\u30ff")
                        total = max(len(text.replace(" ", "")), 1)
                        if hasattr(ad, "metadata") and isinstance(ad.metadata, dict):
                            ad.metadata["japanese_ratio"] = round(jp_chars / total, 3)

                jp_ads = [a for a in ads if (getattr(a, "metadata", None) or {}).get("japanese_ratio", 0) > 0.05]
                non_jp = [a for a in ads if (getattr(a, "metadata", None) or {}).get("japanese_ratio", 0) <= 0.05]

                if jp_ads:
                    results[platform] = jp_ads
                # else: no JP ads at all → keep everything as fallback

            filtered_total = sum(len(v) for v in results.values())
            logger.info(
                "jp_language_filter_applied",
                country=country,
                before=sum(len(ads) for platform, ads in results.items()),
                after=filtered_total,
            )

        return results
    finally:
        await manager.close_all()


def _merge_crawled_data(existing: Ad, crawled_ad, session) -> None:
    """Merge new crawl data into existing ad without overwriting valid data."""
    from sqlalchemy.orm.attributes import flag_modified

    changed = False
    dest_url = _extract_destination_url(crawled_ad)
    title_fallback, desc_fallback = _extract_text_fallback(crawled_ad)

    # Only fill in missing fields — never overwrite non-null with null
    for attr, new_val in [
        ("title", title_fallback),
        ("description", desc_fallback),
        ("thumbnail_url", crawled_ad.thumbnail_url),
        ("snapshot_url", crawled_ad.snapshot_url),
        ("video_url", crawled_ad.video_url),
        ("destination_url", dest_url),
        ("advertiser_name", crawled_ad.advertiser_name),
        ("advertiser_url", crawled_ad.advertiser_url),
    ]:
        if new_val and not getattr(existing, attr, None):
            setattr(existing, attr, new_val)
            changed = True

    # Update metrics if new values are higher (fresher data)
    for attr, new_val in [
        ("view_count", crawled_ad.view_count),
        ("like_count", crawled_ad.like_count),
        ("impressions", crawled_ad.impressions),
    ]:
        if new_val and (not getattr(existing, attr, None) or new_val > getattr(existing, attr)):
            setattr(existing, attr, new_val)
            changed = True

    # Merge metadata
    if crawled_ad.metadata:
        meta = dict(existing.ad_metadata or {})
        for k, v in crawled_ad.metadata.items():
            if v is not None and k not in meta:
                meta[k] = v
        if dest_url and not meta.get("destination_url"):
            meta["destination_url"] = dest_url
            meta.setdefault("destination_type", "LP")
        meta["last_crawled_at"] = __import__("datetime").datetime.utcnow().isoformat()
        existing.ad_metadata = meta
        flag_modified(existing, "ad_metadata")
        changed = True

    if changed:
        try:
            session.commit()
        except Exception:
            session.rollback()
        logger.info("ad_data_merged", ad_id=existing.id, external_id=existing.external_id)


def _inline_enrich(ad: Ad, session) -> None:
    """Inline HTTP+BS4 enrichment fallback when task dispatch fails.

    Extracts og:image, og:title, og:description, and also parses
    <img>/<video> elements from render_ad HTML for better thumbnails.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        url = ad.snapshot_url
        if not url:
            return

        with httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract og:image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            if img_url.startswith("http"):
                if not ad.image_url:
                    ad.image_url = img_url
                if not ad.thumbnail_url:
                    ad.thumbnail_url = img_url

        # Extract og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and not ad.description:
            ad.description = og_desc["content"].strip()

        # Extract og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content") and not ad.title:
            ad.title = og_title["content"].strip()

        # Also parse <img> elements from render_ad HTML for better thumbnails
        # render_ad pages often have the actual ad creative as large <img> elements
        if not ad.thumbnail_url or "s200x200" in (ad.thumbnail_url or ""):
            best_img = None
            best_area = 0
            for img_el in soup.find_all("img"):
                src = img_el.get("src") or img_el.get("data-src") or ""
                if not src.startswith("http"):
                    continue
                # Skip tracking pixels, icons, emojis
                if any(skip in src.lower() for skip in [
                    "pixel", "tracking", "1x1", "favicon", "emoji", "rsrc.php",
                ]):
                    continue
                # Skip small images
                w = int(img_el.get("width", "0") or "0")
                h = int(img_el.get("height", "0") or "0")
                if w > 0 and w < 80:
                    continue
                if h > 0 and h < 80:
                    continue
                area = w * h if w > 0 and h > 0 else 10000  # default area for unsized
                if area > best_area:
                    best_area = area
                    best_img = src

            if best_img:
                ad.thumbnail_url = best_img
                if not ad.image_url:
                    ad.image_url = best_img

        # Check for <video> elements — extract src/poster
        for video_el in soup.find_all("video"):
            # Extract video source URL
            src = video_el.get("src")
            if src and src.startswith("http") and not ad.video_url:
                ad.video_url = src
            # Also check <source> children
            if not ad.video_url:
                for source_el in video_el.find_all("source"):
                    s = source_el.get("src")
                    if s and s.startswith("http"):
                        ad.video_url = s
                        break
            # Extract poster as thumbnail
            poster = video_el.get("poster")
            if poster and poster.startswith("http"):
                if not ad.thumbnail_url:
                    ad.thumbnail_url = poster
            if ad.video_url or poster:
                if not ad.creative_type or ad.creative_type == "unknown":
                    ad.creative_type = "video"
                break

        ad.media_extraction_status = MediaExtractionStatus.ENRICHED
        session.commit()
        logger.info("inline_enrich_completed", ad_id=ad.id)

    except Exception as e:
        logger.warning("inline_enrich_failed", ad_id=ad.id, error=str(e))
        ad.media_extraction_status = MediaExtractionStatus.PENDING
        try:
            session.commit()
        except Exception:
            session.rollback()


def _inline_download_videos(session, saved_count: int) -> None:
    """Download video files inline for recently saved ads with video_url.

    Saves to media_cache/videos/{ad_id}.{ext}. Skips existing files.
    100 MB size limit, streaming download, errors logged and skipped.
    """
    import os
    import requests
    from sqlalchemy.orm.attributes import flag_modified

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VIDEO_DIR = os.path.join(BASE_DIR, "..", "media_cache", "videos")
    VIDEO_DIR = os.path.normpath(VIDEO_DIR)
    MAX_SIZE = 100 * 1024 * 1024  # 100 MB
    TIMEOUT = 30
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )

    ads_with_video = session.query(Ad).filter(
        Ad.video_url.isnot(None),
        Ad.video_url != "",
    ).order_by(Ad.created_at.desc()).limit(saved_count).all()

    if not ads_with_video:
        return

    os.makedirs(VIDEO_DIR, exist_ok=True)
    downloaded = 0

    for ad in ads_with_video:
        # Skip if already cached
        existing = False
        for ext in ("mp4", "webm", "mov"):
            path = os.path.join(VIDEO_DIR, f"{ad.id}.{ext}")
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                existing = True
                break
        if existing:
            continue

        try:
            resp = requests.get(
                ad.video_url,
                timeout=TIMEOUT,
                stream=True,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                logger.warning(
                    "video_download_http_error",
                    ad_id=ad.id, status=resp.status_code,
                )
                continue

            content_type = resp.headers.get("Content-Type", "")
            url_lower = ad.video_url.lower()
            if ".webm" in url_lower or "webm" in content_type:
                ext = "webm"
            elif ".mov" in url_lower or "quicktime" in content_type:
                ext = "mov"
            else:
                ext = "mp4"

            dest_path = os.path.join(VIDEO_DIR, f"{ad.id}.{ext}")
            total = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    total += len(chunk)
                    if total > MAX_SIZE:
                        break
                    f.write(chunk)

            if total > MAX_SIZE:
                os.remove(dest_path)
                logger.info("video_download_too_large", ad_id=ad.id, size_mb=round(total / 1024 / 1024, 1))
                continue

            if os.path.getsize(dest_path) < 1000:
                os.remove(dest_path)
                continue

            # Update metadata
            meta = dict(ad.ad_metadata or {})
            meta["video_cached"] = True
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            downloaded += 1

        except Exception as e:
            logger.warning("video_download_failed", ad_id=ad.id, error=str(e)[:200])
            continue

    if downloaded > 0:
        try:
            session.commit()
        except Exception:
            session.rollback()
        logger.info("inline_video_download_completed", count=downloaded)


def _map_platform(platform: str) -> AdPlatformEnum:
    mapping = {
        "facebook": AdPlatformEnum.FACEBOOK,
        "instagram": AdPlatformEnum.INSTAGRAM,
        "youtube": AdPlatformEnum.YOUTUBE,
        "tiktok": AdPlatformEnum.TIKTOK,
        "x_twitter": AdPlatformEnum.X_TWITTER,
        "line": AdPlatformEnum.LINE,
        "yahoo": AdPlatformEnum.YAHOO,
        "pinterest": AdPlatformEnum.PINTEREST,
        "smartnews": AdPlatformEnum.SMARTNEWS,
        "google_ads": AdPlatformEnum.GOOGLE_ADS,
        "gunosy": AdPlatformEnum.GUNOSY,
    }
    return mapping.get(platform, AdPlatformEnum.OTHER)


# ── CI-114: Crawl Result Verification Sampling ────────────────


def verify_crawl_sample(session, sample_size: int = 10) -> dict:
    """CI-114: Sample recent crawl results and verify data quality.

    Checks:
    - external_id is non-empty
    - title or description is present
    - snapshot_url or image_url is set
    - destination_url format is valid
    - creative_type is not 'unknown'

    Returns summary dict with pass/fail counts and issue details.
    """
    import random

    recent_ads = session.query(Ad).order_by(Ad.created_at.desc()).limit(100).all()
    if not recent_ads:
        return {"sampled": 0, "passed": 0, "failed": 0, "issues": []}

    sample = random.sample(recent_ads, min(sample_size, len(recent_ads)))
    passed = 0
    failed = 0
    issues = []

    for ad in sample:
        ad_issues = []

        if not ad.external_id:
            ad_issues.append("missing_external_id")

        if not ad.title and not ad.description:
            ad_issues.append("no_title_or_description")

        if not ad.snapshot_url and not ad.image_url and not ad.video_url:
            ad_issues.append("no_media_reference")

        if ad.destination_url and not ad.destination_url.startswith(("http://", "https://")):
            ad_issues.append("invalid_destination_url")

        if ad.creative_type == "unknown":
            ad_issues.append("unknown_creative_type")

        if ad_issues:
            failed += 1
            issues.append({"ad_id": ad.id, "issues": ad_issues})
        else:
            passed += 1

    result = {
        "sampled": len(sample),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(sample), 3) if sample else 0,
        "issues": issues,
    }
    logger.info("crawl_sample_verification", **result)
    return result


# ── CI-106: Failure Pattern Report ────────────────────────────


def get_failure_report(session, limit: int = 100) -> dict:
    """CI-106: Report crawl failure patterns grouped by platform and reason.

    Returns:
        Dict with by_reason, by_platform counts and recent_failures list.
    """
    from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
    from collections import Counter

    failed_jobs = (
        session.query(CrawlJob)
        .filter(CrawlJob.status == CrawlJobStatusEnum.FAILED)
        .order_by(CrawlJob.created_at.desc())
        .limit(limit)
        .all()
    )

    by_reason = Counter()
    by_platform = Counter()
    recent = []

    for job in failed_jobs:
        reason = job.failure_reason or "unknown"
        by_reason[reason] += 1

        platforms = job.platforms or []
        for p in platforms:
            by_platform[p] += 1

        if len(recent) < 10:
            recent.append({
                "job_id": job.job_id,
                "query": job.query,
                "reason": reason,
                "platforms": platforms,
                "error": (job.error_message or "")[:200],
                "created_at": str(job.created_at),
            })

    return {
        "total_failures": len(failed_jobs),
        "by_reason": dict(by_reason.most_common()),
        "by_platform": dict(by_platform.most_common()),
        "recent_failures": recent,
    }


# ── CI-084: Snapshot Fallback Capture Queue ───────────────────


def queue_snapshot_fallback(session, limit: int = 50) -> dict:
    """CI-084: Find ads with missing/broken snapshots and queue for re-capture.

    Targets ads where:
    - snapshot_url is NULL but external_id exists
    - media_extraction_status is PENDING or FAILED
    - No image_url or thumbnail_url available

    Returns dict with queued count and ad IDs.
    """
    from sqlalchemy.orm.attributes import flag_modified

    ads = (
        session.query(Ad)
        .filter(
            Ad.external_id.isnot(None),
            Ad.image_url.is_(None),
            Ad.thumbnail_url.is_(None),
            Ad.media_extraction_status.in_([
                MediaExtractionStatus.PENDING,
                MediaExtractionStatus.FAILED,
            ]),
        )
        .order_by(Ad.created_at.desc())
        .limit(limit)
        .all()
    )

    queued_ids = []
    for ad in ads:
        meta = dict(ad.ad_metadata or {})
        # Build snapshot URL from external_id if missing
        if not ad.snapshot_url and ad.external_id:
            ad.snapshot_url = f"https://www.facebook.com/ads/library/?id={ad.external_id}"

        meta["snapshot_fallback_queued"] = True
        meta["snapshot_fallback_at"] = datetime.utcnow().isoformat()
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        ad.media_extraction_status = MediaExtractionStatus.PENDING
        queued_ids.append(ad.id)

    if queued_ids:
        try:
            session.commit()
        except Exception:
            session.rollback()

    logger.info("snapshot_fallback_queued", count=len(queued_ids))
    return {"queued": len(queued_ids), "ad_ids": queued_ids}


# ── CI-076: Retry Budget Dashboard ───────────────────────────


def get_retry_budget_report(session) -> dict:
    """CI-076: Report retry consumption across crawl and media tasks.

    Returns retry counts, budget utilization, and per-status breakdown.
    """
    from sqlalchemy import func

    # Crawl job retries (from CrawlJob table)
    from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum

    total_jobs = session.query(func.count(CrawlJob.id)).scalar() or 0
    failed_jobs = session.query(func.count(CrawlJob.id)).filter(
        CrawlJob.status == CrawlJobStatusEnum.FAILED
    ).scalar() or 0

    # Media extraction retries (from ad.media_extraction_status)
    total_extractions = session.query(func.count(Ad.id)).filter(
        Ad.media_extraction_status.isnot(None),
    ).scalar() or 0
    failed_extractions = session.query(func.count(Ad.id)).filter(
        Ad.media_extraction_status == MediaExtractionStatus.FAILED,
    ).scalar() or 0
    retrying_extractions = session.query(func.count(Ad.id)).filter(
        Ad.media_extraction_status == MediaExtractionStatus.RETRYING,
    ).scalar() or 0

    # Ads with retry metadata
    retry_exhausted = 0
    try:
        retry_exhausted = session.execute(
            text("SELECT COUNT(*) FROM ads WHERE json_extract(metadata, '$.media_retry_count') >= 3")
        ).scalar() or 0
    except Exception:
        pass  # PostgreSQL uses different JSON syntax

    crawl_retry_rate = failed_jobs / total_jobs if total_jobs > 0 else 0
    media_retry_rate = (failed_extractions + retrying_extractions) / total_extractions if total_extractions > 0 else 0

    return {
        "crawl": {
            "total_jobs": total_jobs,
            "failed": failed_jobs,
            "retry_rate": round(crawl_retry_rate, 3),
        },
        "media": {
            "total": total_extractions,
            "failed": failed_extractions,
            "retrying": retrying_extractions,
            "retry_exhausted": retry_exhausted,
            "retry_rate": round(media_retry_rate, 3),
        },
    }
