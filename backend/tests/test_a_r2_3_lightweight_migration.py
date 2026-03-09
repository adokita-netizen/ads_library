import importlib
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_run_migrations_adds_product_ranking_score_columns():
    try:
        database_mod = importlib.import_module("app.core.database")
    except Exception:
        database_mod = None
    if database_mod is None or not hasattr(database_mod, "_run_migrations"):
        database_path = Path(__file__).resolve().parents[1] / "app" / "core" / "database.py"
        spec = importlib.util.spec_from_file_location("database_mod_test", database_path)
        assert spec and spec.loader
        database_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(database_mod)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE product_rankings (
                    id INTEGER PRIMARY KEY,
                    period VARCHAR(20),
                    period_start DATE,
                    period_end DATE,
                    ad_id BIGINT,
                    product_name VARCHAR(255),
                    advertiser_name VARCHAR(255),
                    genre VARCHAR(100),
                    platform VARCHAR(50),
                    rank_position INTEGER,
                    previous_rank INTEGER,
                    rank_change INTEGER,
                    total_view_increase BIGINT,
                    total_spend_increase FLOAT,
                    cumulative_views BIGINT,
                    cumulative_spend FLOAT,
                    is_hit BOOLEAN,
                    hit_score FLOAT,
                    metadata JSON,
                    created_at DATETIME
                )
                """
            )
        )

    database_mod._run_migrations(engine)

    cols = {c["name"] for c in inspect(engine).get_columns("product_rankings")}
    assert "score_delta" in cols
    assert "trend_score" in cols
