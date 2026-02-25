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
            return {"statusCode": 500, "body": json.dumps({"status": "migration_error", "error": str(e)})}

    return _mangum_handler(event, context)
