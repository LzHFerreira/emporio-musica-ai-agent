"""Customer turn source-version contracts for the catalog and policy tools."""

from emporio.catalog import search_catalog
from emporio.catalog.models import SourceSnapshot
from emporio.policy import lookup_public_policy
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class PinnedSourceContractTests(SourceWorkflowFixture):
    def test_both_public_tools_read_the_explicit_retained_snapshot(self):
        from emporio.sources.drafts import create_draft, preview_draft, publish_draft, stage_cell

        pinned = self.snapshot
        self.grant("view_products", "edit_products", "publish_products")
        draft = create_draft(self.user)
        stage_cell(self.user, draft, "products", self.product.source_id, "name", "Changed name", expected_revision=0)
        preview_draft(self.user, draft)
        publish_draft(self.user, draft, expected_revision=1)
        self.assertNotEqual(SourceSnapshot.objects.get(is_active=True).version, pinned.version)
        catalog = search_catalog(
            query=self.product.name, mode="resolve", payment_method="unspecified",
            available_only=False, snapshot_version=pinned.version,
        )
        policy = lookup_public_policy(
            query="devolução compra online", snapshot_version=pinned.version,
        )
        self.assertEqual({s["bundle_version"] for s in catalog["sources"]}, {pinned.version})
        self.assertEqual({s["bundle_version"] for s in policy["sources"]}, {pinned.version})

    def test_unknown_pinned_version_fails_closed_for_both_tools(self):
        catalog = search_catalog(
            query=self.product.name, mode="resolve", payment_method="unspecified",
            available_only=False, snapshot_version="missing-version",
        )
        policy = lookup_public_policy(
            query="horário", topic="hours", snapshot_version="missing-version",
        )
        self.assertEqual((catalog["outcome"], catalog["error_category"]), ("error", "source_unavailable"))
        self.assertEqual((policy["outcome"], policy["error_category"]), ("error", "source_unavailable"))
