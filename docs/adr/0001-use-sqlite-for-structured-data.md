# ADR-0001: Use SQLite for structured operational data

- Status: Accepted
- Date: 2026-10-31

## Context

The Django prototype uses small related CSV snapshots and needs relational queries with application-enforced access to restricted fields and orders. It has no demonstrated need for a separate database server or concurrent writes.

## Decision

Use SQLite as the application SQL database, accessed through Django models and the Django ORM.

Keep synthetic CSVs as versioned fixtures. A management command transactionally validates and repeatably imports selected data, preserving source IDs and snapshot provenance without duplicating unchanged records.

Generate the database locally through migrations and the import command; do not commit the database file or SQLite sidecar files. Document the exact setup commands when implemented.

Expose read-only services that enforce permissions, customer ownership and field allowlists before returning data. Do not let the model generate or execute arbitrary SQL. If included, Django Admin is authorized for read-only inspection.

## Alternatives considered

| Alternative | Assessment |
| --- | --- |
| Direct CSV or in-memory queries | Feasible at this size, but requires custom handling of joins, validation and lookup behavior that Django models can centralize. |
| SQLite through Django ORM | Selected: supports relational queries and migrations without a separately managed database service. |
| PostgreSQL | Adds provisioning and configuration without a demonstrated prototype requirement. Reconsider if deployment or concurrent-write needs justify it. |

## Consequences

Setup requires schema migrations and fixture import. Import validation and source-update semantics need implementation and tests. SQLite remains a snapshot-backed store; importing records does not make prices, stock, promotions or order statuses live.

Django models do not themselves establish authorization or prevent sensitive disclosure. Application services must enforce those boundaries independently of model instructions.

This decision selects storage for structured CSV data. It does not select an agent framework, policy retrieval architecture, model or provider, and does not constitute an implementation or validation result.

## Related documents

- [Requirements](../requirements.md)
- [Data-access design](../data-access.md)
