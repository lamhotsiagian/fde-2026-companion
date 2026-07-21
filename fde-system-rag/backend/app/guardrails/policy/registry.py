"""Process-wide policy registry: one source of truth, atomic hot reload.

The registry is the single seam between the policy *data plane* and the
guard *code plane*. Guards never read YAML and never hold a pack across
requests — they call ``policy_registry.get()`` at the moment they need a
rule, which makes every guard hot-reload aware for free.

Reload semantics:

* ``get()`` is cheap: a TTL-gated mtime fingerprint check (default 5 s), so
  the cost per request is a few ``stat()`` calls at most, usually nothing.
* Reload is **atomic**: the new pack is fully parsed, validated, and
  compiled before the reference is swapped under a lock. Readers see the
  old pack or the new pack, never a half-built one.
* Reload **fails closed to last-known-good**: a broken edit logs loudly and
  changes nothing. The guards keep enforcing the previous pack.
* Every swap is logged with version + checksum, mirroring what the audit
  layer (L9) records per verdict — so "which rules were live at 14:02?" is
  answerable from logs and ``guard_audit`` alike.

Operators can point ``GUARD_POLICY_DIR`` somewhere else (e.g. a ConfigMap
mount in Kubernetes) without touching code.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from loguru import logger

from .loader import PolicyError, builtin_defaults, load_pack, pack_files
from .schema import PolicyPack

DEFAULT_POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"


def _policy_dir() -> Path:
    return Path(os.environ.get("GUARD_POLICY_DIR", str(DEFAULT_POLICY_DIR)))


class PolicyRegistry:
    """Thread-safe holder of the current :class:`PolicyPack`."""

    def __init__(self, root: Path | None = None, ttl_seconds: float = 5.0):
        self._root = root
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._pack: PolicyPack | None = None
        self._fingerprint: tuple = ()
        self._next_check = 0.0

    @property
    def root(self) -> Path:
        return self._root if self._root is not None else _policy_dir()

    # -- public API -----------------------------------------------------------

    def get(self) -> PolicyPack:
        """Current pack; transparently hot-reloads when files changed."""
        now = time.monotonic()
        if self._pack is not None and now < self._next_check:
            return self._pack
        with self._lock:
            if self._pack is None or time.monotonic() >= self._next_check:
                self._maybe_reload()
                self._next_check = time.monotonic() + self._ttl
            return self._pack  # type: ignore[return-value]

    def reload(self) -> PolicyPack:
        """Force an immediate reload attempt (admin endpoint / tests).

        Raises :class:`PolicyError` so callers can surface the exact
        validation failure; the served pack is unchanged on failure."""
        with self._lock:
            self._load(force=True)
            self._next_check = time.monotonic() + self._ttl
            return self._pack  # type: ignore[return-value]

    # -- internals --------------------------------------------------------------

    def _current_fingerprint(self) -> tuple:
        try:
            return tuple(
                (str(p), p.stat().st_mtime_ns, p.stat().st_size)
                for p in pack_files(self.root)
            )
        except (PolicyError, OSError):
            return ()

    def _maybe_reload(self) -> None:
        """Best-effort reload inside ``get()``: never raises."""
        try:
            self._load(force=self._pack is None)
        except PolicyError as exc:
            if self._pack is None:  # nothing good to fall back to except builtins
                self._pack = builtin_defaults()
                logger.error(
                    "policy pack unloadable ({}); serving builtin defaults "
                    "version={}", exc, self._pack.version)
            else:
                logger.error(
                    "policy reload failed ({}); keeping last-known-good "
                    "version={} checksum={}", exc,
                    self._pack.version, self._pack.checksum[:12])

    def _load(self, force: bool) -> None:
        root = self.root
        if not (root / "manifest.yaml").exists():
            if self._pack is None:
                self._pack = builtin_defaults()
                logger.warning(
                    "no policy directory at {}; serving builtin defaults", root)
            return

        fingerprint = self._current_fingerprint()
        if not force and fingerprint == self._fingerprint:
            return  # unchanged — the common case

        pack = load_pack(root)  # raises PolicyError on any problem
        old = self._pack
        self._pack = pack
        self._fingerprint = fingerprint
        logger.info(
            "policy pack loaded version={} checksum={} rules(pii={}, injection={}) "
            "previous={}",
            pack.version, pack.checksum[:12],
            len(pack.pii.rules), len(pack.injection.rules),
            old.version if old else "none",
        )


policy_registry = PolicyRegistry()
