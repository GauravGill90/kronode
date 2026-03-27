"""
Multi-Flow Orchestrator - Main entry point for all flows.

Implements the complete architecture:
1. Receive input
2. Validate (FlowClassifier)
3. Classify to flow (FlowClassifier + LLM)
4. Check confidence (FlowClassifier)
5. Lookup flow (FlowRegistry)
6. Execute flow (LangGraph)
7. Return result
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .core.classifier import FlowClassifier, ClassificationResult
from .core.flow_registry import FlowRegistry
from .state import PipelineState, PipelineStatus
from . import flows  # Import to trigger flow registration

logger = logging.getLogger(__name__)


class MultiFlowOrchestrator:
    """
    Main orchestrator supporting multiple flows.

    Uses FlowClassifier + FlowRegistry + LangGraph for execution.
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.classifier = FlowClassifier()
        logger.info("MultiFlowOrchestrator initialized")

        # Trigger flow registration
        logger.info(f"Registered flows: {FlowRegistry.all()}")

    async def execute(
        self,
        input_data: Dict[str, Any],
        resume_state: Optional[PipelineState] = None
    ) -> PipelineState:
        """
        Execute a flow based on input classification.

        This implements the complete architecture diagram.

        Args:
            input_data: Input data with org_id, action, description, etc.
            resume_state: Optional state to resume from (for paused pipelines)

        Returns:
            Final pipeline state after execution

        Raises:
            ValueError: If input is invalid
            RuntimeError: If flow execution fails
        """
        # If resuming, skip classification
        if resume_state:
            logger.info(
                f"[{resume_state.task_id}] Resuming flow: {resume_state.flow_name}"
            )
            return await self._execute_flow(resume_state)

        # ====================================================================
        # STEP 2-4: CLASSIFY INPUT
        # ====================================================================

        logger.info("Classifying input to determine flow")

        try:
            classification: ClassificationResult = await self.classifier.classify(
                input_data
            )
        except ValueError as e:
            logger.error(f"Classification failed: {e}")
            raise

        logger.info(
            f"Classified to flow '{classification.flow_name}' "
            f"with confidence {classification.confidence:.2f}"
        )

        # ====================================================================
        # STEP 5: LOOKUP FLOW IN REGISTRY
        # ====================================================================

        flow = FlowRegistry.get(classification.flow_name)

        if flow is None:
            logger.error(f"Flow not found: {classification.flow_name}")
            raise RuntimeError(
                f"Flow '{classification.flow_name}' is not registered. "
                f"Available flows: {FlowRegistry.all()}"
            )

        logger.info(f"Found flow: {flow.name} - {flow.description}")

        # ====================================================================
        # CREATE INITIAL STATE
        # ====================================================================

        state = PipelineState(
            task_id=input_data.get('task_id', self._generate_task_id()),
            org_id=input_data['org_id'],
            task_description=input_data.get('task_description', ''),
            user_id=input_data.get('user_id'),
            created_at=datetime.utcnow(),
            flow_name=classification.flow_name,
            classification_confidence=classification.confidence,
            status=PipelineStatus.QUEUED
        )

        # Add classification metadata
        state.add_event("flow_classified", "orchestrator", {
            "flow_name": classification.flow_name,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning
        })

        # ====================================================================
        # STEP 6-7: EXECUTE FLOW
        # ====================================================================

        return await self._execute_flow(state, flow)

    async def _execute_flow(
        self,
        state: PipelineState,
        flow: Optional['Flow'] = None
    ) -> PipelineState:
        """
        Execute a specific flow with LangGraph.

        Args:
            state: Pipeline state
            flow: Flow to execute (if None, lookup from state.flow_name)

        Returns:
            Final state after execution
        """
        # Lookup flow if not provided
        if flow is None:
            if not state.flow_name:
                raise ValueError("State has no flow_name and no flow provided")

            flow = FlowRegistry.get(state.flow_name)
            if flow is None:
                raise RuntimeError(f"Flow not found: {state.flow_name}")

        logger.info(
            f"[{state.task_id}] Executing flow: {flow.name} ({flow.description})"
        )

        try:
            # Execute flow (LangGraph handles the state graph execution)
            final_state = await flow.execute(state, PipelineState)

            logger.info(
                f"[{state.task_id}] Flow execution completed: {final_state.status}"
            )

            return final_state

        except Exception as e:
            logger.error(
                f"[{state.task_id}] Flow execution failed: {e}",
                exc_info=True
            )

            # Update state with error
            state.add_error(f"Flow execution failed: {str(e)}")
            state.mark_blocked(f"Flow execution error: {str(e)}")

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

        if pr_feedback:
            state.review_feedback.append(pr_feedback)
            state.needs_revision = True

        # Reset status to running
        state.status = PipelineStatus.RUNNING

        # Resume execution
        return await self._execute_flow(state)

    def get_flow_info(self) -> Dict[str, Dict]:
        """
        Get information about all registered flows.

        Returns:
            Dict mapping flow names to their metadata
        """
        return FlowRegistry.get_info()

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        import uuid
        return f"task_{uuid.uuid4().hex[:12]}"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_orchestrator_instance: Optional[MultiFlowOrchestrator] = None


def get_orchestrator() -> MultiFlowOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = MultiFlowOrchestrator()

    return _orchestrator_instance


async def run_pipeline(
    org_id: str,
    action: Optional[str] = None,
    task_description: Optional[str] = None,
    task_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
) -> PipelineState:
    """
    Run a pipeline by classifying and executing the appropriate flow.

    Args:
        org_id: Organization ID (required)
        action: Action type (implement, onboard, ingest, etc.)
        task_description: Task description
        task_id: Optional task ID
        user_id: Optional user ID
        **kwargs: Additional context

    Returns:
        Final pipeline state
    """
    # Build input data
    input_data = {
        'org_id': org_id,
        'action': action,
        'task_description': task_description,
        'task_id': task_id,
        'user_id': user_id,
        **kwargs
    }

    # Execute
    orchestrator = get_orchestrator()
    return await orchestrator.execute(input_data)


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


def get_flow_info() -> Dict[str, Dict]:
    """Get information about all registered flows."""
    orchestrator = get_orchestrator()
    return orchestrator.get_flow_info()
