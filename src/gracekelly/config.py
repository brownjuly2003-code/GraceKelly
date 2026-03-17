from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True, frozen=True)
class Settings:
    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8011
    log_level: str = "INFO"
    storage_backend: str = "memory"
    postgres_dsn: str | None = None
    execution_profile: str = "dry-run"
    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_timeout_seconds: float = 30.0
    browser_enabled: bool = False
    browser_automation_backend: str = "null"
    browser_profile_dir: str | None = None
    browser_base_url: str = "https://www.perplexity.ai"
    browser_scripted_logged_in: bool = True
    browser_scripted_model_label: str | None = None
    browser_scripted_output_text: str = "scripted browser result"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            env=os.getenv("GRACEKELLY_ENV", "development"),
            host=os.getenv("GRACEKELLY_HOST", "127.0.0.1"),
            port=int(os.getenv("GRACEKELLY_PORT", "8011")),
            log_level=os.getenv("GRACEKELLY_LOG_LEVEL", "INFO"),
            storage_backend=os.getenv("GRACEKELLY_STORAGE_BACKEND", "memory"),
            postgres_dsn=os.getenv("GRACEKELLY_POSTGRES_DSN"),
            execution_profile=os.getenv("GRACEKELLY_EXECUTION_PROFILE", "dry-run"),
            mistral_api_key=os.getenv("GRACEKELLY_MISTRAL_API_KEY"),
            mistral_base_url=os.getenv("GRACEKELLY_MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
            mistral_timeout_seconds=float(os.getenv("GRACEKELLY_MISTRAL_TIMEOUT_SECONDS", "30")),
            browser_enabled=os.getenv("GRACEKELLY_BROWSER_ENABLED", "false").lower() == "true",
            browser_automation_backend=os.getenv("GRACEKELLY_BROWSER_AUTOMATION_BACKEND", "null"),
            browser_profile_dir=os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR"),
            browser_base_url=os.getenv("GRACEKELLY_BROWSER_BASE_URL", "https://www.perplexity.ai"),
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
        )


settings = Settings.from_env()
