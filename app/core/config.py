"""Application configuration, loaded from environment variables / .env.

Centralizing config here means the LLM provider and model name are never
hardcoded elsewhere in the codebase - swap providers/models by editing
.env only.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    llm_provider: str = "groq"  # "groq" or "gemini"
    model_name: str = "llama-3.3-70b-versatile"

    groq_api_key: str = ""
    gemini_api_key: str = ""

    llm_timeout_seconds: int = 30
    log_level: str = "INFO"

    def active_api_key(self) -> str:
        """Return the API key relevant to the configured provider."""
        if self.llm_provider == "groq":
            return self.groq_api_key
        if self.llm_provider == "gemini":
            return self.gemini_api_key
        raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider}")


@lru_cache
def get_settings() -> Settings:
    # Cached so .env is parsed once per process, not on every call.
    return Settings()
