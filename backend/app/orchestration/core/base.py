"""
Base classes for flows and steps.

Integrates with LangGraph StateGraph for execution.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional, Union
from dataclasses import dataclass

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


@dataclass
class FlowStep:
    """
    Represents a single step in a flow.

    Can be:
    - Simple step: name + node function + next step name
    - Conditional step: name + node function + routing function
    """

    name: str
    node: Callable
    next: Union[str, Callable, None] = None
    description: Optional[str] = None


class Flow(ABC):
    """
    Base class for all flows.

    Subclasses define flows by implementing:
    - get_steps(): Return list of FlowStep objects
    - can_handle(): Check if flow can handle input

    The flow is automatically converted to a LangGraph StateGraph for execution.
    """

    name: str = "base_flow"
    description: str = "Base flow"

    def __init__(self):
        """Initialize flow."""
        self._graph = None
        self._compiled_graph = None

    @abstractmethod
    def get_steps(self) -> List[FlowStep]:
        """
        Define the steps for this flow.

        Returns:
            List of FlowStep objects defining the flow
        """
        pass

    @abstractmethod
    async def can_handle(self, context: Dict[str, Any]) -> bool:
        """
        Check if this flow can handle the given input.

        Args:
            context: Input context

        Returns:
            True if this flow should handle this input
        """
        pass

    def build_graph(self, state_schema: type) -> StateGraph:
        """
        Build a LangGraph StateGraph from flow steps.

        Args:
            state_schema: State schema class (TypedDict or Pydantic model)

        Returns:
            StateGraph instance
        """
        if self._graph is not None:
            return self._graph

        logger.info(f"Building graph for flow: {self.name}")

        # Create StateGraph
        graph = StateGraph(state_schema)

        # Add all nodes
        steps = self.get_steps()
        for step in steps:
            logger.debug(f"Adding node: {step.name}")
            graph.add_node(step.name, step.node)

        # Set entry point (first step)
        if steps:
            graph.set_entry_point(steps[0].name)

        # Add edges
        for i, step in enumerate(steps):
            if step.next is None:
                # Terminal node
                graph.add_edge(step.name, END)

            elif callable(step.next):
                # Conditional edge
                logger.debug(f"Adding conditional edge from: {step.name}")
                # The callable should return the next step name or None for END
                graph.add_conditional_edges(
                    step.name,
                    step.next
                )

            elif isinstance(step.next, str):
                # Direct edge
                graph.add_edge(step.name, step.next)

        self._graph = graph
        return graph

    def compile(self, state_schema: type) -> Any:
        """
        Build and compile the graph for execution.

        Args:
            state_schema: State schema class

        Returns:
            Compiled graph ready for invocation
        """
        if self._compiled_graph is not None:
            return self._compiled_graph

        graph = self.build_graph(state_schema)
        self._compiled_graph = graph.compile()

        logger.info(f"Compiled graph for flow: {self.name}")
        return self._compiled_graph

    async def execute(self, state: Any, state_schema: type) -> Any:
        """
        Execute the flow with given state.

        Args:
            state: Initial state (instance of state_schema)
            state_schema: State schema class

        Returns:
            Final state after execution
        """
        logger.info(f"Executing flow: {self.name}")

        # Compile graph if not already compiled
        compiled_graph = self.compile(state_schema)

        # Execute graph
        try:
            # Convert state to dict if it's a dataclass
            if hasattr(state, 'to_dict'):
                state_dict = state.to_dict()
            elif hasattr(state, '__dict__'):
                state_dict = state.__dict__
            else:
                state_dict = dict(state)

            # Invoke graph
            result = await compiled_graph.ainvoke(state_dict)

            # Convert result back to state schema if needed
            if hasattr(state_schema, 'from_dict'):
                return state_schema.from_dict(result)
            else:
                return result

        except Exception as e:
            logger.error(f"Flow execution failed: {e}", exc_info=True)
            raise

    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this flow.

        Returns:
            Dict with flow metadata
        """
        steps = self.get_steps()

        return {
            'name': self.name,
            'description': self.description,
            'step_count': len(steps),
            'steps': [
                {
                    'name': step.name,
                    'description': step.description,
                    'has_conditional': callable(step.next)
                }
                for step in steps
            ]
        }

    def visualize(self) -> str:
        """
        Generate ASCII visualization of flow.

        Returns:
            ASCII diagram of flow
        """
        lines = [f"Flow: {self.name}", ""]

        steps = self.get_steps()
        for i, step in enumerate(steps):
            # Format step
            lines.append(f"{i+1}. {step.name}")

            if step.description:
                lines.append(f"   {step.description}")

            # Format next step
            if step.next is None:
                lines.append("   └─▶ [END]")
            elif callable(step.next):
                lines.append("   └─▶ [CONDITIONAL]")
            else:
                lines.append(f"   └─▶ {step.next}")

            lines.append("")

        return "\n".join(lines)


class ConditionalRouter:
    """
    Helper class for building conditional routing functions.

    Usage:
        router = ConditionalRouter()
        router.add_condition(lambda state: state.waiting, "wait_node")
        router.add_condition(lambda state: state.blocked, "blocked_node")
        router.set_default("continue_node")

        # Use in FlowStep
        FlowStep(name="check", node=check_node, next=router.route)
    """

    def __init__(self):
        """Initialize router."""
        self.conditions: List[tuple] = []
        self.default_route: Optional[str] = None

    def add_condition(self, condition: Callable, route: str):
        """
        Add a conditional route.

        Args:
            condition: Function that takes state and returns bool
            route: Node name to route to if condition is True
        """
        self.conditions.append((condition, route))

    def set_default(self, route: str):
        """
        Set default route if no conditions match.

        Args:
            route: Node name for default route
        """
        self.default_route = route

    def route(self, state: Any) -> str:
        """
        Evaluate conditions and return route.

        Args:
            state: Current state

        Returns:
            Node name to route to
        """
        # Check conditions in order
        for condition, route in self.conditions:
            if condition(state):
                return route

        # Return default if no conditions matched
        if self.default_route:
            return self.default_route

        # If no default, end flow
        return END
