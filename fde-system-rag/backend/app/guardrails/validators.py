"""Shared deterministic validators: normalization, PII, injection heuristics.

Tier-0 guards. Everything in this module is pure code — no model calls, no
database — so it runs in microseconds and is trivially unit-testable
(``tests/guardrails/test_input_guard.py``).

The *rules* these validators enforce (PII regexes, injection heuristics,
SQL-fragment screens) no longer live here: they are data, loaded from the
versioned policy pack under ``policies/`` via
``app.guardrails.policy.policy_registry`` and hot-reloadable without a
restart. This module keeps only the *mechanics* (how to redact, how to
neutralize) plus PEP 562 shims so the legacy constant names
(``PII_PATTERNS``, ``INSTRUCTION_PATTERN``, ``SQL_FRAGMENT_RE``) keep
working for existing imports and tests.
"""

import re
import unicodedata

from .config import guard_settings
from .policy import policy_registry

# --- Slash-command shape (mirrors app.course.routes.parse_slash_command) ----
# Structural, not policy: this mirrors the command parser, so it versions
# with the code, not with the policy pack.
SLASH_RE = re.compile(r"^/[a-z][a-z0-9-]*")


# --- Policy accessors ---------------------------------------------------------
# Call sites should prefer these functions: each call sees the *current*
# pack, so a hot-reloaded rule change applies to the very next request.

def pii_patterns() -> dict[str, re.Pattern]:
    """Enabled PII rules from the live policy pack."""
    return policy_registry.get().pii.compiled


def instruction_pattern():
    """Combined indirect-injection matcher from the live policy pack
    (a ``CombinedPattern``; supports ``.search`` like ``re.Pattern``).

    Instruction-shaped text inside reference documents is the signature of
    indirect prompt injection (Greshake et al., 2023).
    """
    return policy_registry.get().injection.combined


def sql_fragment_re() -> re.Pattern:
    """SQL-fragment screen for slash-command arguments (L5)."""
    return policy_registry.get().commands.sql_fragment.compiled


def __getattr__(name: str):  # PEP 562: legacy constant names, now live views
    if name == "PII_PATTERNS":
        return pii_patterns()
    if name == "INSTRUCTION_PATTERN":
        return instruction_pattern()
    if name == "SQL_FRAGMENT_RE":
        return sql_fragment_re()
    raise AttributeError(f"module 'app.guardrails.validators' has no attribute '{name}'")


def normalize_input(raw: str, max_chars: int | None = None) -> str:
    """NFKC-normalize, strip control chars, and cap length.

    NFKC folds homoglyph tricks (full-width chars, ligatures) that attackers
    use to slip past keyword filters; the cap bounds classifier and embedding
    cost before anything downstream runs.
    """
    cap = max_chars or guard_settings.max_input_chars
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    return text[:cap]


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace PII spans with typed placeholders; report counts per type.

    Returns the redacted text and a ``{pii_type: count}`` map so the caller
    can log *that* redaction happened without logging *what* was redacted.
    """
    counts: dict[str, int] = {}
    for pii_type, pattern in pii_patterns().items():
        text, n = pattern.subn(f"[{pii_type.upper()}_REDACTED]", text)
        if n:
            counts[pii_type] = n
    return text, counts


def neutralize(chunk_text: str) -> str:
    """Defang instruction-shaped lines inside a retrieved document chunk.

    We keep the chunk (it may still carry useful content) but wrap the
    offending lines so the generator sees them as quoted data, not directives.
    """
    pattern = instruction_pattern()
    lines = []
    for line in chunk_text.splitlines():
        if pattern.search(line):
            lines.append(f"[quoted, non-instructional text] {line}")
        else:
            lines.append(line)
    return "\n".join(lines)


def looks_like_slash(text: str) -> bool:
    """True when the message should route to the deterministic command path."""
    return bool(SLASH_RE.match(text.strip()))
