"""Output Guardrails: Leakage Protection, Voice Formatting, and Output Safety."""
from dataclasses import dataclass
import re
from typing import List, Optional
from .input_guardrails import GuardrailResult, GuardrailStatus


class OutputGuardrail:
    """Multi-layer output guardrail validating agent responses before presentation and TTS."""

    # Patterns indicating unintentional leakage of internal secrets or configs
    _LEAKAGE_PATTERNS = [
        # Database connection strings with passwords
        r"(?i)postgresql\+asyncpg:\/\/[^\s]+",
        r"(?i)sqlite\+aiosqlite:\/\/[^\s]+",
        # JWT signatures / internal tokens
        r"\beyJ[a-zA-Z0-9_\-]{20,}\.eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}\b",
        # Raw system prompt indicators leaked to user
        r"(?i)SYSTEM_PROMPT\s*=\s*",
        r"(?i)You are OmniVox, a voice-controlled executive assistant",
        # Tracebacks / Internal exceptions
        r"Traceback \(most recent call last\):",
    ]

    def __init__(self):
        self.leakage_regexes = [re.compile(p) for p in self._LEAKAGE_PATTERNS]

    def _sanitize_for_voice(self, text: str) -> str:
        """Ensure response is clean of markdown asterisks, raw URLs, and angle brackets."""
        # Strip markdown bold / italics asterisks
        text = text.replace("**", "").replace("*", "")
        # Strip markdown links [label](url) -> label
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Strip raw URLs (http:// or https://)
        text = re.sub(r'https?://\S+', '', text)
        # Strip raw angle brackets <...>
        text = re.sub(r'<[^>]+>', '', text)
        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def validate(self, text: str) -> GuardrailResult:
        """Validate and sanitize output before sending to TTS and frontend."""
        if not text:
            return GuardrailResult(
                status=GuardrailStatus.ALLOWED,
                sanitized_text="",
                is_safe=True,
            )

        applied_rules: List[str] = []

        # 1. Leakage & Traceback Check
        for regex in self.leakage_regexes:
            if regex.search(text):
                return GuardrailResult(
                    status=GuardrailStatus.BLOCKED,
                    sanitized_text="I encountered a secure internal policy constraint and cannot output the raw requested content. How else may I assist you?",
                    is_safe=False,
                    reason="Output contained potential secret leakage or internal traceback.",
                    applied_rules=["secret_leakage_prevented"],
                )

        # 2. Voice Sanitization (Removing asterisks, raw URLs, angle brackets)
        sanitized = self._sanitize_for_voice(text)
        if sanitized != text:
            applied_rules.append("voice_format_sanitized")

        return GuardrailResult(
            status=GuardrailStatus.ALLOWED,
            sanitized_text=sanitized,
            is_safe=True,
            applied_rules=applied_rules,
        )
