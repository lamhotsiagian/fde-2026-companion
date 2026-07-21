"""Typed schema for versioned guardrail policy packs.

A *policy pack* is the data half of the guardrail stack: every regex,
deny-list, and command-risk classification that shapes a verdict, expressed
as reviewable YAML instead of Python constants. The code half (validators,
gates, graph nodes) stays stable across policy releases; the pack carries its
own version and checksum so every verdict can be traced back to the exact
rule set that produced it.

Design rules enforced here (not in the docs — in the schema, so a bad pack
cannot load):

* every pattern must compile as a Python regex at load time;
* every rule carries a ``name`` (audit rows reference rules by name, never by
  regex text) and a ``note`` explaining why it exists;
* the destructive and expensive command sets may not overlap — a command has
  exactly one risk class;
* disabled rules stay in the file (``enabled: false``) so the review history
  shows *why* a rule was retired, instead of the rule silently vanishing.
"""

from __future__ import annotations

import re
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PatternRule(BaseModel):
    """One named, documented, individually toggleable regex rule."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    pattern: str = Field(min_length=1)
    enabled: bool = True
    note: str = ""

    @field_validator("pattern")
    @classmethod
    def _must_compile(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:  # fail at load, never at match time
            raise ValueError(f"regex does not compile: {exc}") from exc
        return v

    @cached_property
    def compiled(self) -> re.Pattern:
        return re.compile(self.pattern)


class PiiPolicy(BaseModel):
    """L1/L2 — PII redaction rules. Placeholder is ``[<NAME>_REDACTED]``."""

    model_config = ConfigDict(frozen=True)

    rules: list[PatternRule] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_names(self) -> "PiiPolicy":
        names = [r.name for r in self.rules]
        if len(names) != len(set(names)):
            raise ValueError("duplicate PII rule names")
        return self

    @cached_property
    def compiled(self) -> dict[str, re.Pattern]:
        return {r.name: r.compiled for r in self.rules if r.enabled}


class CombinedPattern:
    """Duck-types the ``search`` surface of ``re.Pattern`` across many rules.

    Python forbids global inline flags (``(?i)``) mid-pattern, so enabled
    rules are matched one by one instead of being joined into a single
    alternation. Guards only ever call ``.search``, so this is a drop-in for
    the legacy module-level ``INSTRUCTION_PATTERN`` constant."""

    __slots__ = ("_patterns",)

    def __init__(self, patterns: list[re.Pattern]):
        self._patterns = patterns

    def search(self, text: str) -> re.Match | None:
        for p in self._patterns:
            if (m := p.search(text)) is not None:
                return m
        return None


class InjectionPolicy(BaseModel):
    """L6 — instruction-shaped text heuristics for retrieved chunks."""

    model_config = ConfigDict(frozen=True)

    rules: list[PatternRule] = Field(min_length=1)

    @cached_property
    def combined(self) -> CombinedPattern:
        """Search across enabled rules — drop-in for the legacy
        module-level ``INSTRUCTION_PATTERN`` constant."""
        return CombinedPattern([r.compiled for r in self.rules if r.enabled])

    def first_match(self, text: str) -> str | None:
        """Name of the first enabled rule that matches, for audit detail."""
        for r in self.rules:
            if r.enabled and r.compiled.search(text):
                return r.name
        return None


class CommandPolicy(BaseModel):
    """L5 — risk classification and argument screening for slash commands."""

    model_config = ConfigDict(frozen=True)

    destructive: frozenset[str] = frozenset()
    expensive: frozenset[str] = frozenset()
    extra_allowed: frozenset[str] = frozenset()
    sql_fragment: PatternRule

    @model_validator(mode="after")
    def _one_risk_class_per_command(self) -> "CommandPolicy":
        overlap = self.destructive & self.expensive
        if overlap:
            raise ValueError(f"commands in both risk classes: {sorted(overlap)}")
        return self


class PolicyPack(BaseModel):
    """The complete, versioned rule set the guards consume.

    ``version`` is CalVer (``YYYY.MM.DD-NNN``) — policy releases are dated
    events, not API surface. ``checksum`` is the SHA-256 over the source
    files, computed by the loader; together they give every ``guard_audit``
    row an exact provenance."""

    model_config = ConfigDict(frozen=True)

    schema_rev: int = Field(ge=1)
    version: str = Field(pattern=r"^\d{4}\.\d{2}\.\d{2}-\d{3}$")
    owner: str = Field(min_length=1)
    description: str = ""
    pii: PiiPolicy
    injection: InjectionPolicy
    commands: CommandPolicy
    checksum: str = ""          # set by the loader, "" for builtin defaults
    source: str = "builtin"     # "files" | "builtin"

    def compile_all(self) -> None:
        """Touch every lazy-compiled pattern so a bad pack fails at load
        time inside the loader, never at match time inside a request."""
        _ = self.pii.compiled
        _ = self.injection.combined
        _ = self.commands.sql_fragment.compiled
