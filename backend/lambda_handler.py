"""AWS Lambda handler for the FastAPI API (via Mangum)."""

import os
import json

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
    try:
        from app.core.database import sync_engine, Base
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
        Base.metadata.create_all(bind=sync_engine)
        _DB_INITIALIZED = True
    except Exception as e:
        logger.warning("db_init_skipped", error=str(e))

_init_database()

from mangum import Mangum
from app.main import app

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda handler with support for DB migration trigger."""
    # Direct invocation for DB migration
    if isinstance(event, dict) and event.get("action") == "migrate":
        try:
            from alembic.config import Config
            from alembic import command
            from alembic.migration import MigrationContext
            from app.core.database import sync_engine

            alembic_cfg = Config("alembic.ini")

            # Check current alembic version
            with sync_engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()

            if current_rev is None:
                # DB exists but no alembic_version — stamp initial schema, then upgrade
                logger.info("migration_stamp", msg="No alembic version found, stamping 001")
                command.stamp(alembic_cfg, "001")

            command.upgrade(alembic_cfg, "head")
            return {"statusCode": 200, "body": json.dumps({"status": "migration_complete", "from_rev": current_rev})}
        except Exception as e:
            logger.error("migration_error", error=str(e), exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"status": "migration_error", "error": _safe_error(e)})}

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
