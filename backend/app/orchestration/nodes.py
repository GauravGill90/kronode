"""
Pipeline step implementations (nodes).

Each node is an async function that takes PipelineState and modifies it in-place.
No return value needed - state is mutable.
"""

import logging
from typing import Dict, Any

from app.agents.router_agent import RouterAgent
from app.agents.ticket_interpreter import TicketInterpreterAgent
from app.agents.context_builder import ContextBuilderAgent
from app.agents.clarification_agent import ClarificationAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.plan_approval_agent import PlanApprovalAgent
from app.agents.guardrails_agent import GuardrailsAgent
from app.agents.coder_agent import CoderAgent
from app.agents.tester_agent import TesterAgent
from app.agents.execution_verifier import ExecutionVerifierAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.memory_agent import MemoryAgent

from .state import PipelineState, PipelineStatus, TaskComplexity

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT LOGGING
# ============================================================================


async def _emit_event(task_id: str, event_type: str, agent_name: str, data: Dict[str, Any] = None):
    """
    Emit event to database.

    TODO: Import actual emit_event from pipeline.py when integrating
    """
    try:
        from app.pipeline.pipeline import emit_event
        await emit_event(task_id, event_type, agent_name, data or {})
    except ImportError:
        # Fallback if not integrated yet
        logger.debug(f"[{task_id}] Event: {event_type} - {agent_name}")


# ============================================================================
# HELPER: BUILD CONTEXT FROM STATE
# ============================================================================


def _build_context(state: PipelineState) -> Dict[str, Any]:
    """
    Build context dict from state for existing agents.

    Maintains compatibility with existing agent interface.
    """
    return {
        "task_id": state.task_id,
        "org_id": state.org_id,
        "user_id": state.user_id,
        "task_description": state.task_description,
        "routing": state.routing,
        "ticket_data": state.ticket_data,
        "repo_tree": state.repo_tree,
        "relevant_files": state.relevant_files,
        "conventions": state.conventions,
        "skills": state.skills,
        "clarification_answer": state.clarification_answer,
        "plan": state.plan,
        "definition_of_done": state.definition_of_done,
        "branch_name": state.branch_name,
        "pr_url": state.pr_url,
        "files_modified": state.files_modified,
        "test_results": state.test_results,
        "review_feedback": state.review_feedback,
        "revision_count": state.revision_count,
        # Include agent-specific context
        **state.context
    }


# ============================================================================
# NODES
# ============================================================================


async def initialize_pipeline(state: PipelineState):
    """Initialize pipeline with default values."""
    logger.info(f"[{state.task_id}] Initializing pipeline")

    state.status = PipelineStatus.RUNNING
    state.add_event("pipeline_start", "orchestrator", {
        "task_id": state.task_id,
        "description": state.task_description
    })


