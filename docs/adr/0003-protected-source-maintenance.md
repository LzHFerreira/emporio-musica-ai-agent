# ADR-0003: Protected source maintenance and rollback

- Status: Implemented for six CSVs and the policy PDF. Process-crash tests pass; production security and physical power-loss durability are unproven.
- Date: 2026-11-02.

## Decision

Keep all seven source types canonical and publish complete, versioned snapshots through protected Django staff pages. Authenticated staff permissions separately gate viewing, editing, publishing, deletion and rollback; services repeat authorization checks. Customer/model paths cannot edit sources. Imported operational rows remain read-only in ordinary Django Admin.

Staff can stage cell changes or exact-schema uploads, inspect validation errors and a change preview, then publish the reviewed draft revision. Append skips identical rows and rejects conflicting identities; upsert replaces complete matching rows; replace may delete omitted rows only with separate deletion permission and preview confirmation. The six identities are category, product, promotion, customer, order and `(order_id, product_id)` IDs. Uploads validate the complete resulting datasets and references; no effective change reuses the current version.

Publication builds a complete protected bundle (merged CSVs, PDF, hashes and reviewed rules), regenerates derived prices and stages matching SQLite rows. One short expected-version transaction activates the bundle and writes the audit event. Stale drafts conflict; failures before commit leave the old version active, and after commit the new version is authoritative. Rollback reuses a retained hash-verified compatible bundle and is itself audited. Runtime bundles stay outside served paths and are ignored by Git. See [staff interface](../interfaces.md#staff-source-maintenance) and [PDF review](0002-pdf-ingestion-and-retrieval.md) for field-level contracts.

## Evidence and limits

Tests cover permissions/CSRF, edits/uploads, merge modes, validation, explicit deletion, stale revisions, rollback, PDF hash/revision binding and pricing consistency. A subprocess is terminated after staging, within activation before commit and after commit; a fresh process checks the active pointer, hashes, audit, policy and prices. This establishes tested process-crash recovery on the local filesystem/SQLite configuration, not power-loss durability or every contention schedule. See [validation](../validation.md) and [security review](../security-review.md).
