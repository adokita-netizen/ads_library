"""AWS Lambda handler for the FastAPI API (via Mangum)."""

import os
import json
import time

import structlog

logger = structlog.get_logger()

_IS_PRODUCTION = os.environ.get("APP_ENV", "").lower() in ("production", "prod")


def _safe_error(e: Exception) -> str:
    """Return error detail in dev, generic message in production."""
    if _IS_PRODUCTION:
        return "Internal server error"
    return str(e)

# Ensure DB tables are created on first Lambda cold start
_DB_INITIALIZED = False

def _init_database():
    """Run database initialization (create tables if they don't exist)."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    max_retries = 3
    for attempt in range(max_retries):
        session = None
        try:
            from app.core.database import sync_engine, Base, get_session_with_retry
            # These imports register SQLAlchemy models with Base.metadata.
            # Do NOT remove even though they appear unused — required for create_all().
            import app.models.ad  # noqa: F401
            import app.models.ad_metrics  # noqa: F401
            import app.models.analysis  # noqa: F401
            import app.models.user  # noqa: F401
            import app.models.landing_page  # noqa: F401
            import app.models.api_key  # noqa: F401
            import app.models.alert_rule  # noqa: F401
            import app.models.alert_history  # noqa: F401
            import app.models.crawl_job  # noqa: F401
            import app.models.creative_asset  # noqa: F401
            import app.models.brand_registry  # noqa: F401
            session = get_session_with_retry()
            # Create tables one-by-one with checkfirst to avoid DuplicateTable errors
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(sync_engine)
            existing_tables = set(inspector.get_table_names())
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    table.create(bind=sync_engine, checkfirst=True)
            _DB_INITIALIZED = True
            return
        except Exception as e:
            if attempt >= max_retries - 1:
                logger.warning("db_init_skipped", error=str(e), attempts=max_retries)
                return
            delay = float(2 ** attempt)
            logger.warning(
                "db_init_retry",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=delay,
                error=str(e),
            )
            time.sleep(delay)
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

_init_database()

from mangum import Mangum
from app.main import app

_mangum_handler = Mangum(app, lifespan="off")


def _get_forwarded_source_ip(event: dict) -> str:
    """Extract source IP from forwarded headers with safe fallback."""
    if not isinstance(event, dict):
        return "0.0.0.0"
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}
    forwarded = (
        headers.get("x-forwarded-for")
        or headers.get("X-Forwarded-For")
        or headers.get("x-real-ip")
        or headers.get("X-Real-IP")
        or "0.0.0.0"
    )
    return str(forwarded).split(",")[0].strip() or "0.0.0.0"


def _ensure_request_source_ip(event: dict) -> None:
    """Backfill sourceIp fields expected by Mangum for API Gateway events."""
    if not isinstance(event, dict):
        return
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        request_context = {}
        event["requestContext"] = request_context

    source_ip = _get_forwarded_source_ip(event)

    # HTTP API v2 shape: requestContext.http.sourceIp
    http_ctx = request_context.get("http")
    if not isinstance(http_ctx, dict):
        http_ctx = {}
        request_context["http"] = http_ctx
    http_ctx.setdefault("sourceIp", source_ip)

    # REST API v1 shape: requestContext.identity.sourceIp
    identity = request_context.get("identity")
    if not isinstance(identity, dict):
        identity = {}
        request_context["identity"] = identity
    identity.setdefault("sourceIp", source_ip)


def handler(event, context):
    """Lambda handler with support for DB migration trigger."""
    # Direct invocation for DB migration
    if isinstance(event, dict) and event.get("action") == "migrate":
        try:
            from sqlalchemy import text as sa_text
            from app.core.database import sync_engine, Base

            results = {"columns_added": [], "tables_created": [], "errors": []}

            # Add missing columns to ads table
            alter_statements = [
                ("ads", "hit_proxy_score", "ALTER TABLE ads ADD COLUMN hit_proxy_score DOUBLE PRECISION"),
                ("ads", "active_days", "ALTER TABLE ads ADD COLUMN active_days INTEGER"),
                ("ads", "brand_id", "ALTER TABLE ads ADD COLUMN brand_id BIGINT"),
                # H1: Meta Ad Library dedicated fields
                ("ads", "ad_creation_time", "ALTER TABLE ads ADD COLUMN ad_creation_time TIMESTAMPTZ"),
                ("ads", "ad_delivery_start_time", "ALTER TABLE ads ADD COLUMN ad_delivery_start_time TIMESTAMPTZ"),
                ("ads", "ad_delivery_stop_time", "ALTER TABLE ads ADD COLUMN ad_delivery_stop_time TIMESTAMPTZ"),
                ("ads", "publisher_platforms", "ALTER TABLE ads ADD COLUMN publisher_platforms JSONB"),
                ("ads", "estimated_audience_size_min", "ALTER TABLE ads ADD COLUMN estimated_audience_size_min BIGINT"),
                ("ads", "estimated_audience_size_max", "ALTER TABLE ads ADD COLUMN estimated_audience_size_max BIGINT"),
                ("ads", "country_context", "ALTER TABLE ads ADD COLUMN country_context JSONB"),
                ("ads", "demographic_distribution", "ALTER TABLE ads ADD COLUMN demographic_distribution JSONB"),
                ("ads", "searchable_text", "ALTER TABLE ads ADD COLUMN searchable_text TEXT"),
            ]

            for table, col, stmt in alter_statements:
                try:
                    with sync_engine.begin() as conn:
                        conn.execute(sa_text(stmt))
                    results["columns_added"].append(f"{table}.{col}")
                except Exception as col_err:
                    if "already exists" in str(col_err).lower() or "duplicate" in str(col_err).lower():
                        pass  # Column already exists
                    else:
                        results["errors"].append(f"{table}.{col}: {str(col_err)}")

            # Create any missing tables via metadata
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(sync_engine)
            existing_tables = set(inspector.get_table_names())
            import app.models.brand_registry  # noqa: F401
            import app.models.creative_asset  # noqa: F401
            import app.models.crawl_job  # noqa: F401
            for tbl in Base.metadata.sorted_tables:
                if tbl.name not in existing_tables:
                    try:
                        tbl.create(bind=sync_engine, checkfirst=True)
                        results["tables_created"].append(tbl.name)
                    except Exception as tbl_err:
                        results["errors"].append(f"table {tbl.name}: {str(tbl_err)}")

            # L5: Create meta_creative_search_index materialized view
            _SEARCH_INDEX_SQL = """
            CREATE MATERIALIZED VIEW IF NOT EXISTS meta_creative_search_index AS
            SELECT
                cf.id AS family_id,
                cf.canonical_advertiser_name AS brand_name,
                cf.primary_genre_code,
                cf.first_seen,
                cf.last_seen,
                cf.active_days,
                cf.member_count,
                cf.variant_count,
                cf.platform_count,
                cf.hit_proxy_score,
                array_agg(DISTINCT a.platform) FILTER (WHERE a.platform IS NOT NULL) AS platforms,
                array_agg(DISTINCT a.external_id) FILTER (WHERE a.external_id IS NOT NULL) AS library_ids,
                string_agg(DISTINCT a.searchable_text, ' ') AS searchable_text
            FROM creative_families cf
            LEFT JOIN creative_assets ca ON ca.family_id = cf.id
            LEFT JOIN ads a ON a.id = ca.ad_id
            GROUP BY cf.id
            """
            try:
                with sync_engine.begin() as conn:
                    conn.execute(sa_text(_SEARCH_INDEX_SQL))
                    results["tables_created"].append("meta_creative_search_index (matview)")
            except Exception as mv_err:
                if "already exists" not in str(mv_err).lower():
                    results["errors"].append(f"matview: {str(mv_err)}")

            # Create GIN index on searchable_text for full-text search (M3)
            _GIN_INDEX_SQL = """
            CREATE INDEX IF NOT EXISTS idx_ads_searchable_text_gin
            ON ads USING gin(to_tsvector('simple', COALESCE(searchable_text, '')))
            """
            try:
                with sync_engine.begin() as conn:
                    conn.execute(sa_text(_GIN_INDEX_SQL))
                    results["columns_added"].append("idx_ads_searchable_text_gin")
            except Exception as gin_err:
                if "already exists" not in str(gin_err).lower():
                    results["errors"].append(f"gin_index: {str(gin_err)}")

            # Stamp alembic to latest
            try:
                from alembic.config import Config
                from alembic import command
                alembic_cfg = Config("alembic.ini")
                command.stamp(alembic_cfg, "head")
                results["alembic"] = "stamped to head"
            except Exception as alembic_err:
                results["alembic"] = f"stamp error: {str(alembic_err)}"

            return {"statusCode": 200, "body": json.dumps({"status": "migration_complete", "results": results})}
        except Exception as e:
            logger.error("migration_error", error=str(e), exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"status": "migration_error", "error": _safe_error(e)})}

    # Direct invocation for batch pipeline (all enrichment steps)
    if isinstance(event, dict) and event.get("action") == "enrich":
        try:
            from app.core.database import SyncSessionLocal
            session = SyncSessionLocal()
            results = {}
            try:
                # Step 1: Build cards
                from app.services.card_builder import batch_build_cards
                results["cards"] = batch_build_cards(session)

                # Step 2: Extract angles
                from app.services.angle_extractor import batch_extract_angles
                results["angles"] = batch_extract_angles(session)

                # Step 3: Discover brands
                from app.services.brand_resolver import auto_discover_brands
                results["brands"] = auto_discover_brands(session)

                # Step 4: Hit proxy scores
                from app.services.hit_proxy import batch_compute_hit_proxy
                results["hit_proxy"] = batch_compute_hit_proxy()

                # Step 5: Build searchable text
                from app.services.searchable_text_builder import build_searchable_text
                results["searchable_text"] = build_searchable_text(session)

                # Step 6: Build creative families
                from app.services.creative_family_builder import build_creative_families
                results["families"] = build_creative_families(session)

                # Step 7: Compute ad-LP consistency
                from app.services.ad_lp_consistency import batch_compute_consistency
                results["consistency"] = batch_compute_consistency(session)

                session.commit()
            except Exception as inner_err:
                session.rollback()
                raise inner_err
            finally:
                session.close()
            return {"statusCode": 200, "body": json.dumps({"status": "enrich_complete", "results": results}, default=str)}
        except Exception as e:
            logger.error("enrich_error", error=str(e), exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"status": "enrich_error", "error": _safe_error(e)})}

    # Direct invocation for data cleanup (foreign ads, duplicates, creative_type)
    if isinstance(event, dict) and event.get("action") == "cleanup":
        return _run_cleanup(event)

    # Direct invocation for network connectivity test
    if isinstance(event, dict) and event.get("action") == "test_network":
        return _test_network()

    # Direct invocation for batch media extraction (pending ads → SQS → ECS)
    if isinstance(event, dict) and event.get("action") == "extract_media":
        return _run_extract_media(event)

    # Direct invocation for crawling (bypasses API Gateway 29s timeout)
    if isinstance(event, dict) and event.get("action") == "crawl":
        return _run_crawl(event)

    # Direct invocation for updating API keys in DB
    if isinstance(event, dict) and event.get("action") == "update_api_key":
        return _update_api_key(event)

    # Direct invocation for re-downloading thumbnails for existing ads
    if isinstance(event, dict) and event.get("action") == "refresh_thumbnails":
        return _refresh_thumbnails(event)

    # Backfill sourceIp for Mangum compatibility (HTTP API v2 / REST API v1).
    _ensure_request_source_ip(event)

    return _mangum_handler(event, context)


def _test_network() -> dict:
    """Test internet connectivity and Meta API from Lambda VPC."""
    import httpx
    import socket
    import urllib.request
    results = {}

    # Test 1: raw socket connection (IPv4 only)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(("142.250.196.100", 443))  # google.com
        s.close()
        results["socket_ipv4"] = "OK"
    except Exception as e:
        results["socket_ipv4"] = f"{type(e).__name__}: {str(e)}"

    # Test 2: DNS resolution
    try:
        results["dns_google"] = str(socket.getaddrinfo("graph.facebook.com", 443, socket.AF_INET))[:200]
    except Exception as e:
        results["dns_google"] = f"{type(e).__name__}: {str(e)}"

    # Test 3: urllib (standard library)
    try:
        req = urllib.request.urlopen("https://www.google.com", timeout=10)
        results["urllib_google"] = f"status={req.status}"
    except Exception as e:
        results["urllib_google"] = f"{type(e).__name__}: {str(e)}"

    # Test 4: httpx with transport (IPv4 only)
    try:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        client = httpx.Client(transport=transport, timeout=10)
        r = client.get("https://www.google.com", follow_redirects=True)
        results["httpx_ipv4"] = f"status={r.status_code}"
        client.close()
    except Exception as e:
        results["httpx_ipv4"] = f"{type(e).__name__}: {str(e)}"

    # Test with DB token and app token
    try:
        from app.core.database import SyncSessionLocal
        from sqlalchemy import text
        session = SyncSessionLocal()

        # Get all meta keys
        rows = session.execute(text(
            "SELECT key_name, key_value FROM platform_api_keys WHERE platform='meta' AND is_active=true"
        )).fetchall()
        meta_keys = {r[0]: r[1] for r in rows}
        session.close()

        # Test with stored access_token
        token = meta_keys.get("access_token", "")
        r = httpx.get(
            "https://graph.facebook.com/v25.0/ads_archive",
            params={"access_token": token, "search_terms": "スキンケア", "ad_reached_countries": '["JP"]', "limit": "1", "fields": "id,page_name"},
            timeout=15,
        )
        results["meta_stored_token"] = {"status": r.status_code, "body": r.text[:500]}

        # Test with app token (app_id|app_secret)
        app_id = meta_keys.get("app_id", "")
        app_secret = meta_keys.get("app_secret", "")
        if app_id and app_secret:
            app_token = f"{app_id}|{app_secret}"
            r2 = httpx.get(
                "https://graph.facebook.com/v25.0/ads_archive",
                params={"access_token": app_token, "search_terms": "スキンケア", "ad_reached_countries": '["JP"]', "limit": "1", "fields": "id,page_name"},
                timeout=15,
            )
            results["meta_app_token"] = {"status": r2.status_code, "body": r2.text[:500]}
    except Exception as e:
        results["meta_token_test"] = {"error": f"{type(e).__name__}: {str(e)}"}

    return {"statusCode": 200, "body": json.dumps(results, default=str, ensure_ascii=False)}


def _run_crawl(event: dict) -> dict:
    """Run ad crawl directly on Lambda (up to 15min timeout)."""
    import asyncio
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad, AdPlatformEnum, AdCategoryEnum, MediaExtractionStatus

    # Genre rotation: use today's scheduled keywords when rotate_genre=True
    if event.get("rotate_genre"):
        from app.tasks.crawl_tasks import get_today_keywords
        queries = get_today_keywords()
        logger.info("genre_rotation_crawl keywords=%s", queries)
    else:
        queries = event.get("queries", ["スキンケア", "ダイエット", "美容液", "サプリメント", "化粧品"])
    platforms = event.get("platforms", ["facebook", "instagram"])
    limit = event.get("limit_per_platform", 20)
    category = event.get("category", None)

    total_saved = 0
    errors = []
    query_results = {}

    for query in queries:
        try:
            from app.tasks.crawl_tasks import _crawl_platforms, _map_platform
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                _crawl_platforms(query, platforms, category, limit)
            )
            loop.close()

            session = SyncSessionLocal()
            saved = 0
            try:
                for platform, crawled_ads in results.items():
                    for crawled_ad in crawled_ads:
                        if crawled_ad.external_id:
                            existing = session.query(Ad).filter(
                                Ad.external_id == crawled_ad.external_id
                            ).first()
                            if existing:
                                continue

                        has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                        extraction_status = MediaExtractionStatus.SKIPPED if has_direct_media else (MediaExtractionStatus.PENDING if crawled_ad.snapshot_url else MediaExtractionStatus.SKIPPED)

                        ad_category = None
                        if crawled_ad.category:
                            try:
                                ad_category = AdCategoryEnum(crawled_ad.category)
                            except ValueError:
                                ad_category = AdCategoryEnum.OTHER
                        elif category:
                            try:
                                ad_category = AdCategoryEnum(category)
                            except ValueError:
                                pass

                        platform_enum = None
                        try:
                            platform_enum = AdPlatformEnum(platform)
                        except ValueError:
                            pass

                        ad = Ad(
                            external_id=crawled_ad.external_id,
                            title=crawled_ad.title,
                            description=crawled_ad.description,
                            platform=platform_enum,
                            category=ad_category,
                            advertiser_name=crawled_ad.advertiser_name,
                            thumbnail_url=crawled_ad.thumbnail_url or (crawled_ad.image_urls[0] if crawled_ad.image_urls else None),
                            image_url=crawled_ad.image_urls[0] if crawled_ad.image_urls else None,
                            video_url=crawled_ad.video_url,
                            snapshot_url=crawled_ad.snapshot_url,
                            destination_url=crawled_ad.destination_url or (crawled_ad.metadata or {}).get("destination_url"),
                            creative_type="video" if crawled_ad.video_url else ("image" if (crawled_ad.image_urls or crawled_ad.thumbnail_url or crawled_ad.snapshot_url) else "unknown"),
                            media_extraction_status=extraction_status,
                            view_count=crawled_ad.view_count,
                            like_count=crawled_ad.like_count,
                            estimated_impressions=crawled_ad.impressions,
                            spend=crawled_ad.spend,
                            first_seen_at=crawled_ad.first_seen_at,
                            last_seen_at=crawled_ad.last_seen_at,
                            ad_metadata=crawled_ad.metadata or {},
                        )
                        session.add(ad)
                        saved += 1

                session.commit()

                # Download thumbnails immediately while URLs are fresh
                _download_thumbnails_inline(session)
                total_saved += saved
                query_results[query] = {"saved": saved, "platforms": list(results.keys())}
                logger.info("crawl_query_done", query=query, saved=saved)
            except Exception as e:
                session.rollback()
                errors.append(f"{query}: {str(e)}")
                logger.error("crawl_save_error", query=query, error=str(e))
            finally:
                session.close()
        except Exception as e:
            errors.append(f"{query}: {str(e)}")
            logger.error("crawl_error", query=query, error=str(e))

    # Auto-dispatch media extraction for newly saved ads
    if total_saved > 0:
        try:
            from app.tasks.dispatcher import dispatch_task
            _ses = SyncSessionLocal()
            pending_ads = _ses.query(Ad).filter(
                Ad.media_extraction_status == MediaExtractionStatus.PENDING,
                Ad.snapshot_url.isnot(None),
            ).limit(total_saved).all()
            media_dispatched = 0
            for ad in pending_ads:
                try:
                    dispatch_task("extract_media", ad_id=ad.id)
                    ad.media_extraction_status = MediaExtractionStatus.DISPATCHED
                    media_dispatched += 1
                except Exception:
                    pass
            _ses.commit()
            _ses.close()
            query_results["media_dispatched"] = media_dispatched
        except Exception as e:
            logger.warning("auto_media_dispatch_failed", error=str(e))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "total_saved": total_saved,
            "query_results": query_results,
            "errors": errors,
        }, default=str)
    }


def _run_cleanup(event: dict) -> dict:
    """Clean production DB: delete foreign ads, deduplicate, fix creative_type.

    Each step runs in its own transaction so a failure in one step
    does not roll back previous successful steps.
    """
    import re
    from sqlalchemy import text
    from app.core.database import SyncSessionLocal

    dry_run = event.get("dry_run", False)
    results = {"dry_run": dry_run, "steps": []}
    jp_re = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")

    def _step_delete_foreign(session):
        rows = session.execute(text(
            "SELECT id, advertiser_name, title, description FROM ads"
        )).fetchall()
        non_jp_ids = []
        for r in rows:
            combined = (r[2] or "") + " " + (r[1] or "") + " " + (r[3] or "")
            if combined.strip() and not jp_re.search(combined):
                non_jp_ids.append(r[0])
        step = {"name": "delete_foreign_ads", "found": len(non_jp_ids)}
        if non_jp_ids and not dry_run:
            for table in ["ad_daily_metrics", "product_rankings"]:
                session.execute(text(f"DELETE FROM {table} WHERE ad_id = ANY(:ids)"), {"ids": non_jp_ids})
            session.execute(text("DELETE FROM ads WHERE id = ANY(:ids)"), {"ids": non_jp_ids})
            session.commit()
            step["deleted"] = len(non_jp_ids)
        return step

    def _step_deduplicate(session):
        dup_rows = session.execute(text("""
            SELECT title, advertiser_name, array_agg(id ORDER BY id) as ids, count(*) as cnt
            FROM ads
            WHERE title IS NOT NULL AND title != ''
            GROUP BY title, advertiser_name
            HAVING count(*) > 1
        """)).fetchall()
        all_dup_ids = []
        for g in dup_rows:
            ids = list(g[2])
            keep_id = min(ids)
            all_dup_ids.extend(i for i in ids if i != keep_id)
        step = {"name": "deduplicate", "groups": len(dup_rows), "to_delete": len(all_dup_ids)}
        if all_dup_ids and not dry_run:
            for table in ["ad_daily_metrics", "product_rankings"]:
                session.execute(text(f"DELETE FROM {table} WHERE ad_id = ANY(:ids)"), {"ids": all_dup_ids})
            session.execute(text("DELETE FROM ads WHERE id = ANY(:ids)"), {"ids": all_dup_ids})
            session.commit()
            step["deleted"] = len(all_dup_ids)
        return step

    def _step_fix_creative_type(session):
        if not dry_run:
            r1 = session.execute(text("""
                UPDATE ads SET creative_type = 'video'
                WHERE creative_type = 'unknown'
                AND video_url IS NOT NULL AND video_url != ''
            """))
            r2 = session.execute(text("""
                UPDATE ads SET creative_type = 'image'
                WHERE creative_type = 'unknown'
                AND (image_url IS NOT NULL AND image_url != '')
            """))
            r3 = session.execute(text("""
                UPDATE ads SET creative_type = 'image'
                WHERE creative_type = 'unknown'
                AND (thumbnail_url IS NOT NULL AND thumbnail_url != '')
            """))
            r4 = session.execute(text("""
                DELETE FROM ads WHERE creative_type = 'unknown'
                AND image_url IS NULL AND video_url IS NULL AND thumbnail_url IS NULL
                AND snapshot_url IS NULL
            """))
            session.commit()
            return {"name": "fix_creative_type", "to_video": r1.rowcount, "to_image": r2.rowcount + r3.rowcount, "deleted_empty": r4.rowcount}
        cnt = session.execute(text("SELECT count(*) FROM ads WHERE creative_type = 'unknown'")).scalar()
        return {"name": "fix_creative_type", "unknown_count": cnt}

    def _step_flag_remaining(session):
        if not dry_run:
            remaining = session.execute(text("SELECT id, title, advertiser_name, description FROM ads")).fetchall()
            flag_ids = []
            for r in remaining:
                combined = (r[1] or "") + " " + (r[2] or "") + " " + (r[3] or "")
                if combined.strip() and not jp_re.search(combined):
                    flag_ids.append(r[0])
            if flag_ids:
                session.execute(text("""
                    UPDATE ads SET ad_metadata = COALESCE(ad_metadata, '{}'::jsonb) || '{"language": "non-ja", "exclude_from_analysis": true}'::jsonb
                    WHERE id = ANY(:ids)
                """), {"ids": flag_ids})
                session.commit()
            return {"name": "flag_remaining_foreign", "flagged": len(flag_ids)}
        return {"name": "flag_remaining_foreign", "skipped": True}

    # Run each step in its own session/transaction
    for step_fn in [_step_delete_foreign, _step_deduplicate, _step_fix_creative_type, _step_flag_remaining]:
        session = SyncSessionLocal()
        try:
            step_result = step_fn(session)
            results["steps"].append(step_result)
        except Exception as e:
            session.rollback()
            logger.error("cleanup_step_error", step=step_fn.__name__, error=str(e), exc_info=True)
            results["steps"].append({"name": step_fn.__name__, "error": _safe_error(e)})
        finally:
            session.close()

    # Summary (separate session)
    session = SyncSessionLocal()
    try:
        total = session.execute(text("SELECT count(*) FROM ads")).scalar()
        ct_dist = session.execute(text(
            "SELECT creative_type, count(*) FROM ads GROUP BY creative_type ORDER BY count(*) DESC"
        )).fetchall()
        results["final_count"] = total
        results["creative_type_distribution"] = {r[0] or "NULL": r[1] for r in ct_dist}

        samples = session.execute(text(
            "SELECT id, title, advertiser_name, thumbnail_url, image_url, snapshot_url, status FROM ads LIMIT 5"
        )).fetchall()
        results["sample_ads"] = [
            {"id": s[0], "title": (s[1] or "")[:50], "advertiser": (s[2] or "")[:30],
             "has_thumb": bool(s[3]), "has_image": bool(s[4]), "has_snapshot": bool(s[5]),
             "status": str(s[6])} for s in samples
        ]
    except Exception as e:
        logger.error("cleanup_summary_error", error=str(e))
    finally:
        session.close()

    return {"statusCode": 200, "body": json.dumps(results, default=str)}


def _run_extract_media(event: dict) -> dict:
    """Batch dispatch media extraction for ads with pending status."""
    from sqlalchemy import text
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad, MediaExtractionStatus
    from app.tasks.dispatcher import dispatch_task

    limit = event.get("limit", 50)
    statuses = event.get("statuses", ["pending", "pending_heavy"])

    session = SyncSessionLocal()
    try:
        # Reset ads that have no image_s3_key back to pending for re-extraction
        if event.get("reset_no_image"):
            reset_result = session.execute(text("""
                UPDATE ads SET media_extraction_status = 'pending',
                    snapshot_url = NULL
                WHERE image_s3_key IS NULL
                AND (media_extraction_status IN ('completed', 'dispatched', 'failed', 'skipped'))
                AND (external_id IS NOT NULL)
            """))
            session.commit()
            logger.info("reset_no_image_ads", count=reset_result.rowcount)

        rows = session.execute(text("""
            SELECT id, external_id, snapshot_url, media_extraction_status
            FROM ads
            WHERE media_extraction_status = ANY(:statuses)
            AND (snapshot_url IS NOT NULL OR external_id IS NOT NULL)
            ORDER BY id
            LIMIT :limit
        """), {"statuses": statuses, "limit": limit}).fetchall()

        dispatched = []
        errors = []
        for row in rows:
            ad_id = row[0]
            try:
                result = dispatch_task("extract_media", ad_id=ad_id)
                # Mark as dispatched to prevent re-dispatching
                session.execute(text(
                    "UPDATE ads SET media_extraction_status = :status WHERE id = :id"
                ), {"status": MediaExtractionStatus.DISPATCHED, "id": ad_id})
                dispatched.append({"ad_id": ad_id, "message_id": result.id})
            except Exception as e:
                errors.append({"ad_id": ad_id, "error": str(e)})
                logger.error("extract_media_dispatch_failed", ad_id=ad_id, error=str(e))

        # Commit all status updates
        if dispatched:
            session.commit()

        remaining = session.execute(text("""
            SELECT count(*) FROM ads
            WHERE media_extraction_status = ANY(:statuses)
        """), {"statuses": statuses}).scalar()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "dispatched": len(dispatched),
                "errors": len(errors),
                "remaining": remaining,
                "details": dispatched[:10],
                "error_details": errors[:10],
            }, default=str)
        }
    except Exception as e:
        logger.error("extract_media_batch_error", error=str(e), exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": _safe_error(e)})}
    finally:
        session.close()


def _update_api_key(event: dict) -> dict:
    """Update API key in platform_api_keys table."""
    from sqlalchemy import text
    from app.core.database import SyncSessionLocal

    platform = event.get("platform", "")
    key_name = event.get("key_name", "access_token")
    key_value = event.get("key_value", "")

    if not platform or not key_value:
        return {"statusCode": 400, "body": json.dumps({"error": "platform and key_value required"})}

    db = SyncSessionLocal()
    try:
        result = db.execute(text(
            "UPDATE platform_api_keys SET key_value = :value, updated_at = NOW() "
            "WHERE platform = :platform AND key_name = :key_name"
        ), {"value": key_value, "platform": platform, "key_name": key_name})

        if result.rowcount == 0:
            db.execute(text(
                "INSERT INTO platform_api_keys (platform, key_name, key_value, is_active) "
                "VALUES (:platform, :key_name, :value, true)"
            ), {"platform": platform, "key_name": key_name, "value": key_value})

        db.commit()
        return {"statusCode": 200, "body": json.dumps({"status": "updated", "platform": platform, "key_name": key_name})}
    except Exception as e:
        db.rollback()
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        db.close()


def _download_thumbnails_inline(session):
    """Download thumbnails for ads that have thumbnail_url but no image_s3_key.

    Called during crawl to grab images while fbcdn URLs are still fresh.
    """
    import hashlib
    import uuid
    import httpx

    from app.models.ad import Ad

    ads = session.query(Ad).filter(
        Ad.thumbnail_url.isnot(None),
        Ad.image_s3_key.is_(None),
    ).limit(50).all()

    if not ads:
        return

    from app.core.storage import get_storage_client
    storage = get_storage_client()

    downloaded = 0
    for ad in ads:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                r = client.get(ad.thumbnail_url)
                r.raise_for_status()
                data = r.content

            if data and len(data) > 200:
                url_hash = hashlib.md5(ad.thumbnail_url.encode()).hexdigest()[:12]
                s3_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
                storage.upload_bytes(s3_key, data, content_type="image/jpeg")
                ad.image_s3_key = s3_key
                ad.thumbnail_s3_key = s3_key
                if ad.creative_type == "unknown":
                    ad.creative_type = "image"
                ad.media_extraction_status = "completed"
                downloaded += 1
        except Exception as e:
            logger.debug("inline_thumbnail_download_failed", ad_id=ad.id, error=str(e))

    if downloaded:
        session.commit()
        logger.info("inline_thumbnails_downloaded", count=downloaded, total=len(ads))


def _refresh_thumbnails(event: dict) -> dict:
    """Re-fetch thumbnail URLs from Graph API and download them for existing ads.

    For ads that have external_id but no image_s3_key, this:
    1. Queries the Graph API for fresh ad_creative_link_thumbnails
    2. Downloads the thumbnail immediately (before fbcdn token expires)
    3. Uploads to S3 and updates DB
    """
    import hashlib
    import uuid
    import httpx
    from sqlalchemy import text
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    limit = event.get("limit", 50)
    session = SyncSessionLocal()

    try:
        # Get access token
        token_row = session.execute(text(
            "SELECT key_value FROM platform_api_keys "
            "WHERE platform='meta' AND key_name='access_token' AND is_active=true"
        )).first()
        if not token_row:
            return {"statusCode": 400, "body": json.dumps({"error": "No Meta access token in DB"})}
        token = token_row[0]

        # Get ads needing thumbnails
        ads = session.query(Ad).filter(
            Ad.image_s3_key.is_(None),
            Ad.external_id.isnot(None),
        ).order_by(Ad.id).limit(limit).all()

        if not ads:
            return {"statusCode": 200, "body": json.dumps({"message": "No ads need thumbnails", "count": 0})}

        from app.core.storage import get_storage_client
        storage = get_storage_client()

        results = {"total": len(ads), "downloaded": 0, "api_failed": 0, "dl_failed": 0}

        # Batch query Graph API (max 50 IDs per request)
        for i in range(0, len(ads), 50):
            batch = ads[i:i+50]
            ext_ids = [a.external_id for a in batch]
            ad_map = {a.external_id: a for a in batch}

            try:
                with httpx.Client(timeout=30.0) as client:
                    for ext_id in ext_ids:
                        ad = ad_map[ext_id]
                        try:
                            r = client.get(
                                f"https://graph.facebook.com/v25.0/ads_archive",
                                params={
                                    "access_token": token,
                                    "search_terms": "",
                                    "ad_reached_countries": '["JP"]',
                                    "search_page_ids": ext_id.split("_")[0] if "_" in ext_id else "",
                                    "fields": "id,ad_creative_link_thumbnails",
                                    "limit": "1",
                                },
                            )
                            # Graph API search might not find the exact ad
                            # Try direct ad lookup instead
                            r2 = client.get(
                                f"https://graph.facebook.com/v25.0/{ext_id}",
                                params={
                                    "access_token": token,
                                    "fields": "ad_creative_link_thumbnails",
                                },
                            )
                            if r2.status_code == 200:
                                data = r2.json()
                                thumbnails = data.get("ad_creative_link_thumbnails", [])
                                if thumbnails:
                                    thumb_url = thumbnails[0] if isinstance(thumbnails[0], str) else thumbnails[0].get("url", "")
                                    if thumb_url:
                                        # Download immediately
                                        try:
                                            tr = client.get(thumb_url, follow_redirects=True)
                                            tr.raise_for_status()
                                            thumb_data = tr.content
                                            if thumb_data and len(thumb_data) > 200:
                                                url_hash = hashlib.md5(thumb_url.encode()).hexdigest()[:12]
                                                s3_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
                                                storage.upload_bytes(s3_key, thumb_data, content_type="image/jpeg")
                                                ad.image_s3_key = s3_key
                                                ad.thumbnail_s3_key = s3_key
                                                ad.thumbnail_url = thumb_url
                                                if ad.creative_type == "unknown":
                                                    ad.creative_type = "image"
                                                ad.media_extraction_status = "completed"
                                                results["downloaded"] += 1
                                        except Exception:
                                            results["dl_failed"] += 1
                            else:
                                results["api_failed"] += 1
                        except Exception:
                            results["api_failed"] += 1
            except Exception as e:
                logger.error("refresh_thumbnails_batch_error", error=str(e))

        session.commit()
        return {"statusCode": 200, "body": json.dumps(results, default=str)}
    except Exception as e:
        session.rollback()
        logger.error("refresh_thumbnails_error", error=str(e), exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        session.close()
