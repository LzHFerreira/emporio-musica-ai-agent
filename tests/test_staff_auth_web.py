from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class StaffAuthenticationWebTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "staff-login", password="secret", is_staff=True
        )
        self.client = Client(enforce_csrf_checks=True)

    def test_staff_login_redirects_to_portuguese_page_and_logout_ends_session(self):
        protected = "/equipe/fontes/"
        destination = self.client.get(protected)
        self.assertEqual(destination.status_code, 302)
        login_url = destination.headers["Location"]
        self.assertTrue(login_url.startswith("/accounts/login/?next="))
        form = self.client.get(login_url)
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'name="username"')
        self.assertContains(form, "Usuário")
        token = self.client.cookies["csrftoken"].value
        data = {"username": self.user.username, "password": "secret", "next": protected}
        self.assertEqual(self.client.post(login_url, data).status_code, 403)
        logged_in = self.client.post(login_url, data, HTTP_X_CSRFTOKEN=token)
        self.assertRedirects(logged_in, protected, fetch_redirect_response=False)
        page = self.client.get(protected)
        self.assertContains(page, "Fontes de dados")
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        token = self.client.cookies["csrftoken"].value
        self.assertEqual(self.client.post("/accounts/logout/").status_code, 403)
        ended = self.client.post("/accounts/logout/", HTTP_X_CSRFTOKEN=token)
        self.assertRedirects(ended, "/accounts/login/", fetch_redirect_response=False)
        self.assertEqual(self.client.get(protected).status_code, 302)

    def test_invalid_credentials_render_login_error_without_authenticating(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        token = self.client.cookies["csrftoken"].value
        response = self.client.post(
            "/accounts/login/",
            {"username": self.user.username, "password": "wrong"},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.client.get("/equipe/fontes/").status_code, 302)
