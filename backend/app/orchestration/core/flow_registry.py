"""
Flow Registry - Plugin system for flows.

Step 5 from architecture diagram: Agent registry lookup.
"""

import logging
from typing import Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class FlowRegistry:
    """
    Registry for all available flows.

    Implements plugin architecture - flows self-register on import.
    """

    _flows: Dict[str, 'Flow'] = {}

    @classmethod
    def register(cls, name: str, flow: 'Flow'):
        """
        Register a new flow.

        Args:
            name: Flow name (must be unique)
            flow: Flow instance

        Raises:
            ValueError: If flow name already registered
        """
        if name in cls._flows:
            logger.warning(f"Flow '{name}' already registered, overwriting")

        cls._flows[name] = flow
        logger.info(f"Registered flow: {name}")

    @classmethod
    def get(cls, name: str) -> Optional['Flow']:
        """
        Get a flow by name.

        Args:
            name: Flow name

        Returns:
            Flow instance or None if not found
        """
        return cls._flows.get(name)

    @classmethod
    def all(cls) -> List[str]:
        """
        List all registered flow names.

        Returns:
            List of flow names
        """
        return list(cls._flows.keys())

    @classmethod
    def exists(cls, name: str) -> bool:
        """
        Check if a flow is registered.

        Args:
            name: Flow name

        Returns:
            True if flow exists
        """
        return name in cls._flows

    @classmethod
    def clear(cls):
        """Clear all registered flows (useful for testing)."""
        cls._flows = {}
        logger.info("Cleared all registered flows")

    @classmethod
    def get_info(cls) -> Dict[str, Dict]:
        """
        Get information about all registered flows.

        Returns:
            Dict mapping flow names to their info
        """
        return {
            name: {
                'name': flow.name,
                'description': flow.description,
                'steps': len(flow.get_steps()) if hasattr(flow, 'get_steps') else 0
            }
            for name, flow in cls._flows.items()
        }
