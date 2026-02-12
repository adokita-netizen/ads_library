"""Celery tasks for creative generation (script, copy, storyboard)."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.generation_tasks.generate_script_task", bind=True, max_retries=2)
def generate_script_task(self, product_name: str, product_description: str, **kwargs):
    """Generate a video ad script asynchronously."""
    from app.services.generative.script_generator import ScriptGenerator

    logger.info("generate_script_start", product=product_name)
    try:
        generator = ScriptGenerator()
        result = generator.generate(
            product_name=product_name,
            product_description=product_description,
            **kwargs,
        )
        logger.info("generate_script_complete", product=product_name)
        return result
    except Exception as exc:
        logger.error("generate_script_failed", product=product_name, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="app.tasks.generation_tasks.generate_copy_task", bind=True, max_retries=2)
def generate_copy_task(self, product_name: str, product_description: str, **kwargs):
    """Generate ad copy asynchronously."""
    from app.services.generative.copy_generator import CopyGenerator

    logger.info("generate_copy_start", product=product_name)
    try:
        generator = CopyGenerator()
        result = generator.generate(
            product_name=product_name,
            product_description=product_description,
            **kwargs,
        )
        logger.info("generate_copy_complete", product=product_name)
        return result
    except Exception as exc:
        logger.error("generate_copy_failed", product=product_name, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
