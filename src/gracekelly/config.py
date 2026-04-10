from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

if "pytest" not in sys.modules:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

logger = logging.getLogger(__name__)


def _env_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r, using default %s", name, raw, default)
        return int(default)


def _env_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %s", name, raw, default)
        return float(default)


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


@dataclass(slots=True, frozen=True)
class Settings:
    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8011
    log_level: str = "INFO"
    api_key: str | None = None
    storage_backend: str = "memory"
    postgres_dsn: str | None = None
    postgres_connect_timeout_seconds: int = 5
    postgres_pool_enabled: bool = False
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 5
    execution_profile: str = "dry-run"
    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_timeout_seconds: float = 30.0
    mistral_max_retries: int = 0
    mistral_retry_backoff_seconds: float = 1.0
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 60.0
    openai_max_retries: int = 0
    openai_retry_backoff_seconds: float = 1.0
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_timeout_seconds: float = 120.0
    anthropic_max_retries: int = 0
    anthropic_retry_backoff_seconds: float = 1.0
    browser_enabled: bool = False
    browser_automation_backend: str = "null"
    browser_profile_dir: str | None = None
    browser_base_url: str = "https://www.perplexity.ai"
    browser_playwright_channel: str = "chrome"
    browser_playwright_headless: bool = False
    browser_circuit_breaker_enabled: bool = True
    browser_circuit_breaker_failure_threshold: int = 3
    browser_circuit_breaker_cooldown_seconds: int = 60
    browser_scripted_logged_in: bool = True
    browser_scripted_model_label: str | None = None
    browser_scripted_output_text: str = "scripted browser result"
    sentry_dsn: str | None = None
    sentry_environment: str = "production"
    otel_endpoint: str | None = None
    otel_service_name: str = "gracekelly"
    redis_url: str | None = None
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10
    orchestrate_timeout_seconds: float | None = None
    # Health endpoint security
    health_expose_details: bool = False

    def validate(self) -> None:
        """Raise ValueError for invalid configuration combinations."""
        if self.storage_backend == "postgres" and not self.postgres_dsn:
            raise ValueError(
                "GRACEKELLY_POSTGRES_DSN is required when GRACEKELLY_STORAGE_BACKEND=postgres"
            )
        if self.orchestrate_timeout_seconds is not None and self.orchestrate_timeout_seconds <= 0.0:
            raise ValueError(
                f"GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS must be > 0.0, got {self.orchestrate_timeout_seconds}"
            )

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            env=os.getenv("GRACEKELLY_ENV", "development"),
            host=os.getenv("GRACEKELLY_HOST", "127.0.0.1"),
            port=_env_int("GRACEKELLY_PORT", "8011"),
            log_level=os.getenv("GRACEKELLY_LOG_LEVEL", "INFO"),
            api_key=os.getenv("GRACEKELLY_API_KEY"),
            storage_backend=os.getenv("GRACEKELLY_STORAGE_BACKEND", "memory"),
            postgres_dsn=os.getenv("GRACEKELLY_POSTGRES_DSN"),
            postgres_connect_timeout_seconds=_env_int("GRACEKELLY_POSTGRES_CONNECT_TIMEOUT_SECONDS", "5"),
            postgres_pool_enabled=os.getenv("GRACEKELLY_POSTGRES_POOL_ENABLED", "false").lower() == "true",
            postgres_pool_min_size=_env_int("GRACEKELLY_POSTGRES_POOL_MIN_SIZE", "1"),
            postgres_pool_max_size=_env_int("GRACEKELLY_POSTGRES_POOL_MAX_SIZE", "5"),
            execution_profile=os.getenv("GRACEKELLY_EXECUTION_PROFILE", "dry-run"),
            mistral_api_key=os.getenv("GRACEKELLY_MISTRAL_API_KEY"),
            mistral_base_url=os.getenv("GRACEKELLY_MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
            mistral_timeout_seconds=_env_float("GRACEKELLY_MISTRAL_TIMEOUT_SECONDS", "30"),
            mistral_max_retries=_env_int("GRACEKELLY_MISTRAL_MAX_RETRIES", "0"),
            mistral_retry_backoff_seconds=_env_float("GRACEKELLY_MISTRAL_RETRY_BACKOFF_SECONDS", "1.0"),
            openai_api_key=os.getenv("GRACEKELLY_OPENAI_API_KEY"),
            openai_base_url=os.getenv("GRACEKELLY_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_timeout_seconds=_env_float("GRACEKELLY_OPENAI_TIMEOUT_SECONDS", "60"),
            openai_max_retries=_env_int("GRACEKELLY_OPENAI_MAX_RETRIES", "0"),
            openai_retry_backoff_seconds=_env_float("GRACEKELLY_OPENAI_RETRY_BACKOFF_SECONDS", "1.0"),
            anthropic_api_key=os.getenv("GRACEKELLY_ANTHROPIC_API_KEY"),
            anthropic_base_url=os.getenv("GRACEKELLY_ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            anthropic_timeout_seconds=_env_float("GRACEKELLY_ANTHROPIC_TIMEOUT_SECONDS", "120"),
            anthropic_max_retries=_env_int("GRACEKELLY_ANTHROPIC_MAX_RETRIES", "0"),
            anthropic_retry_backoff_seconds=_env_float("GRACEKELLY_ANTHROPIC_RETRY_BACKOFF_SECONDS", "1.0"),
            browser_enabled=os.getenv("GRACEKELLY_BROWSER_ENABLED", "false").lower() == "true",
            browser_automation_backend=os.getenv("GRACEKELLY_BROWSER_AUTOMATION_BACKEND", "null"),
            browser_profile_dir=os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR"),
            browser_base_url=os.getenv("GRACEKELLY_BROWSER_BASE_URL", "https://www.perplexity.ai"),
            browser_playwright_channel=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL", "chrome"),
            browser_playwright_headless=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_HEADLESS", "false").lower()
            == "true",
            browser_circuit_breaker_enabled=os.getenv(
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_ENABLED",
                "true",
            ).lower()
            == "true",
            browser_circuit_breaker_failure_threshold=_env_int(
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3",
            ),
            browser_circuit_breaker_cooldown_seconds=_env_int(
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60",
            ),
            browser_scripted_logged_in=os.getenv(
                "GRACEKELLY_BROWSER_SCRIPTED_LOGGED_IN",
                "true",
            ).lower()
            == "true",
            browser_scripted_model_label=os.getenv("GRACEKELLY_BROWSER_SCRIPTED_MODEL_LABEL"),
            browser_scripted_output_text=os.getenv(
                "GRACEKELLY_BROWSER_SCRIPTED_OUTPUT_TEXT",
                "scripted browser result",
            ),
            sentry_dsn=os.getenv("GRACEKELLY_SENTRY_DSN") or None,
            sentry_environment=os.getenv("GRACEKELLY_SENTRY_ENVIRONMENT", "production"),
            otel_endpoint=os.getenv("GRACEKELLY_OTEL_ENDPOINT") or None,
            otel_service_name=os.getenv("GRACEKELLY_OTEL_SERVICE_NAME", "gracekelly"),
            redis_url=os.getenv("GRACEKELLY_REDIS_URL") or None,
            rate_limit_rpm=_env_int("GRACEKELLY_RATE_LIMIT_RPM", "60"),
            rate_limit_burst=_env_int("GRACEKELLY_RATE_LIMIT_BURST", "10"),
            orchestrate_timeout_seconds=_env_float("GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS", "0") or None,
            health_expose_details=os.getenv("GRACEKELLY_HEALTH_EXPOSE_DETAILS", "false").lower() == "true",
        )


settings = Settings.from_env()
