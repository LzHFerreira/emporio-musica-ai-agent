"""Minimal settings for the local CSV-backed catalog harness."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-only-harness-secret")
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "emporio.catalog.apps.CatalogConfig",
    "emporio.orders.apps.OrdersConfig",
    "emporio.chat.apps.ChatConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("EMPORIO_DB_PATH", BASE_DIR / ".emporio.sqlite3"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "America/Campo_Grande"
LANGUAGE_CODE = "pt-br"
ROOT_URLCONF = "emporio.urls"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/equipe/fontes/"
LOGOUT_REDIRECT_URL = LOGIN_URL
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "emporio/sources/templates"],
        "APP_DIRS": True,
    }
]
EMPORIO_PIX_BASIS_POINTS = 500
EMPORIO_PRICING_RULE_VERSION = "pix-500-v1"
META_APP_SECRET = os.environ.get(
    "META_APP_SECRET", os.environ.get("EMPORIO_META_APP_SECRET", "local-only-test-secret")
)
META_WEBHOOK_VERIFY_TOKEN = os.environ.get(
    "META_WEBHOOK_VERIFY_TOKEN",
    os.environ.get("EMPORIO_META_VERIFY_TOKEN", "local-only-verify-token"),
)
META_BUSINESS_ID = os.environ.get(
    "META_BUSINESS_ID", os.environ.get("EMPORIO_META_BUSINESS_ID", "100000000000001")
)
META_PHONE_NUMBER_ID = os.environ.get(
    "META_PHONE_NUMBER_ID", os.environ.get("EMPORIO_META_PHONE_NUMBER_ID", "100000000000002")
)
META_API_VERSION = "v24.0"
META_BASE_URL = os.environ.get(
    "META_API_BASE_URL", os.environ.get("EMPORIO_META_BASE_URL", "https://graph.facebook.com")
)
META_API_TOKEN = os.environ.get("META_ACCESS_TOKEN", os.environ.get("EMPORIO_META_API_TOKEN", ""))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")

MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "cloudflare").strip().lower()
ALLOW_PAID_MODELS = os.environ.get("ALLOW_PAID_MODELS", "false").lower() == "true"
CLOUDFLARE_API_KEY = os.environ.get("CLOUDFLARE_API_KEY") or os.environ.get(
    "CLOUDFLARE_API_TOKEN", ""
)
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_MODEL = os.environ.get("CLOUDFLARE_MODEL", "@cf/zai-org/glm-4.7-flash")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
# Local models on consumer CPUs/iGPUs read long prompts slowly; 60s cut off valid replies.
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))
# 60s matches the WhatsApp reply target; raise only for slow local models.
TURN_DEADLINE_SECONDS = float(os.environ.get("TURN_DEADLINE_SECONDS", "60"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
OPENAI_API_MODE = os.environ.get("OPENAI_API_MODE", "responses").strip().lower()
OPENAI_REASONING_EFFORT = os.environ.get("OPENAI_REASONING_EFFORT", "").strip().lower()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
