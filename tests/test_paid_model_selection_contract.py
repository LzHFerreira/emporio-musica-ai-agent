"""Cost opt-in policy at provider selection, without API calls."""

import importlib

from django.test import SimpleTestCase, override_settings


class PaidModelSelectionContractTests(SimpleTestCase):
    def test_openrouter_free_model_stays_available_but_paid_model_requires_opt_in(self):
        providers = importlib.import_module("emporio.chat.providers")
        with override_settings(MODEL_PROVIDER="openrouter", OPENROUTER_API_KEY="key", OPENROUTER_MODEL="google/gemma-4-26b-a4b-it:free", ALLOW_PAID_MODELS=False):
            model = providers.create_model_client()
            self.assertEqual(model.model, "google/gemma-4-26b-a4b-it:free")
            model.client.close()
        with override_settings(MODEL_PROVIDER="openrouter", OPENROUTER_API_KEY="key", OPENROUTER_MODEL="provider/paid-model", ALLOW_PAID_MODELS=False):
            with self.assertRaisesRegex(ValueError, "ALLOW_PAID_MODELS"):
                providers.create_model_client()
        with override_settings(MODEL_PROVIDER="openrouter", OPENROUTER_API_KEY="key", OPENROUTER_MODEL="provider/paid-model", ALLOW_PAID_MODELS=True):
            model = providers.create_model_client()
            self.assertEqual(model.model, "provider/paid-model")
            model.client.close()

    def test_unreviewed_cloudflare_model_requires_paid_opt_in(self):
        providers = importlib.import_module("emporio.chat.providers")
        settings = {"MODEL_PROVIDER": "cloudflare", "CLOUDFLARE_API_KEY": "key", "CLOUDFLARE_ACCOUNT_ID": "acct", "CLOUDFLARE_MODEL": "@cf/example/unreviewed-tool-model"}
        with override_settings(**settings, ALLOW_PAID_MODELS=False):
            with self.assertRaisesRegex(ValueError, "ALLOW_PAID_MODELS"):
                providers.create_model_client()
        with override_settings(**settings, ALLOW_PAID_MODELS=True):
            model = providers.create_model_client()
            self.assertEqual(model.model, "@cf/example/unreviewed-tool-model")
            model.client.close()
