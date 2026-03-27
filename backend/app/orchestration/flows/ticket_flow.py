"""
Ticket Implementation Flow - From ticket → PR.

Migrates the existing 14-step pipeline to LangGraph flow format.
"""

import logging
from typing import Dict, Any, List
from langgraph.graph import END

from ..core.base import Flow, FlowStep
from ..core.flow_registry import FlowRegistry
from ..state import PipelineState
from .. import nodes

logger = logging.getLogger(__name__)


class TicketImplementationFlow(Flow):
    """
    Flow for implementing a ticket and creating a PR.

    Steps:
    1. Initialize pipeline
    2. Route task (determine complexity)
    3. Interpret ticket
    4. Build context (repo tree, conventions)
    5. Check clarification (pause if needed)
    6. Generate plan
    7. Approve plan (post to Slack/Jira)
    8. Check guardrails
    9. Generate code (create PR)
    10. Generate tests
    11. Verify execution (build, test, lint)
    12. Review implementation (loop back if needed)
    13. Store memory (learn patterns)
    14. Finalize pipeline
    """

    name = "ticket_implementation"
    description = "Implement a ticket and create a PR with full verification"

    # Maximum revisions before forcing completion
    MAX_REVISIONS = 3

    def __init__(self):
        """Initialize the flow."""
        super().__init__()
        logger.info(f"Initialized {self.name} flow")

    def get_steps(self) -> List[FlowStep]:
        """
        Define the 14 steps for ticket implementation.

        Returns:
            List of FlowStep objects
        """
        return [
            # Step 1-2: Initialize and route
            FlowStep(
                name="initialize",
                node=nodes.initialize_pipeline,
                next="route",
                description="Initialize pipeline state"
            ),
            FlowStep(
                name="route",
                node=nodes.route_task,
                next="interpret_ticket",
                description="Determine task complexity and agents"
            ),

            # Step 3-4: Interpret and build context
            FlowStep(
                name="interpret_ticket",
                node=nodes.interpret_ticket,
                next="build_context",
                description="Parse ticket requirements"
            ),
            FlowStep(
                name="build_context",
                node=nodes.build_context,
                next="check_clarification",
                description="Fetch repo tree and conventions"
            ),

            # Step 5: Clarification check (conditional pause)
            FlowStep(
                name="check_clarification",
                node=nodes.check_clarification,
                next=self._decide_after_clarification,
                description="Check if user clarification needed"
            ),

            # Step 6-7: Planning
            FlowStep(
                name="generate_plan",
                node=nodes.generate_plan,
                next="approve_plan",
                description="Generate implementation plan"
            ),
            FlowStep(
                name="approve_plan",
                node=nodes.approve_plan,
                next="check_guardrails",
                description="Post plan to Slack/Jira for visibility"
            ),

            # Step 8: Guardrails check (conditional block)
            FlowStep(
                name="check_guardrails",
                node=nodes.check_guardrails,
                next=self._decide_after_guardrails,
                description="Validate plan against guardrails"
            ),

            # Step 9-11: Implementation
            FlowStep(
                name="generate_code",
                node=nodes.generate_code,
                next="generate_tests",
                description="Generate code and create PR"
            ),
            FlowStep(
                name="generate_tests",
                node=nodes.generate_tests,
                next="verify_execution",
                description="Generate unit and integration tests"
            ),
            FlowStep(
                name="verify_execution",
                node=nodes.verify_execution,
                next="review_implementation",
                description="Run build, tests, and linting"
            ),

            # Step 12: Review (conditional loop)
            FlowStep(
                name="review_implementation",
                node=nodes.review_implementation,
                next=self._decide_after_review,
                description="Review against Definition of Done"
            ),

            # Step 13-14: Finalize
            FlowStep(
                name="store_memory",
                node=nodes.store_memory,
                next="finalize",
                description="Store learned patterns and pitfalls"
            ),
            FlowStep(
                name="finalize",
                node=nodes.finalize_pipeline,
                next=None,  # Terminal node
                description="Set final status and cleanup"
            ),
        ]

    async def can_handle(self, context: Dict[str, Any]) -> bool:
        """
        Check if this flow can handle the given input.

        This flow handles ticket implementation requests:
        - Has 'action' field with 'implement' or similar
        - Has 'task_description' or 'ticket_id'
        - Is a task execution request (not onboarding or ingestion)

        Args:
            context: Input context with org_id, action, etc.

        Returns:
            True if this flow should handle this request
        """
        # Check for explicit action
        action = context.get('action', '').lower()
        if action in ['implement', 'ticket', 'feature', 'bugfix', 'fix']:
            return True

        # Check for task description (implicit ticket)
        if context.get('task_description') or context.get('ticket_id'):
            return True

        # Check for PR-related fields
        if context.get('pr_number') or context.get('branch_name'):
            return True

        return False

    # ========================================================================
    # CONDITIONAL ROUTING FUNCTIONS
    # ========================================================================

    def _decide_after_clarification(self, state: Dict[str, Any]) -> str:
        """
        Decide next step after clarification check.

        Args:
            state: Current pipeline state (dict from LangGraph)

        Returns:
            Next node name or END
        """
        # LangGraph passes state as dict, not PipelineState object
        waiting = state.get('waiting', False)
        clarification_needed = state.get('clarification_needed', False)

        if waiting or clarification_needed:
            # Pause pipeline - user needs to provide clarification
            logger.info(f"[{state.get('task_id')}] Pausing for clarification")
            return END

        # Continue to planning
        return "generate_plan"

    def _decide_after_guardrails(self, state: Dict[str, Any]) -> str:
        """
        Decide next step after guardrails check.

        Args:
            state: Current pipeline state

        Returns:
            Next node name or END
        """
        blocked = state.get('blocked', False)

        if blocked:
            # Pipeline blocked by guardrails
            logger.warning(f"[{state.get('task_id')}] Blocked by guardrails")
            return END

        # Continue to code generation
        return "generate_code"

    def _decide_after_review(self, state: Dict[str, Any]) -> str:
        """
        Decide next step after review.

        Implements revision loop - if review fails and under max revisions,
        loop back to code generation.

        Args:
            state: Current pipeline state

        Returns:
            Next node name
        """
        needs_revision = state.get('needs_revision', False)
        revision_count = state.get('revision_count', 0)

        if needs_revision and revision_count < self.MAX_REVISIONS:
            # Loop back for revision
            logger.info(
                f"[{state.get('task_id')}] Revision needed "
                f"(attempt {revision_count + 1}/{self.MAX_REVISIONS})"
            )
            return "generate_code"

        elif needs_revision and revision_count >= self.MAX_REVISIONS:
            # Max revisions reached, force completion
            logger.warning(
                f"[{state.get('task_id')}] Max revisions reached, forcing completion"
            )
            return "store_memory"

        else:
            # Review passed, continue to memory storage
            return "store_memory"


# ============================================================================
# AUTO-REGISTRATION
# ============================================================================

# Register this flow on import
_flow_instance = TicketImplementationFlow()
FlowRegistry.register(_flow_instance.name, _flow_instance)

logger.info(f"Registered flow: {_flow_instance.name}")
