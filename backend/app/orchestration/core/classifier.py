"""
Flow classification layer.

Implements steps 2-4 from the architecture diagram:
- Step 2: Validate ticket
- Step 3: LLM classifier (cheap model)
- Step 4: Confidence check + escalation
"""

import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of flow classification."""

    flow_name: Optional[str]
    confidence: float
    rejected: bool = False
    escalate: bool = False
    reason: Optional[str] = None
    reasoning: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FlowClassifier:
    """
    Classifies incoming requests and routes to appropriate flow.

    Implements the classification layer from architecture diagram:
    1. Validation (reject malformed inputs)
    2. LLM classification (determine flow)
    3. Confidence check (escalate if uncertain)
    """

    # Confidence threshold for automatic processing
    CONFIDENCE_THRESHOLD = 0.7

    # Available flows (will be populated from registry)
    AVAILABLE_FLOWS = {
        "onboarding": "Initial context building for new team/org",
        "continuous_ingestion": "Background updates of team context",
        "ticket_implementation": "Implement a ticket and create PR",
    }

    def __init__(self):
        """Initialize classifier."""
        self.confidence_threshold = self.CONFIDENCE_THRESHOLD

    async def classify(self, input_data: Dict[str, Any]) -> ClassificationResult:
        """
        Main classification pipeline.

        Steps:
        1. Validate input
        2. LLM classification
        3. Confidence check
        4. Return classification result

        Args:
            input_data: Input request data

        Returns:
            ClassificationResult with flow name and confidence
        """
        logger.info(f"Classifying input: {input_data.get('action', 'unknown')}")

        # Step 1: Validate
        validation = self._validate(input_data)
        if not validation['valid']:
            logger.warning(f"Validation failed: {validation['reason']}")
            return ClassificationResult(
                flow_name=None,
                confidence=0.0,
                rejected=True,
                reason=validation['reason']
            )

        # Step 2: LLM Classification
        try:
            classification = await self._llm_classify(input_data)
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return ClassificationResult(
                flow_name=None,
                confidence=0.0,
                rejected=True,
                reason=f"Classification error: {str(e)}"
            )

        # Step 3: Confidence Check
        if classification['confidence'] < self.confidence_threshold:
            logger.warning(
                f"Low confidence ({classification['confidence']}) for flow "
                f"'{classification['flow']}', escalating to human"
            )
            return ClassificationResult(
                flow_name=classification['flow'],
                confidence=classification['confidence'],
                escalate=True,
                reason=f"Confidence {classification['confidence']} below threshold {self.confidence_threshold}",
                reasoning=classification.get('reasoning'),
                metadata=classification.get('metadata')
            )

        # Step 4: Return result
        logger.info(
            f"Classified as '{classification['flow']}' "
            f"with confidence {classification['confidence']}"
        )
        return ClassificationResult(
            flow_name=classification['flow'],
            confidence=classification['confidence'],
            reasoning=classification.get('reasoning'),
            metadata=classification.get('metadata')
        )

    def _validate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2 from diagram: Validate ticket.

        Checks:
        - Required fields present
        - Org exists
        - Input not empty/malformed

        Args:
            input_data: Input to validate

        Returns:
            Dict with 'valid' and 'reason' keys
        """
        # Check required fields
        if not input_data:
            return {'valid': False, 'reason': 'Empty input'}

        if not input_data.get('org_id'):
            return {'valid': False, 'reason': 'Missing org_id'}

        # Check for explicit action or inferrable context
        has_action = 'action' in input_data
        has_ticket = 'ticket_id' in input_data or 'description' in input_data
        has_context = has_action or has_ticket

        if not has_context:
            return {
                'valid': False,
                'reason': 'Missing action or ticket context'
            }

        # Specific validations based on action
        action = input_data.get('action', '').lower()

        if action == 'onboard':
            if not input_data.get('github_repo'):
                return {'valid': False, 'reason': 'Onboarding requires github_repo'}

        elif action == 'implement':
            if not (input_data.get('ticket_id') or input_data.get('description')):
                return {
                    'valid': False,
                    'reason': 'Ticket implementation requires ticket_id or description'
                }

        # All checks passed
        return {'valid': True, 'reason': None}

    async def _llm_classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 3 from diagram: LLM classifier (cheap model).

        Uses cheap LLM to classify input into one of the available flows.

        Args:
            input_data: Input to classify

        Returns:
            Dict with 'flow', 'confidence', 'reasoning' keys
        """
        # Import LLM function
        try:
            from app.core.llm import cheap
        except ImportError:
            # Fallback for testing
            logger.warning("LLM not available, using rule-based classification")
            return self._rule_based_classify(input_data)

        # Build prompt for LLM
        flows_description = "\n".join([
            f"- {name}: {desc}"
            for name, desc in self.AVAILABLE_FLOWS.items()
        ])

        prompt = f"""You are a flow classifier for an AI development assistant.

