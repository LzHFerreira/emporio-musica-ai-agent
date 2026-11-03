from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile

from emporio.catalog.pricing import percentage_basis_points
from emporio.sources import policy_pdf
from emporio.sources.draft_bundle import (
    _base_rule,
    _manifest,
    _rule_name,
    _stage_policy,
    prepare_bundle,
)
from emporio.sources.draft_data import materialize
from emporio.sources.drafts import create_draft
from emporio.sources.read import CSV_FILES
from tests.policy_pdf_fixture import text_pdf
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class DraftBundlePolicyTests(SourceWorkflowFixture):
    def setUp(self):
        super().setUp()
        self.grant("edit_policy_pdf", "view_policy_pdf", "publish_policy_pdf")

    def test_prepare_bundle_copies_base_pdf_and_rebuilds_only_changed_csvs(self):
        draft = create_draft(self.user)
        sources = materialize(draft)
        _, manifest, version = prepare_bundle(sources, [], self.snapshot)
        self.assertEqual(manifest["pdf_sha256"], self.snapshot.manifest["pdf_sha256"])
        self.assertNotEqual(version, self.snapshot.version)

        _, changed, _ = prepare_bundle(sources, ["products"], self.snapshot)
        for name in CSV_FILES:
            if name != "products":
                self.assertEqual(
                    changed["csv_sha256"][name], self.snapshot.manifest["csv_sha256"][name]
                )
        self.assertEqual(_rule_name(300), "pix-3-v1")
        self.assertEqual(_rule_name(0), "pix-0-v1")

    def make_reviewed_pdf(self):
        base_dir = self.bundle_root / self.snapshot.version
        draft = create_draft(self.user)
        content = text_pdf(["PIX discount 3 percent"])
        draft = policy_pdf.stage_policy_pdf(
            self.user,
            draft,
            SimpleUploadedFile("policy.pdf", content),
            expected_revision=0,
        )
        review = {
            "pix_discount_percent": "3",
            "unchanged_rules_attested": "yes",
            "passage_reviews": (
                '[{"page":1,"section":"§3","topic":"payment",'
                '"audience":"public","conflict":false,"text":"PIX discount 3 percent"}]'
            ),
        }
        draft = policy_pdf.review_policy_pdf(
            self.user, draft, review, expected_revision=draft.revision
        )
        return draft, content, base_dir

    def test_pdf_bundle_requires_matching_review(self):
        base_dir = self.bundle_root / self.snapshot.version
        for policy in ({}, {"review": {}}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                _stage_policy(
                    Path(self.temp.name),
                    base_dir,
                    ["policy_pdf"],
                    policy,
                    self.snapshot.manifest["policy"],
                )

    def test_pdf_bundle_uses_reviewed_rule_and_hash(self):
        draft, content, _ = self.make_reviewed_pdf()
        sources = materialize(draft)
        _, manifest, _ = prepare_bundle(
            sources, ["policy_pdf"], self.snapshot, draft.policy
        )
        self.assertEqual(manifest["pix_basis_points"], 300)
        self.assertEqual(manifest["policy"]["pdf_sha256"], sha256(content).hexdigest())

    def test_pdf_bundle_rejects_candidate_hash_mismatch(self):
        draft, _, base_dir = self.make_reviewed_pdf()
        stale = {**draft.policy, "candidate_sha256": "stale"}
        with self.assertRaises(ValueError):
            _stage_policy(
                Path(self.temp.name),
                base_dir,
                ["policy_pdf"],
                stale,
                self.snapshot.manifest["policy"],
            )

    def test_base_rule_falls_back_for_unmanaged_legacy_snapshot_and_manifest_defaults(self):
        legacy = SimpleNamespace(manifest={}, pricing_rule_version="old", pix_basis_points=750)
        self.assertEqual(_base_rule(legacy)[1], percentage_basis_points("5"))
        root = Path(self.temp.name)
        for filename in CSV_FILES.values():
            (root / filename).write_text("source", encoding="utf-8")
        (root / "políticas_da_loja.pdf").write_bytes(b"pdf")
        manifest = _manifest(root, "rule", 500, {})
        self.assertEqual(manifest["policy_rule_code"], "")
