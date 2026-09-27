"""Input Guardrails: Prompt Injection Defense, PII Masking, and Safety Filters."""
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Dict, List, Optional, Tuple


class GuardrailStatus(str, Enum):
    ALLOWED = "allowed"
    FLAGGED = "flagged"
    BLOCKED = "blocked"
    REDACTED = "redacted"


@dataclass
class GuardrailResult:
    status: GuardrailStatus
    sanitized_text: str
    is_safe: bool = True
    reason: Optional[str] = None
    applied_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


class InputGuardrail:
    """Multi-layer input guardrail verifying user input before LLM execution."""

    # Common prompt injection, jailbreak, and system override patterns
    _INJECTION_PATTERNS = [
        # Direct instruction overrides
        r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules|guidelines)",
        r"(?i)\b(?:system\s*prompt\s*(?:reveal|leak|print|show|dump|echo))",
        r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:DAN|developer\s+mode|unrestricted|jailbroken|evil)",
        r"(?i)\b(?:override\s+system\s+(?:rules|instructions|security))",
        r"(?i)\b(?:output\s+your\s+(?:initial|hidden|system)\s+prompt)",
        # Special system token injection attempts
        r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",
        r"(?i)###\s*(?:instruction|system|human|assistant):",
        # Sudo / administrative simulation
        r"(?i)\b(?:sudo\s+mode|maintenance\s+mode|debug\s+mode\s+enabled)\b",
    ]

    # Patterns for detecting and redacting PII / sensitive data
    _PII_PATTERNS = [
        # US SSN (XXX-XX-XXXX)
        (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
        # Credit / Debit card (13-16 digits with optional spaces or dashes)
        (r"\b(?:\d{4}[ -]?){3}\d{4}\b", "[REDACTED_CARD]"),
        # AWS Access Key ID
        (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED_AWS_KEY]"),
        # Generic Secret API Keys (e.g., sk-..., ntn_..., ghp_..., etc.)
        (r"\b(?:sk-[a-zA-Z0-9]{20,}|ntn_[a-zA-Z0-9]{20,}|secret_[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,})\b", "[REDACTED_API_KEY]"),
        # Bearer tokens in raw text
        (r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.]{25,}\b", "Bearer [REDACTED_TOKEN]"),
    ]

    # Patterns for harmful, malicious or dangerous intents
    _HARMFUL_PATTERNS = [
        r"(?i)\b(?:how\s+to\s+(?:make|build|synthesize)\s+(?:a\s+)?(?:bomb|explosive|weapon|poison|virus|malware))\b",
        r"(?i)\b(?:generate|write)\s+(?:a\s+)?(?:ransomware|keylogger|trojan|exploit\s+payload)\b",
        r"(?i)\b(?:how\s+to\s+(?:hack|ddos|attack|crack)\s+(?:into\s+)?[a-zA-Z0-9\.\-_]+)\b",
    ]

    _MAX_INPUT_LENGTH = 4000

    def __init__(self):
        self.injection_regexes = [re.compile(p) for p in self._INJECTION_PATTERNS]
        self.harmful_regexes = [re.compile(p) for p in self._HARMFUL_PATTERNS]
        self.pii_rules = [(re.compile(pattern), repl) for pattern, repl in self._PII_PATTERNS]

    def validate(self, text: str) -> GuardrailResult:
        """Run all input guardrails sequentially on user input."""
        applied_rules: List[str] = []

        if not text or not text.strip():
            return GuardrailResult(
                status=GuardrailStatus.ALLOWED,
                sanitized_text="",
                is_safe=True,
                reason="Empty input",
            )

        sanitized = text.strip()

        # 1. Payload Length Guardrail
        if len(sanitized) > self._MAX_INPUT_LENGTH:
            sanitized = sanitized[:self._MAX_INPUT_LENGTH]
            applied_rules.append("truncated_length")

        # 2. Harmful / Malicious Content Guardrail
        for regex in self.harmful_regexes:
            if regex.search(sanitized):
                return GuardrailResult(
                    status=GuardrailStatus.BLOCKED,
                    sanitized_text="",
                    is_safe=False,
                    reason="Input contains restricted security or harmful request patterns.",
                    applied_rules=["harmful_content_blocked"],
                )

        # 3. Prompt Injection & Jailbreak Guardrail
        for regex in self.injection_regexes:
            if regex.search(sanitized):
                return GuardrailResult(
                    status=GuardrailStatus.BLOCKED,
                    sanitized_text="",
                    is_safe=False,
                    reason="Potential prompt injection or security policy override detected.",
                    applied_rules=["prompt_injection_blocked"],
                )

        # 4. PII Redaction Guardrail
        redacted = sanitized
        has_pii = False
        for regex, replacement in self.pii_rules:
            if regex.search(redacted):
                redacted = regex.sub(replacement, redacted)
                has_pii = True

        if has_pii:
            applied_rules.append("pii_redacted")
            return GuardrailResult(
                status=GuardrailStatus.REDACTED,
                sanitized_text=redacted,
                is_safe=True,
                reason="PII or credential tokens detected and masked.",
                applied_rules=applied_rules,
            )

        return GuardrailResult(
            status=GuardrailStatus.ALLOWED,
            sanitized_text=sanitized,
            is_safe=True,
            applied_rules=applied_rules,
        )
