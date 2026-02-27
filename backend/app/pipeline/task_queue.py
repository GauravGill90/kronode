import asyncio

from app.celery_app import celery_app


@celery_app.task(name="run_pipeline", bind=True, max_retries=0)
def run_pipeline(self, task_id: str):
    from app.pipeline.pipeline import run_pipeline as _run_pipeline
    asyncio.run(_run_pipeline(task_id))
