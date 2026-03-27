"""
Flows module - Auto-imports all flows for registration.

When this module is imported, all flows are automatically registered
with the FlowRegistry through their auto-registration pattern.
"""

# Import all flows - they self-register on import
from .ticket_flow import TicketImplementationFlow
from .onboarding_flow import OnboardingFlow
from .ingestion_flow import ContinuousIngestionFlow

__all__ = [
    'TicketImplementationFlow',
    'OnboardingFlow',
    'ContinuousIngestionFlow',
]
