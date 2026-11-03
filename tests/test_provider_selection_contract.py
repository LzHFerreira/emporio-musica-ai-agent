from django.test import SimpleTestCase, override_settings

from emporio.chat.ollama import OllamaClient
from emporio.chat.openrouter import OpenRouterClient
from emporio.chat.providers import check_model_settings, create_model_client


class ProviderSelectionTests(SimpleTestCase):
    @override_settings(MODEL_PROVIDER="ollama", OPENROUTER_API_KEY="cloud-secret", OLLAMA_BASE_URL="http://127.0.0.1:11434/v1", OLLAMA_MODEL="qwen3:4b")
    def test_local_provider_needs_no_openrouter_key_and_receives_no_cloud_secret(self):
        check_model_settings()
        model = create_model_client()
        self.assertIsInstance(model, OllamaClient)
        self.assertEqual((model.base_url, model.model), ("http://127.0.0.1:11434/v1", "qwen3:4b"))
        self.assertNotIn("authorization", model.client.headers)
        model.client.close()

    @override_settings(MODEL_PROVIDER="openrouter", OPENROUTER_API_KEY="")
    def test_openrouter_requires_its_own_key(self):
        with self.assertRaises(ValueError):
            create_model_client()

    @override_settings(MODEL_PROVIDER="openrouter", OPENROUTER_API_KEY="router-key")
    def test_factory_returns_only_the_explicit_openrouter_provider(self):
        model = create_model_client()
        self.assertIsInstance(model, OpenRouterClient)
        model.client.close()

    @override_settings(MODEL_PROVIDER="ollama", OPENROUTER_API_KEY="", OLLAMA_BASE_URL="http://localhost:11434/v1", OLLAMA_MODEL="qwen3:4b")
    def test_factory_returns_only_the_explicit_local_provider(self):
        model = create_model_client()
        self.assertIsInstance(model, OllamaClient)
        model.client.close()

    def test_unknown_provider_fails_closed(self):
        with override_settings(MODEL_PROVIDER="unknown", OPENROUTER_API_KEY="key"):
            with self.assertRaises(ValueError):
                create_model_client()

    def test_ollama_url_allows_only_local_v1_endpoints(self):
        unsafe = ("https://example.com/v1", "http://localhost:11434/v1?token=secret", "http://user:secret@localhost:11434/v1", "http://127.0.0.1:9000/v1", "http://localhost/v2")
        for url in unsafe:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    OllamaClient(base_url=url)
                with override_settings(MODEL_PROVIDER="ollama", OLLAMA_BASE_URL=url, OLLAMA_MODEL="qwen3:4b"):
                    with self.assertRaises(ValueError):
                        check_model_settings()

    def test_cloud_model_tags_are_rejected_but_local_tag_is_allowed(self):
        for model in ("qwen3:4b-cloud", "gpt-oss:20b-cloud", "qwen3:cloud", "https://ollama.com/library/qwen3"):
            with self.subTest(model=model):
                with self.assertRaises(ValueError):
                    OllamaClient(model=model)
                with override_settings(MODEL_PROVIDER="ollama", OLLAMA_MODEL=model):
                    with self.assertRaises(ValueError):
                        check_model_settings()
        self.assertEqual(OllamaClient(model="qwen3:4b").model, "qwen3:4b")

    def test_invalid_url_syntax_and_empty_model_are_rejected(self):
        for url in ("http://[::1",):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaClient(base_url=url)
        with override_settings(OLLAMA_BASE_URL=None), self.assertRaises(ValueError):
            OllamaClient()
        for model in ("", " "):
            with self.subTest(model=model), self.assertRaises(ValueError):
                OllamaClient(model=model)
