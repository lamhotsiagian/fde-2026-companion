"""Load and validate a policy pack from a versioned directory of YAML files.

Layout (``app/guardrails/policies/``)::

    policies/
    ├── manifest.yaml     # version, owner, which file carries which section
    ├── pii.yaml          # L1/L2 redaction rules
    ├── injection.yaml    # L6 indirect-injection heuristics
    └── commands.yaml     # L5 risk classes + SQL-fragment screen

Loading is strict and atomic: parse every file, validate the whole pack
against the schema, force-compile every regex, and only then hand the pack
to the registry. Any failure raises :class:`PolicyError` — the registry
keeps serving the last-known-good pack, so a broken edit can never take
the guards down or (worse) silently disable them.

``builtin_defaults()`` reproduces the rule set that previously lived as
constants in ``validators.py`` / ``tool_gate.py``. It is the fallback when
no policy directory exists, which keeps behaviour identical for anyone who
checked out the repo before the data plane existed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from .schema import CommandPolicy, InjectionPolicy, PatternRule, PiiPolicy, PolicyPack


class PolicyError(ValueError):
    """A policy pack failed to parse, validate, or compile."""


MANIFEST = "manifest.yaml"

# --- Builtin defaults: byte-for-byte the legacy hard-coded rules -------------

_DEFAULT_PII = [
    {"name": "email", "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
     "note": "RFC-ish address shape"},
    {"name": "phone",
     "pattern": r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b",
     "note": "international + US shapes"},
    {"name": "credit_card", "pattern": r"\b(?:\d[ -]?){13,19}\b",
     "note": "13-19 digit PAN with separators"},
    {"name": "ssn", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "note": "US SSN"},
]

_DEFAULT_INJECTION = [
    {"name": "override-instructions",
     "pattern": r"(?i)\b(ignore (all|previous|above)|disregard (the|all|previous))",
     "note": "classic instruction override (Greshake et al., 2023)"},
    {"name": "role-reassignment",
     "pattern": r"(?i)\b(you are now|new instructions?:)",
     "note": "persona / instruction replacement"},
    {"name": "system-prompt-probe", "pattern": r"(?i)\bsystem prompt\b",
     "note": "prompt-extraction probe"},
    {"name": "counter-instruction",
     "pattern": r"(?i)\b(do not follow|instead,? (do|say|run|execute))",
     "note": "negation / redirection of prior instructions"},
    {"name": "command-smuggling", "pattern": r"(?i)\b(run the command|type /)",
     "note": "tries to trigger the slash-command path from a document"},
]

_DEFAULT_COMMANDS = {
    "destructive": ["reset-tenant-data", "reset-memory"],
    "expensive": ["catalog-scale", "tenant-users", "memory-session"],
    "extra_allowed": ["catalog"],
    "sql_fragment": {
        "name": "sql-fragment",
        "pattern": r"(?i)(;|--|\b(drop|delete|truncate|update|insert|alter|grant)\b)",
        "note": "screens every free-string slash-command argument",
    },
}


def builtin_defaults() -> PolicyPack:
    """The legacy rule set as a pack — fallback of last resort."""
    pack = PolicyPack(
        schema_rev=1,
        version="2026.01.01-000",
        owner="builtin",
        description="Compiled-in defaults mirroring the pre-data-plane constants.",
        pii=PiiPolicy(rules=[PatternRule(**r) for r in _DEFAULT_PII]),
        injection=InjectionPolicy(rules=[PatternRule(**r) for r in _DEFAULT_INJECTION]),
        commands=CommandPolicy(
            destructive=frozenset(_DEFAULT_COMMANDS["destructive"]),
            expensive=frozenset(_DEFAULT_COMMANDS["expensive"]),
            extra_allowed=frozenset(_DEFAULT_COMMANDS["extra_allowed"]),
            sql_fragment=PatternRule(**_DEFAULT_COMMANDS["sql_fragment"]),
        ),
        source="builtin",
    )
    pack.compile_all()
    return pack


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file missing: {path.name}") from exc
    except yaml.YAMLError as exc:
        raise PolicyError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError(f"{path.name}: expected a mapping at top level")
    return data


def pack_files(root: Path) -> list[Path]:
    """Every file that participates in the pack checksum, sorted for
    deterministic hashing."""
    manifest = _read_yaml(root / MANIFEST)
    files = manifest.get("files", {})
    return sorted([root / MANIFEST] + [root / f for f in files.values()])


def load_pack(root: Path) -> PolicyPack:
    """Parse, validate, compile, and fingerprint the pack under ``root``."""
    manifest = _read_yaml(root / MANIFEST)
    files = manifest.get("files", {})
    for section in ("pii", "injection", "commands"):
        if section not in files:
            raise PolicyError(f"manifest.yaml: missing files.{section}")

    pii_doc = _read_yaml(root / files["pii"])
    inj_doc = _read_yaml(root / files["injection"])
    cmd_doc = _read_yaml(root / files["commands"])

    digest = hashlib.sha256()
    for path in pack_files(root):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())

    try:
        pack = PolicyPack(
            schema_rev=manifest.get("schema", 0),
            version=manifest.get("version", ""),
            owner=manifest.get("owner", ""),
            description=manifest.get("description", ""),
            pii=PiiPolicy(**pii_doc),
            injection=InjectionPolicy(**inj_doc),
            commands=CommandPolicy(**cmd_doc),
            checksum=digest.hexdigest(),
            source="files",
        )
        pack.compile_all()
    except (ValueError, TypeError) as exc:  # pydantic ValidationError included
        raise PolicyError(f"policy pack invalid: {exc}") from exc
    return pack