Available flows:
{flows_description}

Input to classify:
{json.dumps(input_data, indent=2)}

Classify this input into ONE of the available flows based on:
- Explicit 'action' field if present
- Implicit intent from ticket_id, description, or other fields
- Context clues

Return ONLY valid JSON in this exact format:
{{
  "flow": "flow_name",
  "confidence": 0.0-1.0,
  "reasoning": "why you chose this flow"
}}

Valid flow names: {list(self.AVAILABLE_FLOWS.keys())}
"""

        # Call LLM
        try:
            response = await cheap(prompt)

            # Parse JSON from response
            # LLM might wrap in markdown code blocks, so clean it
            response = response.strip()
            if response.startswith('```'):
                # Extract JSON from code block
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1])  # Remove first and last line

            result = json.loads(response)

            # Validate result
            if 'flow' not in result or 'confidence' not in result:
                raise ValueError("LLM response missing required fields")

            if result['flow'] not in self.AVAILABLE_FLOWS:
                raise ValueError(f"Invalid flow name: {result['flow']}")

            # Ensure confidence is a float between 0 and 1
            result['confidence'] = float(result['confidence'])
            if not 0 <= result['confidence'] <= 1:
                result['confidence'] = 0.5  # Default if out of range

            return result

        except Exception as e:
            logger.error(f"LLM classification failed, falling back to rules: {e}")
            return self._rule_based_classify(input_data)

    def _rule_based_classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback rule-based classification if LLM fails.

        Args:
            input_data: Input to classify

        Returns:
            Dict with 'flow', 'confidence', 'reasoning' keys
        """
        action = input_data.get('action', '').lower()

        # Explicit action mapping
        if action == 'onboard':
            return {
                'flow': 'onboarding',
                'confidence': 0.95,
                'reasoning': 'Explicit onboarding action specified'
            }

        if action == 'ingest':
            return {
                'flow': 'continuous_ingestion',
                'confidence': 0.95,
                'reasoning': 'Explicit ingestion action specified'
            }

        if action == 'implement':
            return {
                'flow': 'ticket_implementation',
                'confidence': 0.95,
                'reasoning': 'Explicit implement action specified'
            }

        # Implicit classification based on fields
        if input_data.get('ticket_id') or input_data.get('description'):
            return {
                'flow': 'ticket_implementation',
                'confidence': 0.85,
                'reasoning': 'Has ticket_id or description, likely ticket implementation'
            }

        if input_data.get('github_repo') and not input_data.get('ticket_id'):
            return {
                'flow': 'onboarding',
                'confidence': 0.75,
                'reasoning': 'Has github_repo without ticket, likely onboarding'
            }

        # Default to ticket implementation with low confidence
        return {
            'flow': 'ticket_implementation',
            'confidence': 0.50,
            'reasoning': 'Default classification, insufficient context'
        }

    async def escalate_to_human(
        self,
        input_data: Dict[str, Any],
        classification: ClassificationResult
    ) -> Dict[str, Any]:
        """
        Escalate low-confidence classification to human.

        Args:
            input_data: Original input
            classification: Classification result that triggered escalation

        Returns:
            Dict with escalation details
        """
        logger.info(
            f"Escalating classification to human: "
            f"{classification.flow_name} @ {classification.confidence}"
        )

        escalation_data = {
            'escalation_id': f"esc_{datetime.utcnow().timestamp()}",
            'input': input_data,
            'classification': {
                'flow': classification.flow_name,
                'confidence': classification.confidence,
                'reasoning': classification.reasoning
            },
            'reason': classification.reason,
            'escalated_at': datetime.utcnow().isoformat(),
            'status': 'pending_human_review'
        }

        # TODO: Implement actual escalation (e.g., post to Slack, create Jira ticket)
        # For now, just log and return

        return escalation_data
