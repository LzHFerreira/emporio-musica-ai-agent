import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".env.example"


def _template_values():
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


def _assert_safe_template():
    values = _template_values()
    for credential in ("CLOUDFLARE_API_KEY", "CLOUDFLARE_API_TOKEN", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        assert values[credential] == ""
    assert values["OPENROUTER_MODEL"] == "google/gemma-4-26b-a4b-it:free"
    assert values["EMPORIO_DB_PATH"] == ".emporio.sqlite3"


def test_template_defaults_keep_cloud_key_empty():
    _assert_safe_template()


def test_uv_env_file_supplies_django_config_without_exporting_key():
    uv = shutil.which("uv")
    assert uv is not None
    with tempfile.TemporaryDirectory() as directory:
        database = str(Path(directory) / "isolated.sqlite3")
        env_file = Path(directory) / "dummy.env"
        env_file.write_text(
            f"OPENROUTER_API_KEY=review-sentinel\nOPENROUTER_MODEL=review/model\nEMPORIO_DB_PATH={database}\n",
            encoding="utf-8",
        )
        command = [uv, "run", "--no-sync", "--env-file", str(env_file), "python", "-c", _CHECK_SETTINGS]
        cache = Path(directory) / "uv-cache"
        cache.mkdir()
        environment = _clean_environment(cache)
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "settings-loaded"
    assert "review-sentinel" not in result.stdout + result.stderr


def _clean_environment(cache):
    environment = os.environ.copy()
    for key in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "EMPORIO_DB_PATH"):
        environment.pop(key, None)
    environment["DJANGO_SETTINGS_MODULE"] = "emporio.settings"
    environment["UV_CACHE_DIR"] = str(cache)
    return environment


_CHECK_SETTINGS = """
from django.conf import settings
assert settings.OPENROUTER_API_KEY == 'review-sentinel'
assert settings.OPENROUTER_MODEL == 'review/model'
assert str(settings.DATABASES['default']['NAME']).endswith('isolated.sqlite3')
print('settings-loaded')
"""
