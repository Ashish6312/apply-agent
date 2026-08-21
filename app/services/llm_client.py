"""LLM provider factory.

Every node that needs the LLM calls get_chat_model() instead of
instantiating ChatGroq/ChatGoogleGenerativeAI directly. This is the single
place that reads LLM_PROVIDER / MODEL_NAME, so the rest of the codebase
never hardcodes a provider or model name (per project requirement).
"""
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMConfigurationError(Exception):
    """Raised when the configured provider has no usable API key."""


def get_chat_model() -> BaseChatModel:
    """Build a LangChain chat model for the configured provider.

    Raises LLMConfigurationError early (at graph-run time, not deep inside
    a node) if the required API key is missing, so the API layer can return
    a clear 4xx instead of an opaque provider error.
    """
    settings = get_settings()
    api_key = settings.active_api_key()
    if not api_key:
        raise LLMConfigurationError(
            f"LLM_PROVIDER is set to '{settings.llm_provider}' but its API key is missing. "
            "Set GROQ_API_KEY or GEMINI_API_KEY in .env."
        )

    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.model_name,
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            temperature=0.2,
        )

    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.model_name,
            google_api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            temperature=0.2,
        )

    raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


class EmptyLLMResponseError(Exception):
    """Raised when a call technically succeeds but returns blank content.

    Free/rate-limited models occasionally return a 200 with an empty or
    whitespace-only completion (no exception to catch) - without this check
    that blank string would sail straight through into a "generated" cover
    letter or gap analysis with a hole where the content should be, instead
    of triggering the same fallback path a real failure would.
    """


def invoke_with_retry(runnable: Runnable, prompt: str, attempts: int = 3) -> Any:
    """Invoke a (possibly structured-output) chain with retries on failure.

    Open-weight models occasionally skip the forced tool call on a long
    structured-output request (a Groq/tool-calling quirk, not a logic bug) -
    a single retry resolves most of these transient failures cheaply, before
    the caller's own except-block falls back to a deterministic default.

    Also retries a "successful" call that came back with empty content
    (see EmptyLLMResponseError) - a blank response isn't a Python exception,
    so without this it would silently pass straight through as if it were
    real generated content.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = runnable.invoke(prompt)
            content = getattr(result, "content", None)
            if isinstance(content, str) and not content.strip():
                raise EmptyLLMResponseError("Model returned an empty completion.")
            return result
        except Exception as exc:  # noqa: BLE001 - provider errors vary in type
            last_error = exc
            logger.warning("LLM call failed on attempt %d/%d: %s", attempt, attempts, exc)
    raise last_error
