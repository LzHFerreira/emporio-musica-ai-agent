# ADR-0001: Use SQLite for structured operational data

- Status: SQLite accepted; Django integration under review following the WhatsApp channel decision (2026-11-01).
- Date: 2026-10-31

## Context

The prototype uses small related CSV datasets as its canonical project sources and needs relational queries with application-enforced access to restricted fields and orders. SQLite is a derived query store, not an independent business-data authority. There is no demonstrated need for a separate database server or concurrent writes.

## Decision

Use SQLite as the application SQL database. The Django models, ORM, management commands and Admin discussed below belong to the initial integration proposal; re-evaluate them against the [WhatsApp channel requirements](../requirements.md#purpose-and-scope) before implementation.

Keep CSVs as versioned canonical project sources. A management command transactionally validates and repeatably imports selected data into SQLite, preserving source IDs and source-file provenance without duplicating unchanged records. In a real-world scenario, the responsible BU owns updating the canonical data. A BU-facing maintenance interface may be implemented if time permits; any such interface must update the canonical source through validation rather than introduce database-only facts.

Generate the database locally through migrations and the import command; do not commit the database file or SQLite sidecar files. Document the exact setup commands when implemented.

Expose read-only services that enforce permissions, customer ownership and field allowlists before returning data. Do not let the model generate or execute arbitrary SQL. If included, Django Admin is authorized for read-only inspection.

## Alternatives considered

| Alternative | Assessment |
| --- | --- |
| Direct CSV or in-memory queries | Feasible at this size, but requires custom handling of joins, validation and lookup behavior that Django models can centralize. |
| SQLite through Django ORM | Selected: supports relational queries and migrations without a separately managed database service. |
| PostgreSQL | Adds provisioning and configuration without a demonstrated prototype requirement. Reconsider if deployment or concurrent-write needs justify it. |

## Consequences

Setup requires schema migrations and canonical-source import. Import validation, source-update and reconciliation semantics need implementation and tests. SQLite remains a derived store; answers reflect the canonical source version imported into it. The prototype does not claim live synchronization with external operational systems.

Django models do not themselves establish authorization or prevent sensitive disclosure. Application services must enforce those boundaries independently of model instructions.

This decision selects storage for structured CSV data. It does not select an agent framework, policy retrieval architecture, model or provider, and does not constitute an implementation or validation result.

## Related documents

- [Requirements](../requirements.md)
- [Data-access design](../data-access.md)
