import re
import json
from loguru import logger
from pydantic import BaseModel

class OutputGuardrailResult(BaseModel):
    is_valid: bool
    pii_detected: bool
    toxicity_detected: bool
    citation_present: bool
    reason: str | None = None
    sanitized_output: str

class OutputGuardrail:
    PII_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    }
    
    TOXIC_WORDS = ["hate", "kill", "harm", "exploit"]

    @classmethod
    def validate_and_sanitize(cls, output_text: str, require_citation: bool = False) -> OutputGuardrailResult:
        sanitized = output_text
        pii_found = False
        
        # 1. Mask PII
        for pii_type, pattern in cls.PII_PATTERNS.items():
            if re.search(pattern, sanitized):
                pii_found = True
                sanitized = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", sanitized)
                
        # 2. Check Toxicity
        toxic_found = any(word in sanitized.lower() for word in cls.TOXIC_WORDS)
        
        # 3. Check Citation requirement
        citation_found = bool(re.search(r"\[Document|Source|Ref\]", sanitized, re.IGNORECASE))
        
        reason = None
        if pii_found:
            reason = "PII redacted from output"
        if toxic_found:
            reason = "Toxic language filtered"
            
        return OutputGuardrailResult(
            is_valid=not toxic_found,
            pii_detected=pii_found,
            toxicity_detected=toxic_found,
            citation_present=citation_found,
            reason=reason,
            sanitized_output=sanitized,
        )
