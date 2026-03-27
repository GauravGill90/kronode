"""
Agent Registry - Plugin system for agents.

Step 5 from architecture diagram: Agent registry lookup.
"""

import logging
from typing import Dict, List, Optional, Type, Any

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for all available agents.

    Implements plugin architecture - agents self-register on import.
    """

    _agents: Dict[str, Type['AgentBase']] = {}

    @classmethod
    def register(cls, name: str, agent_class: Type['AgentBase']):
        """
        Register a new agent.

        Args:
            name: Agent name (must be unique)
            agent_class: Agent class (not instance)

        Raises:
            ValueError: If agent name already registered
        """
        if name in cls._agents:
            logger.warning(f"Agent '{name}' already registered, overwriting")

        cls._agents[name] = agent_class
        logger.info(f"Registered agent: {name}")

    @classmethod
    def get(cls, name: str) -> Optional['AgentBase']:
        """
        Get an agent instance by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        agent_class = cls._agents.get(name)
        if agent_class is None:
            logger.error(f"Agent '{name}' not found in registry")
            return None

        # Return new instance
        return agent_class()

    @classmethod
    def get_class(cls, name: str) -> Optional[Type['AgentBase']]:
        """
        Get an agent class by name.

        Args:
            name: Agent name

        Returns:
            Agent class or None if not found
        """
        return cls._agents.get(name)

    @classmethod
    def all(cls) -> List[str]:
        """
        List all registered agent names.

        Returns:
            List of agent names
        """
        return list(cls._agents.keys())

    @classmethod
    def exists(cls, name: str) -> bool:
        """
        Check if an agent is registered.

        Args:
            name: Agent name

        Returns:
            True if agent exists
        """
        return name in cls._agents

    @classmethod
    def clear(cls):
        """Clear all registered agents (useful for testing)."""
        cls._agents = {}
        logger.info("Cleared all registered agents")

    @classmethod
    def dispatch(cls, agent_names: List[str], context: Dict[str, Any]) -> List[Dict]:
        """
        Dispatch multiple agents and collect results.

        Step 6 from architecture diagram: Dispatch agents.

        Args:
            agent_names: List of agent names to dispatch
            context: Context to pass to agents

        Returns:
            List of agent results
        """
        results = []

        for name in agent_names:
            agent = cls.get(name)

            if agent is None:
                logger.error(f"Cannot dispatch unknown agent: {name}")
                results.append({
                    'agent': name,
                    'success': False,
                    'error': f'Agent not found: {name}'
                })
                continue

            try:
                # Run agent (assuming async)
                import asyncio
                result = asyncio.run(agent.run(context))
                results.append({
                    'agent': name,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                logger.error(f"Agent '{name}' failed: {e}")
                results.append({
                    'agent': name,
                    'success': False,
                    'error': str(e)
                })

        return results

    @classmethod
    def get_info(cls) -> Dict[str, Dict]:
        """
        Get information about all registered agents.

        Returns:
            Dict mapping agent names to their info
        """
        return {
            name: {
                'name': name,
                'class': agent_class.__name__,
                'module': agent_class.__module__
            }
            for name, agent_class in cls._agents.items()
        }
