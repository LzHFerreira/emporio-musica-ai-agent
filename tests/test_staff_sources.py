from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from emporio.catalog.models import SourceSnapshot


class StaffSourcesTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user("source-staff", is_staff=True)

    def test_active_staff_gets_portuguese_source_index(self):
        from emporio.sources.views import source_index

        request = self.factory.get("/equipe/fontes/")
        request.user = self.user
        response = source_index(request)
        self.assertContains(response, "Fontes de dados")

    def test_active_staff_sees_source_names(self):
        from emporio.sources.read import CSV_FILES
        from emporio.sources.views import source_index

        request = self.factory.get("/equipe/fontes/")
        content_type = ContentType.objects.get_for_model(SourceSnapshot)
        for name in CSV_FILES:
            Permission.objects.get_or_create(
                content_type=content_type, codename=f"view_{name}", defaults={"name": name}
            )
        self.user.user_permissions.add(*Permission.objects.filter(content_type=content_type, codename__startswith="view_"))
        request.user = self.user
        response = source_index(request)

        labels = {
            "categories": "Categorias", "products": "Produtos", "promotions": "Promoções",
            "customers": "Clientes", "orders": "Pedidos", "order_items": "Itens dos pedidos",
        }
        self.assertEqual(response.status_code, 200)
        for name, filename in CSV_FILES.items():
            with self.subTest(source=name):
                self.assertContains(response, labels[name])
                self.assertContains(response, f"/equipe/fontes/{name}/")
                self.assertContains(response, filename)

    def test_nonstaff_cannot_use_source_index(self):
        from emporio.sources.views import source_index

        request = self.factory.get("/equipe/fontes/")
        request.user = get_user_model().objects.create_user("customer", is_staff=False)
        self.assertEqual(source_index(request).status_code, 403)
