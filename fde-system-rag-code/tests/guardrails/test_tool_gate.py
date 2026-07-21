"""Unit tests for tool-gate argument validation and risk classification."""

import pytest

from app.guardrails.tool_gate import (
    DESTRUCTIVE, EXPENSIVE, CatalogScaleArgs, validate_args,
)


class TestValidateArgs:
    def test_catalog_scale_within_bounds(self):
        out = validate_args("catalog-scale", {"n": 2000, "seed": 42})
        assert out == {"n": 2000, "seed": 42}

    def test_catalog_scale_over_cap_rejected(self):
        with pytest.raises(ValueError, match="invalid argument"):
            validate_args("catalog-scale", {"n": 999_999})

    def test_catalog_scale_non_int_rejected(self):
        with pytest.raises(ValueError):
            validate_args("catalog-scale", {"n": "lots"})

    @pytest.mark.parametrize("payload", [
        "1; DROP TABLE interactions",
        "x' OR 1=1 --",
        "TRUNCATE tenants",
    ])
    def test_sql_fragments_rejected_on_any_command(self, payload):
        with pytest.raises(ValueError, match="disallowed token"):
            validate_args("classify-feedback", {"text": payload})

    def test_benign_free_text_arg_allowed(self):
        out = validate_args("classify-feedback",
                            {"text": "loved the movie, five stars"})
        assert out["text"].startswith("loved")


class TestRiskSets:
    def test_resets_are_destructive(self):
        assert {"reset-tenant-data", "reset-memory"} <= set(DESTRUCTIVE)

    def test_generation_commands_are_expensive(self):
        assert "catalog-scale" in EXPENSIVE

    def test_no_overlap_between_risk_classes(self):
        assert not (set(DESTRUCTIVE) & set(EXPENSIVE))


def test_catalog_scale_schema_defaults():
    args = CatalogScaleArgs(n=100)
    assert args.seed == 42  # reproducible by default
