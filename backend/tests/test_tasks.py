"""Tests for Celery task module imports and structure."""

import os
import pytest

celery = pytest.importorskip("celery", reason="celery not installed")


class TestTaskModuleImports:
    """Verify all task modules can be imported without errors."""

    def test_import_generation_tasks(self):
        from app.tasks.generation_tasks import generate_script_task, generate_copy_task
        assert callable(generate_script_task)
        assert callable(generate_copy_task)

    def test_import_ranking_tasks(self):
        from app.tasks.ranking_tasks import compute_rankings_task
        assert callable(compute_rankings_task)

    def test_import_alert_tasks(self):
        from app.tasks.alert_tasks import detect_alerts_task
        assert callable(detect_alerts_task)

    def test_import_analysis_tasks(self):
        from app.tasks.analysis_tasks import analyze_ad_task
        assert callable(analyze_ad_task)

    def test_import_crawl_tasks(self):
        from app.tasks.crawl_tasks import crawl_ads_task
        assert callable(crawl_ads_task)


class TestTaskAttributes:
    """Verify task configuration attributes."""

    def test_generation_task_names(self):
        from app.tasks.generation_tasks import generate_script_task, generate_copy_task
        assert generate_script_task.name == "app.tasks.generation_tasks.generate_script_task"
        assert generate_copy_task.name == "app.tasks.generation_tasks.generate_copy_task"

    def test_ranking_task_name(self):
        from app.tasks.ranking_tasks import compute_rankings_task
        assert compute_rankings_task.name == "app.tasks.ranking_tasks.compute_rankings_task"

    def test_alert_task_name(self):
        from app.tasks.alert_tasks import detect_alerts_task
        assert detect_alerts_task.name == "app.tasks.alert_tasks.detect_alerts_task"


class TestWorkerConfiguration:
    """Test Celery worker configuration."""

    def test_worker_imports(self):
        from app.tasks.worker import celery_app
        assert celery_app is not None

    def test_beat_schedule_configured(self):
        from app.tasks.worker import celery_app
        beat = celery_app.conf.beat_schedule
        assert "crawl-daily-all-platforms" in beat
        assert "compute-daily-rankings" in beat
        assert "detect-daily-alerts" in beat

    def test_beat_schedule_tasks_valid(self):
        from app.tasks.worker import celery_app
        beat = celery_app.conf.beat_schedule

        assert beat["crawl-daily-all-platforms"]["task"] == "app.tasks.crawl_tasks.crawl_ads_task"
        assert beat["compute-daily-rankings"]["task"] == "app.tasks.ranking_tasks.compute_rankings_task"
        assert beat["detect-daily-alerts"]["task"] == "app.tasks.alert_tasks.detect_alerts_task"


class TestMigrationFile:
    """Verify migration file exists and is valid."""

    def test_migration_file_exists(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "migrations", "versions", "001_initial_schema.py"
        )
        assert os.path.exists(path), "Initial migration file should exist"

    def test_migration_file_has_upgrade_and_downgrade(self):
        """Check file content for upgrade/downgrade functions without importing alembic."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "migrations", "versions", "001_initial_schema.py"
        )
        with open(path) as f:
            content = f.read()
        assert "def upgrade()" in content, "Migration should have upgrade()"
        assert "def downgrade()" in content, "Migration should have downgrade()"
        assert "op.create_table" in content, "Migration should create tables"
