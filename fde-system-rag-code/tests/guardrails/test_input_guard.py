"""Unit tests for the deterministic tier of the input guard (pure code,
no DB, no model — these run in milliseconds and gate every CI build)."""

import pytest

from app.guardrails.validators import (
    PII_PATTERNS, looks_like_slash, normalize_input, redact_pii,
)


class TestNormalizeInput:
    def test_caps_length(self):
        assert len(normalize_input("x" * 10_000, max_chars=4000)) == 4000

    def test_nfkc_folds_fullwidth_homoglyphs(self):
        # Full-width "ignore" folds to ASCII, so keyword heuristics see it.
        assert "ignore" in normalize_input("ｉｇｎｏｒｅ")

    def test_strips_control_chars_keeps_newlines(self):
        out = normalize_input("a\x00b\x08c\nd\te")
        assert out == "abc\nd\te"


class TestRedactPII:
    def test_email_redacted_and_counted(self):
        text, counts = redact_pii("mail me at alice@example.com please")
        assert "[EMAIL_REDACTED]" in text and "alice@" not in text
        assert counts == {"email": 1}

    def test_ssn_redacted(self):
        text, counts = redact_pii("ssn 123-45-6789")
        assert "[SSN_REDACTED]" in text and counts["ssn"] == 1

    def test_benign_text_untouched(self):
        text, counts = redact_pii("what is NDCG@10 in chapter 6?")
        assert counts == {} and "NDCG@10" in text


class TestSlashDetection:
    @pytest.mark.parametrize("prompt,expected", [
        ("/catalog", True),
        ("  /tenant-demo  ", True),
        ("/catalog-scale n=2000", True),
        ("what does /catalog do?", False),
        ("//not-a-command", False),
        ("", False),
    ])
    def test_looks_like_slash(self, prompt, expected):
        assert looks_like_slash(prompt) is expected


def test_all_pii_patterns_compile_and_match_samples():
    samples = {
        "email": "bob@corp.io",
        "phone": "+1 415 555 1234",
        "credit_card": "4111 1111 1111 1111",
        "ssn": "078-05-1120",
    }
    for name, sample in samples.items():
        assert PII_PATTERNS[name].search(sample), f"{name} failed on {sample}"
