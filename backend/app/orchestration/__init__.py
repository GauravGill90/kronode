"""
Orchestration module for the ticket → PR pipeline.

Plain Python state machine - no external dependencies required.

Usage:
    from app.orchestration import run_pipeline, resume_pipeline, PipelineState

    # Run a new pipeline
    final_state = await run_pipeline(
        task_id="task-123",
        org_id="org-456",
        task_description="Add user authentication"
    )

    # Resume from clarification
    final_state = await resume_pipeline(
        state,
        clarification_answer="Use OAuth2"
    )

    # Visualize pipeline flow
    from app.orchestration import visualize_pipeline
    print(visualize_pipeline())
"""

# State schema
from .state import PipelineState, PipelineStatus, TaskComplexity

# Orchestrator
from .orchestrator import (
    PipelineOrchestrator,
    get_orchestrator,
    run_pipeline,
    resume_pipeline,
    visualize_pipeline,
)

# Celery integration
from .celery_integration import (
    run_pipeline_task,
    resume_pipeline_task,
    cancel_pipeline_task,
    poll_clarifications_task,
    poll_pr_outcomes_task,
)

__all__ = [
    # State
    "PipelineState",
    "PipelineStatus",
    "TaskComplexity",
    # Orchestrator
    "PipelineOrchestrator",
    "get_orchestrator",
    # Main functions
    "run_pipeline",
    "resume_pipeline",
    "visualize_pipeline",
    # Celery tasks
    "run_pipeline_task",
    "resume_pipeline_task",
    "cancel_pipeline_task",
    "poll_clarifications_task",
    "poll_pr_outcomes_task",
]
