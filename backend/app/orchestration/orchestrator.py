"""
Main orchestrator for the ticket → PR pipeline.

Plain Python state machine - no LangGraph dependencies.
"""

import logging
from typing import Callable, Optional, List, Literal
from datetime import datetime

from .state import PipelineState, PipelineStatus
from . import nodes

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    State machine orchestrator for the ticket → PR pipeline.

    Executes pipeline steps sequentially with conditional branching,
    pause/resume capability, and revision loops.
    """

    # Maximum revisions before forcing completion
    MAX_REVISIONS = 3

    def __init__(self):
        """Initialize the orchestrator."""
        self.steps = self._build_pipeline_steps()
        logger.info("PipelineOrchestrator initialized")

    def _build_pipeline_steps(self) -> List[dict]:
        """
        Define the pipeline steps and their flow.

        Each step is a dict with:
        - name: Step name
        - node: Node function to execute
        - next: Next step name (or callable for conditional)
        """
        return [
            {
                'name': 'initialize',
                'node': nodes.initialize_pipeline,
                'next': 'route',
            },
            {
                'name': 'route',
                'node': nodes.route_task,
                'next': 'interpret_ticket',
            },
            {
                'name': 'interpret_ticket',
                'node': nodes.interpret_ticket,
                'next': 'build_context',
            },
            {
                'name': 'build_context',
                'node': nodes.build_context,
                'next': 'check_clarification',
            },
            {
                'name': 'check_clarification',
                'node': nodes.check_clarification,
                'next': self._decide_after_clarification,
            },
            {
                'name': 'generate_plan',
                'node': nodes.generate_plan,
                'next': 'approve_plan',
            },
            {
                'name': 'approve_plan',
                'node': nodes.approve_plan,
                'next': 'check_guardrails',
            },
            {
                'name': 'check_guardrails',
                'node': nodes.check_guardrails,
                'next': self._decide_after_guardrails,
            },
            {
                'name': 'generate_code',
                'node': nodes.generate_code,
                'next': 'generate_tests',
            },
            {
                'name': 'generate_tests',
                'node': nodes.generate_tests,
                'next': 'verify_execution',
            },
            {
                'name': 'verify_execution',
                'node': nodes.verify_execution,
                'next': 'review_implementation',
            },
            {
                'name': 'review_implementation',
                'node': nodes.review_implementation,
                'next': self._decide_after_review,
            },
            {
                'name': 'store_memory',
                'node': nodes.store_memory,
                'next': 'finalize',
            },
            {
                'name': 'finalize',
                'node': nodes.finalize_pipeline,
                'next': None,  # Terminal node
            },
        ]

    def _decide_after_clarification(self, state: PipelineState) -> Optional[str]:
        """Decide next step after clarification check."""
        if state.waiting or state.clarification_needed:
            # Pause pipeline - will resume from generate_plan
            logger.info(f"[{state.task_id}] Pausing for clarification")
            return None  # None means pause
        return 'generate_plan'

    def _decide_after_guardrails(self, state: PipelineState) -> Optional[str]:
        """Decide next step after guardrails check."""
        if state.blocked:
            logger.warning(f"[{state.task_id}] Blocked by guardrails")
            return None  # Terminal - blocked
        return 'generate_code'

    def _decide_after_review(self, state: PipelineState) -> Optional[str]:
        """Decide next step after review."""
        if state.needs_revision and state.revision_count < self.MAX_REVISIONS:
            logger.info(
                f"[{state.task_id}] Revision needed "
                f"(attempt {state.revision_count + 1}/{self.MAX_REVISIONS})"
            )
            return 'generate_code'  # Loop back to coding
        elif state.needs_revision and state.revision_count >= self.MAX_REVISIONS:
            logger.warning(
                f"[{state.task_id}] Max revisions reached, forcing completion"
            )
            return 'store_memory'
        else:
            return 'store_memory'

    async def run(
        self,
        state: PipelineState,
        start_from: Optional[str] = None
    ) -> PipelineState:
        """
        Run the pipeline from start to finish (or until pause).

        Args:
            state: Initial or resumed pipeline state
            start_from: Optional step name to start from (for resume)

        Returns:
            Final pipeline state
        """
        logger.info(f"[{state.task_id}] Starting pipeline execution")

        # Set status to running
        state.status = PipelineStatus.RUNNING

        # Find starting step
        current_step_name = start_from or 'initialize'
        step_index = self._find_step_index(current_step_name)

        if step_index is None:
            raise ValueError(f"Invalid start step: {current_step_name}")

        # Execute pipeline
        while step_index is not None:
            step = self.steps[step_index]
            step_name = step['name']
            node_func = step['node']
            next_step = step['next']

            logger.info(f"[{state.task_id}] Executing step: {step_name}")

            try:
                # Execute node
                await node_func(state)

                # Check for terminal conditions
                if state.blocked:
                    logger.warning(f"[{state.task_id}] Pipeline blocked, stopping")
                    break

                if state.waiting:
                    logger.info(f"[{state.task_id}] Pipeline waiting, pausing")
                    break

                # Determine next step
                if callable(next_step):
                    # Conditional routing
                    next_step_name = next_step(state)
                else:
                    # Direct routing
                    next_step_name = next_step

                if next_step_name is None:
                    # Terminal node or pause
                    logger.info(f"[{state.task_id}] Reached terminal node: {step_name}")
                    break

                # Move to next step
                step_index = self._find_step_index(next_step_name)

            except Exception as e:
                logger.error(
                    f"[{state.task_id}] Error in step {step_name}: {e}",
                    exc_info=True
                )
                state.add_error(f"{step_name}: {str(e)}")
                state.mark_blocked(f"Exception in {step_name}: {str(e)}")
                break

        logger.info(
            f"[{state.task_id}] Pipeline execution completed with status: {state.status}"
        )

        return state

    async def resume(
        self,
        state: PipelineState,
        clarification_answer: Optional[str] = None,
        pr_feedback: Optional[str] = None
    ) -> PipelineState:
        """
        Resume a paused pipeline.

        Args:
            state: Previously paused state
            clarification_answer: Answer to clarification (if applicable)
            pr_feedback: PR review feedback (if applicable)

        Returns:
            Final state after resumption
        """
        logger.info(f"[{state.task_id}] Resuming pipeline")

        # Update state with input
        if clarification_answer:
            state.clarification_answer = clarification_answer
            state.clarification_needed = False
            state.waiting = False
            state.status = PipelineStatus.RUNNING

            # Resume from planning
            return await self.run(state, start_from='generate_plan')

        elif pr_feedback:
            state.review_feedback.append(pr_feedback)
            state.needs_revision = True
            state.status = PipelineStatus.RUNNING

            # Resume from coding (revision loop)
            return await self.run(state, start_from='generate_code')

        else:
            # Generic resume - continue from current state
            state.status = PipelineStatus.RUNNING
            return await self.run(state)

    def _find_step_index(self, step_name: str) -> Optional[int]:
        """Find the index of a step by name."""
        for i, step in enumerate(self.steps):
            if step['name'] == step_name:
                return i
        return None

    def get_current_step(self, state: PipelineState) -> Optional[str]:
        """
        Determine the current step from state.

        Useful for resuming pipelines.
        """
        # Check last event
        if state.events:
            last_event = state.events[-1]
            if last_event['event_type'] == 'agent_start':
                return last_event['agent_name']

        # Determine from state flags
        if state.waiting:
            return 'check_clarification'
        elif state.plan and not state.pr_url:
            return 'generate_code'
        elif state.pr_url and not state.review_passed:
            return 'review_implementation'

        return None

    def visualize(self) -> str:
        """
        Generate a text visualization of the pipeline flow.

        Returns:
            ASCII diagram of the pipeline
        """
        lines = ["Pipeline Flow:", ""]

        for i, step in enumerate(self.steps):
            name = step['name']
            next_step = step['next']

            # Format step
            lines.append(f"{i+1}. {name}")

            # Format next step
            if next_step is None:
                lines.append("   └─▶ [END]")
            elif callable(next_step):
                lines.append("   └─▶ [CONDITIONAL]")
            else:
                lines.append(f"   └─▶ {next_step}")

            lines.append("")

        return "\n".join(lines)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


_orchestrator_instance: Optional[PipelineOrchestrator] = None


def get_orchestrator() -> PipelineOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = PipelineOrchestrator()

    return _orchestrator_instance


async def run_pipeline(
    task_id: str,
    org_id: str,
    task_description: str,
    user_id: Optional[str] = None
) -> PipelineState:
    """
    Run the pipeline for a new task.

    Args:
        task_id: Task ID
        org_id: Organization ID
        task_description: Task description/requirements
        user_id: Optional user ID

    Returns:
        Final pipeline state
    """
    # Create initial state
    state = PipelineState(
        task_id=task_id,
        org_id=org_id,
        task_description=task_description,
        user_id=user_id,
        created_at=datetime.utcnow(),
    )

    # Run pipeline
    orchestrator = get_orchestrator()
    final_state = await orchestrator.run(state)

    return final_state


async def resume_pipeline(
    state: PipelineState,
    clarification_answer: Optional[str] = None,
    pr_feedback: Optional[str] = None
) -> PipelineState:
    """
    Resume a paused pipeline.

    Args:
        state: Previously saved state
        clarification_answer: Answer to clarification
        pr_feedback: PR review feedback

    Returns:
        Final state after resumption
    """
    orchestrator = get_orchestrator()
    return await orchestrator.resume(
        state,
        clarification_answer=clarification_answer,
        pr_feedback=pr_feedback
    )


def visualize_pipeline() -> str:
    """Get a text visualization of the pipeline flow."""
    orchestrator = get_orchestrator()
    return orchestrator.visualize()
