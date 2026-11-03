import csv
import io
from django.urls import reverse

from tests.staff_source_web_fixture import StaffSourceWebFixture


class StaffSourceWebTests(StaffSourceWebFixture):
    def test_login_browses_active_sqlite_table_with_source_permission(self):
        response = self.client.get(reverse("staff-source-index"))
        self.assertEqual(response.status_code, 302)
        self.login()
        response = self.client.get(reverse("staff-source-detail", args=["products"]))
        self.assertEqual(response.status_code, 403)
        self.grant("view_products")
        response = self.client.get(reverse("staff-source-detail", args=["products"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fontes de dados")
        self.assertContains(response, self.snapshot.version)
        self.assertContains(response, self.product.name)

    def test_view_edit_publish_and_rollback_permissions_are_separate(self):
        self.login()
        self.grant("view_products")
        detail = reverse("staff-source-detail", args=["products"])
        edit = reverse("staff-source-edit", args=["products", self.product.source_id])
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(edit, {"field": "name", "value": "Nome novo"}).status_code, 403)
        self.grant("edit_products")
        self.client.get(edit)
        self.assertEqual(self.post_with_csrf(edit, {"field": "name", "value": "Nome novo"}).status_code, 302)
        self.assertEqual(self.client.post(reverse("staff-source-publish", args=[1])).status_code, 403)
        self.assertEqual(self.client.post(reverse("staff-source-rollback", args=[self.snapshot.version])).status_code, 403)

    def test_csrf_protects_staff_mutations_and_page_forms_are_portuguese(self):
        self.login()
        self.grant("view_products", "edit_products")
        edit = reverse("staff-source-edit", args=["products", self.product.source_id])
        response = self.client.get(edit)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salvar")
        self.assertContains(response, "Publicar")
        self.assertEqual(self.client.post(edit, {"field": "name", "value": "Alterado"}).status_code, 403)
        csrf = self.client.cookies["csrftoken"].value
        response = self.post_with_csrf(edit, {"field": "name", "value": "Alterado", "csrfmiddlewaretoken": csrf})
        self.assertNotEqual(response.status_code, 403)

    def test_upload_preview_publish_and_rollback_flow_uses_reviewed_draft(self):
        self.login()
        self.grant("view_products", "edit_products", "publish_products", "rollback_sources")
        page = self.client.get(reverse("staff-source-detail", args=["products"]))
        self.assertContains(page, "Enviar arquivo CSV")
        rows = list(csv.DictReader((self.sources / "desafio_tecnico_ai_eng - products.csv").open(encoding="utf-8-sig")))
        rows[0]["name"] = "Instrumento revisado"
        upload = io.StringIO()
        writer = csv.DictWriter(upload, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
        upload.seek(0)
        upload_url = reverse("staff-source-upload", args=["products"])
        self.client.get(upload_url)
        created = self.post_with_csrf(upload_url, {"file": upload, "mode": "replace"})
        self.assertIn(created.status_code, (200, 302))
        draft_id = created.context["draft"].pk if created.context else created.json()["draft_id"]
        preview = self.client.get(reverse("staff-source-preview", args=[draft_id]))
        self.assertContains(preview, "Pré-visualização")
        self.assertContains(preview, "Instrumento revisado")
        published = self.post_with_csrf(reverse("staff-source-publish", args=[draft_id]), {})
        self.assertEqual(published.status_code, 302)
        rollback = self.post_with_csrf(reverse("staff-source-rollback", args=[self.snapshot.version]), {"reason": "Restaurar versão"})
        self.assertEqual(rollback.status_code, 302)
