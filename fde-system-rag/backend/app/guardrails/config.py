"""Guardrail configuration.

Every threshold that shapes a guard verdict lives here, loaded from the
environment via pydantic-settings so operators can retune guards without a
deploy. Extends the pattern of ``app.config.Settings`` and the variables
documented in ``env.example``.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class GuardSettings(BaseSettings):
    """Thresholds and budgets for the ten-layer guardrail stack.

    All values are safe-by-default: if the env file is missing, the guards
    run with conservative production settings rather than disabling.
    """

    # --- L1 input guard -----------------------------------------------------
    injection_threshold: float = Field(default=0.8, alias="GUARD_INJECTION_THRESHOLD")
    toxicity_threshold: float = Field(default=0.8, alias="GUARD_TOXICITY_THRESHOLD")
    max_input_chars: int = Field(default=4000, alias="GUARD_MAX_INPUT_CHARS")

    # --- L3 intent guard ----------------------------------------------------
    topic_min_cosine: float = Field(default=0.72, alias="GUARD_TOPIC_MIN_COSINE")

    # --- L6 retrieval guard -------------------------------------------------
    doc_min_cosine: float = Field(default=0.65, alias="GUARD_DOC_MIN_COSINE")

    # --- L4 / L2 semantic + output guards ------------------------------------
    grounding_min: float = Field(default=0.7, alias="GUARD_GROUNDING_MIN")
    dedup_max_cosine: float = Field(default=0.95, alias="GUARD_DEDUP_MAX_COSINE")
    max_retries: int = Field(default=2, alias="GUARD_MAX_RETRIES")

    # --- L7 rate & cost guards ----------------------------------------------
    session_token_cap: int = Field(default=20_000, alias="GUARD_SESSION_TOKEN_CAP")
    tenant_daily_token_cap: int = Field(default=500_000, alias="GUARD_TENANT_DAILY_TOKEN_CAP")
    rate_limit_rpm: int = Field(default=30, alias="GUARD_RATE_LIMIT_RPM")
    expensive_command_daily_cap: int = Field(default=20, alias="GUARD_EXPENSIVE_CMD_DAILY_CAP")
    breaker_failure_threshold: int = Field(default=5, alias="GUARD_BREAKER_FAILURES")
    breaker_reset_seconds: float = Field(default=30.0, alias="GUARD_BREAKER_RESET_SECONDS")
    ollama_timeout_seconds: float = Field(default=20.0, alias="GUARD_OLLAMA_TIMEOUT_SECONDS")

    # --- Guard model routing -------------------------------------------------
    judge_model: str = Field(default="llama3.1", alias="GUARD_JUDGE_MODEL")
    classifier_model: str = Field(default="llama3.2:1b", alias="GUARD_CLASSIFIER_MODEL")

    # --- Master switch -------------------------------------------------------
    # When False the app uses its legacy (unguarded) chat path, so the whole
    # stack can be rolled back with one env var and no deploy.
    enabled: bool = Field(default=True, alias="GUARD_ENABLED")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", extra="allow", populate_by_name=True
    )


guard_settings = GuardSettings()
