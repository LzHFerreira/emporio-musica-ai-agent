# ADR-0001: SQLite through Django ORM

- Status: Implemented locally; broader contention and durability limits remain unqualified.
- Date: 2026-10-31; updated 2026-11-02.

## Decision

Use Django 5.2 LTS models, migrations and management commands with SQLite for derived catalog/order data and application-owned conversation, job, reply and delivery state. The web process persists accepted work; a separate worker processes it. Keep writes short and outside provider calls. The database is generated locally and is not committed.

The six CSVs and policy PDF remain canonical business sources. Imports and protected staff publication create versioned snapshots; database-only edits cannot change business facts. Conversational services enforce ownership and field allowlists. The model cannot issue SQL. Ordinary admin views of imported rows are read-only. See [staff publication](0003-protected-source-maintenance.md) and the [tool boundary](../data-access.md).

## Alternatives and tradeoffs

| Option | Reason |
| --- | --- |
| Direct CSV/in-memory reads | Simpler at this scale, but duplicates relational validation and query logic. |
| SQLite + Django ORM | Selected: relational queries and shared local state without a database service. Concurrent writes still need deployment-specific validation. |
| PostgreSQL | Revisit if deployment or measured write contention requires it. |

## Evidence and limits

Snapshot publication, source imports, pinned reads and process-termination recovery have automated tests. They do not prove broad simultaneous-process behavior or physical power-loss durability. SQLite stores derived business data and authoritative application state; it is not live-synchronized with an external database. See [validation](../validation.md) and [interfaces](../interfaces.md).