async def route_task(state: PipelineState):
    """Determine task complexity and select agents to run."""
    logger.info(f"[{state.task_id}] Running RouterAgent")

    state.add_event("agent_start", "router_agent", {})

    try:
        context = _build_context(state)
        agent = RouterAgent()
        result = await agent.run(context)

        # Update state
        state.routing = result
        state.complexity = TaskComplexity(result.get("complexity", "medium"))
        state.agents_to_run = result.get("agents", [])

        state.add_event("agent_complete", "router_agent", {
            "summary": result.get("summary"),
            "complexity": state.complexity.value,
            "agents": state.agents_to_run
        })

        await _emit_event(state.task_id, "agent_complete", "router_agent", {
            "complexity": state.complexity.value
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] RouterAgent failed: {e}")
        state.add_error(f"RouterAgent: {str(e)}")
        state.mark_blocked(f"Routing failed: {str(e)}")


async def interpret_ticket(state: PipelineState):
    """Parse and interpret ticket requirements."""
    logger.info(f"[{state.task_id}] Running TicketInterpreterAgent")

    state.add_event("agent_start", "ticket_interpreter", {})

    try:
        context = _build_context(state)
        agent = TicketInterpreterAgent()
        result = await agent.run(context)

        state.ticket_data = result
        state.context["ticket_interpreter"] = result

        state.add_event("agent_complete", "ticket_interpreter", {
            "summary": result.get("summary")
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] TicketInterpreterAgent failed: {e}")
        state.add_error(f"TicketInterpreterAgent: {str(e)}")


async def build_context(state: PipelineState):
    """Fetch repository context and conventions."""
    logger.info(f"[{state.task_id}] Running ContextBuilderAgent")

    state.add_event("agent_start", "context_builder", {})

    try:
        context = _build_context(state)
        agent = ContextBuilderAgent()
        result = await agent.run(context)

        state.repo_tree = result.get("repo_tree")
        state.relevant_files = result.get("relevant_files", [])
        state.conventions = result.get("conventions", {})
        state.skills = result.get("skills", {})
        state.context["context_builder"] = result

        state.add_event("agent_complete", "context_builder", {
            "summary": result.get("summary"),
            "file_count": len(state.relevant_files)
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] ContextBuilderAgent failed: {e}")
        state.add_error(f"ContextBuilderAgent: {str(e)}")


async def check_clarification(state: PipelineState):
    """Check if clarification is needed from user."""
    logger.info(f"[{state.task_id}] Running ClarificationAgent")

    state.add_event("agent_start", "clarification_agent", {})

    try:
        context = _build_context(state)
        agent = ClarificationAgent()
        result = await agent.run(context)

        state.clarification_needed = result.get("waiting", False)
        state.clarification_question = result.get("question")
        state.slack_thread_ts = result.get("slack_thread_ts")
        state.context["clarification_agent"] = result

        if result.get("waiting", False):
            state.mark_waiting()

        state.add_event("agent_complete", "clarification_agent", {
            "summary": result.get("summary"),
            "needs_clarification": state.clarification_needed
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] ClarificationAgent failed: {e}")
        state.add_error(f"ClarificationAgent: {str(e)}")


async def generate_plan(state: PipelineState):
    """Generate implementation plan."""
    logger.info(f"[{state.task_id}] Running PlannerAgent")

    state.add_event("agent_start", "planner_agent", {})

    try:
        context = _build_context(state)
        agent = PlannerAgent()
        result = await agent.run(context)

        state.plan = result.get("plan")
        state.plan_confidence = result.get("confidence")
        state.definition_of_done = result.get("definition_of_done", [])
        state.context["planner_agent"] = result

        state.add_event("agent_complete", "planner_agent", {
            "summary": result.get("summary"),
            "confidence": state.plan_confidence
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] PlannerAgent failed: {e}")
        state.add_error(f"PlannerAgent: {str(e)}")


async def approve_plan(state: PipelineState):
    """Post plan to Slack/Jira for visibility."""
    logger.info(f"[{state.task_id}] Running PlanApprovalAgent")

    state.add_event("agent_start", "plan_approval_agent", {})

    try:
        context = _build_context(state)
        agent = PlanApprovalAgent()
        result = await agent.run(context)

        state.context["plan_approval_agent"] = result

        state.add_event("agent_complete", "plan_approval_agent", {
            "summary": result.get("summary")
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] PlanApprovalAgent failed: {e}")
        state.add_error(f"PlanApprovalAgent: {str(e)}")


async def check_guardrails(state: PipelineState):
    """Validate plan against guardrails."""
    logger.info(f"[{state.task_id}] Running GuardrailsAgent")

    state.add_event("agent_start", "guardrails_agent", {})

    try:
        context = _build_context(state)
        agent = GuardrailsAgent()
        result = await agent.run(context)

        state.guardrails_passed = not result.get("blocked", False)
        state.guardrails_warnings = result.get("warnings", [])
        state.context["guardrails_agent"] = result

        if result.get("blocked", False):
            state.mark_blocked(result.get("reason", "Guardrails check failed"))

        state.add_event("agent_complete", "guardrails_agent", {
            "summary": result.get("summary"),
            "blocked": state.blocked
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] GuardrailsAgent failed: {e}")
        state.add_error(f"GuardrailsAgent: {str(e)}")


async def generate_code(state: PipelineState):
    """Generate code and create PR."""
    logger.info(f"[{state.task_id}] Running CoderAgent")

    state.add_event("agent_start", "coder_agent", {})

    try:
        context = _build_context(state)
        agent = CoderAgent()
        result = await agent.run(context)

        state.branch_name = result.get("branch_name")
        state.commits = result.get("commits", [])
        state.pr_number = result.get("pr_number")
        state.pr_url = result.get("pr_url")
        state.files_modified = result.get("files_modified", [])
        state.context["coder_agent"] = result

        state.add_event("agent_complete", "coder_agent", {
            "summary": result.get("summary"),
            "pr_url": state.pr_url
        })

        await _emit_event(state.task_id, "pr_created", "coder_agent", {
            "pr_url": state.pr_url
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] CoderAgent failed: {e}")
        state.add_error(f"CoderAgent: {str(e)}")
        state.mark_blocked(f"Code generation failed: {str(e)}")


async def generate_tests(state: PipelineState):
    """Generate unit and integration tests."""
    logger.info(f"[{state.task_id}] Running TesterAgent")

    state.add_event("agent_start", "tester_agent", {})

    try:
        context = _build_context(state)
        agent = TesterAgent()
        result = await agent.run(context)

        state.tests_generated = result.get("tests_generated", [])
        state.context["tester_agent"] = result

        state.add_event("agent_complete", "tester_agent", {
            "summary": result.get("summary"),
            "test_count": len(state.tests_generated)
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] TesterAgent failed: {e}")
        state.add_error(f"TesterAgent: {str(e)}")


async def verify_execution(state: PipelineState):
    """Run build, tests, and linting."""
    logger.info(f"[{state.task_id}] Running ExecutionVerifierAgent")

    state.add_event("agent_start", "execution_verifier", {})

    try:
        context = _build_context(state)
        agent = ExecutionVerifierAgent()
        result = await agent.run(context)

        state.build_passed = result.get("build_passed", False)
        state.tests_passed = result.get("tests_passed", False)
        state.lint_passed = result.get("lint_passed", False)
        state.verification_errors = result.get("errors", [])
        state.test_results = result.get("test_results")
        state.context["execution_verifier"] = result

        state.add_event("agent_complete", "execution_verifier", {
            "summary": result.get("summary"),
            "build_passed": state.build_passed,
            "tests_passed": state.tests_passed
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] ExecutionVerifierAgent failed: {e}")
        state.add_error(f"ExecutionVerifierAgent: {str(e)}")


async def review_implementation(state: PipelineState):
    """Review implementation against Definition of Done."""
    logger.info(f"[{state.task_id}] Running ReviewerAgent")

    state.add_event("agent_start", "reviewer_agent", {})

    try:
        context = _build_context(state)
        agent = ReviewerAgent()
        result = await agent.run(context)

        state.review_passed = result.get("approved", False)
        state.review_feedback = result.get("feedback", [])
        state.needs_revision = result.get("needs_revision", False)
        state.context["reviewer_agent"] = result

        if state.needs_revision:
            state.revision_count += 1

        state.add_event("agent_complete", "reviewer_agent", {
            "summary": result.get("summary"),
            "approved": state.review_passed,
            "needs_revision": state.needs_revision
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] ReviewerAgent failed: {e}")
        state.add_error(f"ReviewerAgent: {str(e)}")


async def store_memory(state: PipelineState):
    """Store learned patterns and pitfalls."""
    logger.info(f"[{state.task_id}] Running MemoryAgent")

    state.add_event("agent_start", "memory_agent", {})

    try:
        context = _build_context(state)
        agent = MemoryAgent()
        result = await agent.run(context)

        state.patterns_learned = result.get("patterns", [])
        state.pitfalls_encountered = result.get("pitfalls", [])
        state.context["memory_agent"] = result

        state.add_event("agent_complete", "memory_agent", {
            "summary": result.get("summary")
        })

    except Exception as e:
        logger.error(f"[{state.task_id}] MemoryAgent failed: {e}")
        state.add_error(f"MemoryAgent: {str(e)}")


async def finalize_pipeline(state: PipelineState):
    """Finalize pipeline and set final status."""
    logger.info(f"[{state.task_id}] Finalizing pipeline")

    # Determine final status
    if state.blocked:
        state.status = PipelineStatus.FAILED
    elif state.waiting:
        state.status = PipelineStatus.WAITING_CLARIFICATION
    elif state.pr_url:
        state.status = PipelineStatus.IN_REVIEW
    else:
        state.status = PipelineStatus.DONE

    state.add_event("pipeline_complete", "orchestrator", {
        "final_status": state.status.value,
        "pr_url": state.pr_url,
        "errors": state.errors
    })

    await _emit_event(state.task_id, "pipeline_complete", "orchestrator", {
        "status": state.status.value
    })
