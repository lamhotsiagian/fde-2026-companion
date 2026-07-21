"""Policy data plane for the guardrail stack.

Splits the guardrails into a *code plane* (validators, gates, graph nodes —
changes ship through deploys) and a *data plane* (regexes, deny-lists, risk
classifications — changes ship as versioned policy packs, reviewed like code
but reloaded without a restart).

Public surface:

    from app.guardrails.policy import policy_registry
    pack = policy_registry.get()          # current pack, hot-reload aware
    pack.pii.compiled                     # {name: re.Pattern}
    pack.injection.combined               # single alternation re.Pattern
    pack.commands.destructive             # frozenset[str]
    pack.version, pack.checksum           # provenance for audit rows
"""

from .registry import PolicyRegistry, policy_registry
from .schema import CommandPolicy, InjectionPolicy, PatternRule, PiiPolicy, PolicyPack
from .loader import PolicyError, builtin_defaults, load_pack

__all__ = [
    "PolicyRegistry", "policy_registry",
    "PolicyPack", "PiiPolicy", "InjectionPolicy", "CommandPolicy", "PatternRule",
    "PolicyError", "builtin_defaults", "load_pack",
]
