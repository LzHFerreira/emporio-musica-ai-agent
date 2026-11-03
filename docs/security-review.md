# Local security review

Scope: synthetic fixtures, staff source maintenance, retrieval, customer tools, signed webhook and local worker/transport. This is a targeted source review with adversarial tests, not a penetration test, production certification or live-provider assessment. See [requirements](requirements.md), [interface contracts](interfaces.md) and [validation evidence](validation.md).

## Boundaries and controls

| Risk | Control and evidence limit |
| --- | --- |
| Forged sender or replayed event | Verify raw-body HMAC and business scope before parsing trusted identity; deduplicate by scoped provider ID and reject conflicting reuse. Tests cover signatures, batches and duplicates. |
| Unauthorized customer/source access | Application supplies sender identity and pins a retained snapshot; tools enforce ownership and field allowlists. Model arguments cannot select identity or version. Targeted tests cover ownership and pin changes. |
| Staff or model changing canonical data | Django session/CSRF and separate source permissions; author/revision-bound drafts; publication rechecks authorization. Model/customer paths are read-only. Tests cover permissions and stale drafts. |
| Private/internal policy exposure | Staff-reviewed public passages bound to PDF hash/revision; lookup filters public passages before ranking. Fixed-set tests do not prove all prose safe or all queries correct. |
| Malformed or unsupported model output | Validate tool/terminal shapes, bounds and selected numeric/product claims; reject malformed/truncated output. These finite guards do not prove arbitrary Portuguese prose truthful. |
| Stale or unsafe draft dispatch | Recheck takeover, source, authorization, deadline and service window before send. Tests exercise these races; they do not cover every schedule. |
| Duplicate/uncertain send or reordered callback | Persist before I/O; unknown sends are not resent automatically; callback IDs resolve within provider/recipient scope. Recovery tests cover selected transitions. |
| Contact data in model context/history | Minimize contact spans and retain only bounded accepted history after sender/source checks; re-minimize and requery facts. Structured preference/candidate replay is not implemented. |
| Dynamic callback destination | Restrict helper/callback targets to explicit loopback HTTP authorities; mock checks token and text shape. This is a local harness boundary, not deployment networking policy. |
| Cross-provider leakage or cloud routing | Ollama validates local/private endpoints and local model tags, rejects authenticated clients and redirects, and never uses the OpenRouter key. Mocked tests cover transport isolation; the live greeting does not qualify task quality. |
| Development credentials and storage | Local settings/fixtures are not deployment configuration. Deployment needs private secrets, HTTPS, hardened Django settings and protected storage. |

The model is not an authorization mechanism. Public retrieval is evidence, not proof of answer correctness; source allowlists and targeted output checks need separate quality evaluation. A malicious local filesystem administrator is outside this prototype boundary.

## Recovery evidence

Publication tests terminate a subprocess after bundle staging, inside activation before commit, and after commit. A fresh process checks the pointer, audit, retained hashes, policy provenance and price rows. Pre-commit termination preserves the old version; post-commit termination preserves the new one. This demonstrates process-crash behavior for the tested filesystem/SQLite configuration only, not power loss.

Customer recovery distinguishes pending, interrupted, accepted and unknown work; provider acceptance is not delivery. See [validation](validation.md) for run scope and remaining acceptance gaps.
