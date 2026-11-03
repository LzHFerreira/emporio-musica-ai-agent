"""Explicit provider selection and local-endpoint validation."""

from django.conf import settings

from emporio.chat.anthropic import AnthropicClient
from emporio.chat.cloudflare import CloudflareClient, _validate_config
from emporio.chat.ollama import OllamaClient, validate_ollama_configuration
from emporio.chat.openrouter import OpenRouterClient

_FREE_CLOUDFLARE_MODELS = {
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/zai-org/glm-4.7-flash",
}


def check_model_settings() -> None:
    """Validate provider credentials and any configured local endpoint."""
    provider = settings.MODEL_PROVIDER
    validator = _PROVIDER_VALIDATORS.get(provider)
    if validator is None:
        raise ValueError(
            "MODEL_PROVIDER must be cloudflare, ollama, openai, anthropic, or openrouter"
        )
    validator()


def _check_openrouter() -> None:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("Set OPENROUTER_API_KEY before using the OpenRouter provider")
    if not settings.ALLOW_PAID_MODELS and not settings.OPENROUTER_MODEL.endswith(":free"):
        raise ValueError("Set ALLOW_PAID_MODELS=true for a paid OpenRouter model")


def _check_ollama() -> None:
    validate_ollama_configuration(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)


def _check_cloudflare() -> None:
    _validate_config(
        settings.CLOUDFLARE_ACCOUNT_ID,
        settings.CLOUDFLARE_API_KEY,
        settings.CLOUDFLARE_MODEL,
    )
    if not settings.ALLOW_PAID_MODELS and settings.CLOUDFLARE_MODEL not in _FREE_CLOUDFLARE_MODELS:
        raise ValueError("Set ALLOW_PAID_MODELS=true for an unreviewed Cloudflare model")


def _check_openai() -> None:
    _check_paid_settings("openai")
    _check_openai_mode()


def _check_anthropic() -> None:
    _check_paid_settings("anthropic")


_PROVIDER_VALIDATORS = {
    "openrouter": _check_openrouter,
    "ollama": _check_ollama,
    "cloudflare": _check_cloudflare,
    "openai": _check_openai,
    "anthropic": _check_anthropic,
}


def _check_paid_settings(provider: str) -> None:
    if not settings.ALLOW_PAID_MODELS:
        raise ValueError("Set ALLOW_PAID_MODELS=true before using a paid provider")
    api_key = settings.OPENAI_API_KEY if provider == "openai" else settings.ANTHROPIC_API_KEY
    variable = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    if not api_key:
        raise ValueError(f"Set {variable} before using {provider}")


def _check_openai_mode() -> None:
    if settings.OPENAI_API_MODE not in {"responses", "chat_completions"}:
        raise ValueError("OPENAI_API_MODE must be responses or chat_completions")


def create_model_client():
    """Create the configured provider client without automatic fallback."""
    check_model_settings()
    return {
        "openrouter": OpenRouterClient,
        "ollama": OllamaClient,
        "cloudflare": CloudflareClient,
        "anthropic": AnthropicClient,
        "openai": _openai_client,
    }[settings.MODEL_PROVIDER]()


def _openai_client():
    from emporio.chat.openai import OpenAIClient

    return OpenAIClient()
