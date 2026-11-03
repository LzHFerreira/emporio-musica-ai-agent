import csv
import io
from types import SimpleNamespace

from django.urls import reverse

from emporio.sources.read import CSV_FILES, CSV_HEADERS
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class AllSixSqliteTablesProjectCanonicalCsvColumnsTests(SourceWorkflowFixture):
    def test_all_six_sqlite_tables_project_canonical_csv_columns(self):
        from emporio.sources.source_tables import source_rows

        for source, headers in CSV_HEADERS.items():
            with self.subTest(source=source):
                rows = source_rows(self.snapshot, source)
                self.assertTrue(rows)
                self.assertEqual(tuple(rows[0]), headers)
                self.assertEqual(
                    len(rows),
                    len(
                        list(
                            csv.DictReader(
                                (self.sources / CSV_FILES[source]).open(encoding="utf-8-sig")
                            )
                        )
                    ),
                )
        with self.assertRaises(ValueError):
            source_rows(self.snapshot, "unknown")


class SourceWebErrorDisplayTests(SourceWorkflowFixture):
    def test_error_messages_cover_import_mutation_and_lookup_failures(self):
        from emporio.sources.source_web import display_error

        errors = [
            ("invalid columns: x.csv", "colunas"),
            ("invalid CSV: x", "interpretar"),
            ("invalid row count or shape: x", "vazio"),
            ("stale revision", "mudou"),
            ("not found", "encontrado"),
            ("missing permission", "autorização"),
            ("duplicate", "duplicadas"),
            ("unknown reference", "inexistente"),
            ("invalid value", "inválido"),
            ("provider error", "concluir"),
        ]
        for message, expected in errors:
            self.assertIn(expected, display_error(ValueError(message)))


class SourceWebTypedControlTests(SourceWorkflowFixture):
    def test_controls_format_fields_and_report_requiredness(self):
        from emporio.sources.source_web import (
            _control_kind,
            _control_value,
            _edit_context,
            _is_required,
        )

        self.assertEqual(_control_value("order_date", "10/15/2025"), "2025-10-15")
        self.assertEqual(_control_value("name", "x"), "x")
        kinds = {
            "is_active": "boolean",
            "specs": "json",
            "price_brl": "decimal",
            "stock_quantity": "integer",
            "created_at": "date",
            "name": "text",
        }
        for field, expected in kinds.items():
            self.assertEqual(_control_kind(field), expected)
        self.assertFalse(_is_required("products", "description"))
        self.assertTrue(_is_required("products", "name"))
        context = _edit_context(
            "products", {"product_id": "1", "name": "x"}, ("name",), SimpleNamespace(revision=0)
        )
        self.assertEqual(context["identity"], "1")


class IndexAuthAndAllSourceDetailsSupportSearchPaginationAndPermissionsTests(SourceWorkflowFixture):
    def test_index_auth_and_all_source_details_support_search_pagination_and_permissions(self):
        index = reverse("staff-source-index")
        self.assertEqual(self.client.get(index).status_code, 302)
        self.login()
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(index).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.grant(*[f"view_{name}" for name in CSV_HEADERS])
        self.grant("rollback_sources")
        self.client.get(index)
        for source in CSV_HEADERS:
            response = self.client.get(reverse("staff-source-detail", args=[source]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, CSV_HEADERS[source][0])
        self.assertEqual(
            self.client.get(reverse("staff-source-detail", args=["bogus"])).status_code, 403
        )
        filtered = self.client.get(
            reverse("staff-source-detail", args=["products"]), {"q": self.product.name[:5]}
        )
        self.assertContains(filtered, self.product.name)
        self.assertEqual(
            self.client.get(
                reverse("staff-source-detail", args=["products"]), {"page": "999"}
            ).status_code,
            200,
        )


class EditAndUploadRoutesCoverPermissionsInvalidValuesAndSuccessTests(SourceWorkflowFixture):
    def test_edit_and_upload_routes_cover_permissions_invalid_values_and_success(self):
        self.login()
        product_edit = reverse("staff-source-edit", args=["products", self.product.source_id])
        self.assertEqual(self.client.get(product_edit).status_code, 403)
        self.grant("view_products", "edit_products")
        response = self.client.get(product_edit)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.cookies.get("csrftoken"))
        bad = self.post_csrf(product_edit, {"field": "product_id", "value": "7"})
        self.assertEqual(bad.status_code, 400)
        saved = self.post_csrf(product_edit, {"field": "name", "value": "Nome revisado"})
        self.assertEqual(saved.status_code, 302)
        upload_url = reverse("staff-source-upload", args=["products"])
        self.assertEqual(self.client.get(upload_url).status_code, 200)
        self.assertEqual(self.post_csrf(upload_url, {}).status_code, 400)
        file = io.BytesIO(b"wrong,columns\n1,2\n")
        file.name = "invalid.csv"
        invalid = self.post_csrf(upload_url, {"file": file, "mode": "append"})
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, "inválido", status_code=400)
