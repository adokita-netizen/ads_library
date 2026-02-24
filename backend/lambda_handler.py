"""AWS Lambda handler for the FastAPI API (via Mangum)."""

import os
import json

import structlog

logger = structlog.get_logger()

# Ensure DB tables are created on first Lambda cold start
def _init_database():
    """Run database initialization (create tables if they don't exist)."""
    try:
        from app.core.database import sync_engine, Base
        import app.models.ad  # noqa: F401
        import app.models.ad_metrics  # noqa: F401
        import app.models.analysis  # noqa: F401
        import app.models.user  # noqa: F401
        import app.models.landing_page  # noqa: F401
        import app.models.api_key  # noqa: F401
        Base.metadata.create_all(bind=sync_engine)
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
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            return {"statusCode": 200, "body": json.dumps({"status": "migration_complete"})}
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"status": "migration_error", "error": str(e)})}

    return _mangum_handler(event, context)
