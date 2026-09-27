"""Guardrails Manager orchestrating input and output safety checks for OmniVox."""
import logging
from typing import Optional
from .input_guardrails import GuardrailResult, GuardrailStatus, InputGuardrail
from .output_guardrails import OutputGuardrail

logger = logging.getLogger("omnivox.guardrails")


class GuardrailsManager:
    """Enterprise safety manager running active validation on user input and agent output."""

    def __init__(self):
        self.input_guard = InputGuardrail()
        self.output_guard = OutputGuardrail()

    def validate_input(self, user_text: str) -> GuardrailResult:
        """Evaluate input before passing to LangChain / sub-agents."""
        res = self.input_guard.validate(user_text)
        if not res.is_safe:
            logger.warning(f"[Guardrails] Input blocked. Reason: {res.reason}")
        elif res.status == GuardrailStatus.REDACTED:
            logger.info(f"[Guardrails] Input sanitized/redacted: {res.applied_rules}")
        return res

    def validate_output(self, response_text: str) -> GuardrailResult:
        """Evaluate output before passing to TTS and user interface."""
        res = self.output_guard.validate(response_text)
        if not res.is_safe:
            logger.warning(f"[Guardrails] Output blocked. Reason: {res.reason}")
        return res


guardrails_manager = GuardrailsManager()
