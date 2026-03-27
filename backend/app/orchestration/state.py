"""
State schema for the orchestration pipeline.

Compatible with LangGraph StateGraph execution.
Uses TypedDict for LangGraph compatibility with helper methods from dataclass.
"""

from typing import Any, Dict, List, Optional, TypedDict
from typing_extensions import Annotated
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_CLARIFICATION = "waiting_clarification"
    PAUSED = "paused"
    IN_REVIEW = "in_review"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class PipelineState:
    """
    Complete state for the entire pipeline execution.

    This is a mutable state object that flows through all pipeline steps.
    """

    # ========================================================================
    # TASK METADATA
    # ========================================================================

    task_id: str
    org_id: str
    task_description: str
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None

    # Flow identification (which flow is executing)
    flow_name: Optional[str] = None
    classification_confidence: Optional[float] = None

    # ========================================================================
    # ROUTING & AGENT SELECTION
    # ========================================================================

    routing: Optional[Dict[str, Any]] = None
    complexity: Optional[TaskComplexity] = None
    agents_to_run: List[str] = field(default_factory=list)
    current_agent_index: int = 0

    # ========================================================================
    # TICKET INTERPRETATION
    # ========================================================================

    ticket_data: Optional[Dict[str, Any]] = None

    # ========================================================================
    # CONTEXT BUILDING
    # ========================================================================

    repo_tree: Optional[List[str]] = None
    relevant_files: List[str] = field(default_factory=list)
    conventions: Optional[Dict[str, Any]] = None
    skills: Optional[Dict[str, Any]] = None

    # ========================================================================
    # CLARIFICATION
    # ========================================================================

    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    clarification_answer: Optional[str] = None
    slack_thread_ts: Optional[str] = None

    # ========================================================================
    # PLANNING
    # ========================================================================

    plan: Optional[Dict[str, Any]] = None
    plan_confidence: Optional[float] = None
    definition_of_done: List[str] = field(default_factory=list)

    # ========================================================================
    # GUARDRAILS
    # ========================================================================

    guardrails_passed: bool = True
    guardrails_warnings: List[str] = field(default_factory=list)

    # ========================================================================
    # CODING
    # ========================================================================

    branch_name: Optional[str] = None
    commits: List[Dict[str, str]] = field(default_factory=list)
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)

    # ========================================================================
    # TESTING
    # ========================================================================

    tests_generated: List[str] = field(default_factory=list)
    test_results: Optional[Dict[str, Any]] = None

    # ========================================================================
    # VERIFICATION
    # ========================================================================

    build_passed: bool = False
    tests_passed: bool = False
    lint_passed: bool = False
    verification_errors: List[str] = field(default_factory=list)

    # ========================================================================
    # REVIEW
    # ========================================================================

    review_passed: bool = False
    review_feedback: List[str] = field(default_factory=list)
    needs_revision: bool = False
    revision_count: int = 0

    # ========================================================================
    # MEMORY & LEARNING
    # ========================================================================

    patterns_learned: List[str] = field(default_factory=list)
    pitfalls_encountered: List[str] = field(default_factory=list)

    # ========================================================================
    # CONTROL FLOW
    # ========================================================================

    status: PipelineStatus = PipelineStatus.QUEUED
    blocked: bool = False
    blocking_reason: Optional[str] = None
    waiting: bool = False

    # ========================================================================
    # EVENT LOGGING
    # ========================================================================

    events: List[Dict[str, Any]] = field(default_factory=list)

    # ========================================================================
    # ERROR HANDLING
    # ========================================================================

    errors: List[str] = field(default_factory=list)
    retry_count: int = 0

    # ========================================================================
    # ADDITIONAL CONTEXT
    # ========================================================================

    context: Dict[str, Any] = field(default_factory=dict)

    # ========================================================================
    # METHODS
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        data = asdict(self)

        # Convert enums to strings
        if isinstance(data.get('status'), PipelineStatus):
            data['status'] = data['status'].value
        elif isinstance(data.get('status'), str):
            pass  # Already converted by asdict

        if isinstance(data.get('complexity'), TaskComplexity):
            data['complexity'] = data['complexity'].value
        elif isinstance(data.get('complexity'), str):
            pass  # Already converted by asdict

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineState':
        """Create state from dictionary."""
        # Convert status string to enum
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = PipelineStatus(data['status'])

        # Convert complexity string to enum
        if 'complexity' in data and isinstance(data['complexity'], str):
            data['complexity'] = TaskComplexity(data['complexity'])

        # Convert created_at string to datetime
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        return cls(**data)

    def add_event(self, event_type: str, agent_name: str, data: Optional[Dict[str, Any]] = None):
        """Add an event to the event log."""
        self.events.append({
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'agent_name': agent_name,
            'data': data or {}
        })

    def add_error(self, error: str):
        """Add an error to the error list."""
        self.errors.append(error)

    def mark_blocked(self, reason: str):
        """Mark pipeline as blocked."""
        self.blocked = True
        self.blocking_reason = reason
        self.status = PipelineStatus.FAILED

    def mark_waiting(self):
        """Mark pipeline as waiting for input."""
        self.waiting = True
        self.status = PipelineStatus.WAITING_CLARIFICATION

    def is_terminal(self) -> bool:
        """Check if pipeline is in a terminal state."""
        return self.status in [
            PipelineStatus.DONE,
            PipelineStatus.FAILED,
            PipelineStatus.CANCELLED
        ]

    def get_progress(self) -> float:
        """Calculate pipeline progress (0.0 to 1.0)."""
        stages = {
            'routing': 0.05,
            'ticket_data': 0.10,
            'relevant_files': 0.15,
            'plan': 0.25,
            'pr_url': 0.60,
            'test_results': 0.75,
            'review_passed': 0.90,
        }

        progress = 0.0
        for field, weight in stages.items():
            if getattr(self, field, None):
                progress = weight

        if self.status == PipelineStatus.DONE:
            progress = 1.0

        return progress
