import re
from loguru import logger
from pydantic import BaseModel

class GuardrailValidationResult(BaseModel):
    is_safe: bool
    reason: str | None = None
    cleaned_input: str

class InputGuardrail:
    PROMPT_INJECTION_PATTERNS = [
        r"ignore (all )?previous instructions",
        r"you are now a",
        r"system prompt",
        r"bypass safety",
        r"jailbreak",
    ]
    
    SQL_INJECTION_PATTERNS = [
        r";\s*drop\s+table",
        r";\s*delete\s+from",
        r"union\s+select",
        r"exec\(",
    ]
    
    XSS_PATTERNS = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"onload\s*=",
    ]

    @classmethod
    def validate(cls, input_text: str) -> GuardrailValidationResult:
        # Check Prompt Injection
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                logger.warning(f"Prompt injection detected: {pattern}")
                return GuardrailValidationResult(is_safe=False, reason="Prompt injection attempt detected", cleaned_input=input_text)
                
        # Check SQL Injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                logger.warning(f"SQL injection detected: {pattern}")
                return GuardrailValidationResult(is_safe=False, reason="SQL injection attempt detected", cleaned_input=input_text)
                
        # Check XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                logger.warning(f"XSS detected: {pattern}")
                return GuardrailValidationResult(is_safe=False, reason="Malicious script detected", cleaned_input=input_text)

        # Sanitize HTML tags
        cleaned = re.sub(r"<[^>]*>", "", input_text)
        return GuardrailValidationResult(is_safe=True, cleaned_input=cleaned)
