# Requirements — Empório da Música assistant

## Purpose and scope

Build a Python text customer-service assistant for the fictional Empório da Música. The [challenge brief](../desafio_tecnico_ai_eng_artefact.pdf) is authoritative for assignment scope; this document distinguishes project decisions and extensions.

Baseline: Django 5.2, SQLite/Django ORM, web process plus worker, Meta Cloud API transport, small Python tool loop and local stdio MCP tool server. `MODEL_PROVIDER` defaults to Cloudflare Workers AI; explicit values also support Ollama, OpenAI, Anthropic and the existing OpenRouter adapter. OpenAI and Anthropic, non-free OpenRouter routes and Cloudflare models outside the reviewed free-model list require `ALLOW_PAID_MODELS=true`; no provider failover is implicit. The customer-agent factory controls inference; the MCP server exposes application tools to a client-owned model. See [ADR-0004](adr/0004-free-model-and-provider-fallbacks.md) and [interfaces](interfaces.md). Run with `uv run --env-file .env`; plain Python does not load `.env`.

WhatsApp is the project channel (policy §7, p.6); the brief permits CLI/notebook/API/simple UI, so live Meta is not required for submission. Local path: CLI → signed webhook → validate/minimize/dedupe/persist/ack → worker → checked Meta-client send → mock → separate status webhook. Switching to Meta retains handler/parser/worker/client; live compatibility is unverified. See [interfaces](interfaces.md).

Status: source maintenance and local integration are implemented; retrieval, publication-crash and targeted security evidence exists. Full multi-turn/operator/resource acceptance, live Meta and generated-model quality remain unverified. See [validation](validation.md).

Delivery order is defined in the [README roadmap](../README.md#development-roadmap): qualify the actual customer agent, correct grounding/retrieval, demonstrate complete conversations, then close extension acceptance. Requirements below remain targets; their presence does not imply implementation or block the core behind optional infrastructure work.

## Agent execution

The business-tool registry contains exactly four callable operations: catalog search, public-policy lookup, list own orders and get own-order status. Only the direct Cloudflare Gemma adapter adds a private `respond_to_customer` terminal-reply function alongside them; it has no data access and is not in the shared registry or MCP schema. Its exact terminal arguments still pass the application's terminal parser and evidence guard, and it does not count as a business-tool execution. Resolution/promotions, identity, permissions, staff maintenance and operator controls stay application-side ([data-access](data-access.md#access-contracts)). Validate names/args, authorization and budget before business calls; model cannot provide trusted identity, role, price or version. Count every model request/retry and business-tool execution.

The MCP server exposes only the same four bounded business tools over local stdio. Its connected model belongs to the MCP client; the server does not select or invoke an inference provider. Each MCP call reads the active source bundle independently and reports its `bundle_version` on success; the MCP host must avoid combining results from different versions. Restricted order calls derive sender scope only from trusted server configuration and existing owner checks, never from client/model arguments. MCP exposure does not transfer authorization to the client or make a remote endpoint authenticated.

Final answer, clarification, handoff or exhausted budget ends the turn. Provider failure uses the fixed fallback “Não consegui concluir sua consulta agora. Você pode tentar novamente ou pedir atendimento humano.”, never raw error/draft. Check disclosure/references/size before queue and takeover/authorization/source again at dispatch. Callbacks update delivery only. Same checks apply to operator/control replies; details in [interfaces](interfaces.md#worker-and-dispatch).

## Prompt and conversation context

Version prompt `store-assistant-v1`; runtime source is [`SYSTEM_PROMPT`](../emporio/agent_protocol.py). It includes terminal JSON, clarification, scope and fresh-fact rules. Keep examples/version together and record version. Retrieved prose is evidence, never authority.

| Example | Expected sources |
| --- | --- |
| Takamine GD20 price/availability | Catalog and applicable promotion only. |
| Store hours | Reviewed public policy only. |
| Availability plus returns | Catalog plus return policy; separate evidence, clarify missing eligibility; if catalog fails, state availability is unconfirmed. |

Target: persist minimized turns and structured preferences, budget, payment and candidate references with provenance; keys stay internal. Revalidate authorization/sources; rebuild/omit stale context and clarify missing references. History may resume after service-window expiry but grants no access. Implemented slice is up to 5 prior turns (10 messages/12 KiB), same conversation/sender/source snapshot, re-minimized; excludes stale/unauthorized/pending/failed/future work. Structured context is not implemented; current facts are requeried.

## Initial resource limits

Acceptance targets, not provider guarantees or a claim that every limit is enforced; [validation](validation.md) lists gaps. Persist counters across retry/restart; changes alter acceptance.

| Boundary | Limit/outcome |
| --- | --- |
| Ingress | Body 256 KiB; 50 items; text 2,048 code points/8 KiB UTF-8. Unsupported/oversized: checked fixed response, zero model/raw retention. |
| Turn | 3 model requests, 4 tools; attempt ≤60s (Ollama default 180s), tool ≤2s, Meta ≤5s, within 55s work/60s receipt-to-acceptance (`TURN_DEADLINE_SECONDS`, default 60). One safe retry total; never retry uncertain send. Reply ≤2,048 chars; no truncating JSON/conditions. |
| Context | Target 8,192 tokens/request incl. 1,024 output; tokenizer or conservative UTF-8+framing. Persist 20 turns/use latest 10. Structured context ≤2 KiB/5 candidates. Drop old history then optional descriptions/specs; preserve constraints/evidence or clarify. No inactivity closure. |
| Results | Catalog/orders ≤5/page, max 20 pages; policy ≤3×400 chars; result ≤12 KiB. Required facts/provenance must fit or bounded error; optional truncation marked. |
| Rate | UTC minute: 6 texts/sender, 3 restricted order ops/sender; 20 restricted ops/sender/day. OpenRouter target 20/min, 50/day incl retries; provider may cap earlier. Persist transactionally. One fixed rate notice/sender/minute. |
| Queue | 5 unclaimed jobs/conversation, 100 global. Excess creates no job; durable rejection and one busy notice/sender/minute. Worker checks deadlines every 250ms; notification-only work is ingress-bounded/event-deduped and cannot reset budget. |
| Maintenance | CSV 2 MiB; PDF 10 MiB/20 pages/128 KiB extracted; bundle 32 MiB/10,000 rows/source; parse 5s, staging 30s. Full validation before activation; failures preserve active version. |

## Working assumptions

### Synthetic challenge data

Treat supplied datasets as synthetic per [README](../README.md#synthetic-data-assumption), absent contradictory evidence. This does not relax authorization, ownership or minimization; credentials/production data are excluded.

### Canonical data and freshness

Six CSVs and policy PDF are canonical, maintained by authorized staff through protected workflow. Derived data follows validated versions; DB-only edits cannot create business facts. Answers reflect active project data, not external live systems. Promotion `active` is snapshot state; no dates are supplied.

## Scope and scenarios

### Baseline

Handle contact/hours; product, price, availability, promotions and recommendations; customer policy; missing/conflicting/out-of-scope requests; instruction/access attacks; verified owned-order status.

### Required staff workflow and deferred extensions

Protected maintenance of all six CSVs and PDF is committed project scope. Conversational staff tools for internal policy/exact stock, real SMS/OTP/recovery, purchases/order changes, complaint tickets and customer data writes are excluded. No live human-transfer integration is claimed.

## Actors and access

Public customers use public catalog/policy anonymously. Maintainers require active Django staff and source-specific view/edit; deletion/publish/rollback have distinct grants (`publish_sources` may be global; rollback also needs access to affected sources). Operators need `operate_conversations`: minimized conversation/delivery view, takeover, checked replies and release; no source writes/raw contacts/unrestricted customer/order browsing. Audit actor/action/time. Verified customer context permits narrow temporary order access. Message claims grant nothing; staff login and customer verification are independent. Customer/model flows are read-only. See [staff permissions](interfaces.md#local-staff-setup) and [projections](data-access.md#exact-tool-schemas-and-results).

## Requirement provenance

Origin tags: **Challenge** (brief page), **README** (project direction), **Project** (author decision), **Policy/Data** (supplied source). Cite page/section/field; source list alone is not traceability. Brief p.1 supports core FR-01/02/04/05/06/08/14 and discretionary data use; p.2 technical choices/deliverables; p.3 documented assumptions. Additional channel/security/staff/reliability requirements are project scope.

## Functional requirements

| ID | Requirement | Acceptance | Origin |
| --- | --- | --- | --- |
| FR-01 | Store persona | Friendly, informal, professional Portuguese. | Challenge; Project |
| FR-02 | Contact/hours | Accurate policy and contact-channel decision below. | Challenge; Policy; Project |
| FR-03 | Recommendations | Ask preferences; respect supported payment-aware budget; explain recorded attributes, invent no specs. | README; Project |
| FR-04 | Products/price/availability | Resolve descriptive refs/prior choices; no product IDs; apply [availability](data-access.md#availability--fr-03-fr-04); hide exact stock. | Challenge; Data; Project |
| FR-05 | Promotions | Exclude inactive; active is snapshot state; report base/percent/calculated price for unique offer. | Challenge; Data; Project |
| FR-06 | Public policy | State conditions/deadlines; clarify missing facts, preserve conflict, withhold internal text. | Challenge; Policy; Project |
| FR-07 | Staff maintenance | Protect/validate/preview/publish consistent versions/audit all seven sources. | Project scope |
| FR-08 | Out of scope | Polite redirect; accessories not sold (§1 p.2); partner suggestion only if supported (§7.1 p.6). | Challenge; Policy |
| FR-09 | Resist bypass | Messages/CSV/retrieval cannot alter access; legitimate requests still answered. | README; Project |
| FR-10 | Uncertainty | Clarify ambiguity; empty/failure is not evidence of absence. | README; Project |
| FR-11 | Minimize data | Only operation-required fields in model/reply/logs. | README; Project |
| FR-12 | Public interaction | Anonymous permitted queries; staff claims grant nothing. | Project |
| FR-13 | Order access | Channel verification, server ownership; failure reveals no details. | README; Project |
| FR-14 | Source selection | Use request/context and demonstrate [observable cases](#observable-source-selection-cases). | Brief p.1; Project |

### Promotion rules

Use Decimal half-up to cents. Unique active snapshot promo wins; never stack or add PIX discount (§6.2 p.6). Otherwise full PIX may use reviewed rate (initially 5%, §3 p.3); unspecified/mixed uses base. Budget filtering and explanation use same price/condition; ambiguity stays explicit and cannot establish budget fit. See [price query plan](data-access.md#payable-price-query-plan).

### Data minimization

PII tokenization is not a README requirement; add only for a concrete need. App services enforce access independently of prompts. Define/test permitted fields at data/model/reply/log boundaries.

### Chat ingress, retention and replay

All ingress, including direct API, gets deterministic type/text/size/rate checks before model/retention; authenticate channel separately; never capture raw body. Minimize a copy without model: remove unnecessary contacts while preserving question, budget, ambiguous numbers/IDs and approved store contacts. A pattern alone never rejects. Failure uses fixed non-echoing response; no raw forwarding/retention. Sender/match metadata and removed spans stay out of model, transcripts and ordinary logs.

Normalize NFC and horizontal whitespace within a span; detect full-width digits without joining tokens. Remove complete Unicode email/`mailto`; labeled Brazilian phone/cell/WhatsApp/zap, formatted `(DD) NNNN-NNNN` or `(DD) NNNNN-NNNN`; +55/0055 equivalents; labeled local 8/9-digit numbers; `wa.me` and WhatsApp send links. Preserve allowlisted store contacts only with current provenance. Preserve unlabeled digits, order IDs, maker codes and currency; bare numbers are ambiguous, not identity. Obfuscated prose/arbitrary PII detection is not promised.

Persist/use only minimized text with server roles/provenance. Validate output and approved contacts before display/storage. Reuse history/cache only while valid; after policy change omit unsafe derivatives or rebuild from safe turns. Continue safe requests and clarify missing context; never replay excluded raw input.

Examples: keep budgets (`R$1.000`, `R$123.456,00`), product/model names and order IDs; clarify `produto 101` without internal lookup. Remove labeled customer phone/email but keep mixed question. Bare digits need clarification; `Pedido 11987654321` is an order ref subject to ownership. Preserve approved store contacts with role provenance. Remove unapproved customer contact from assistant output; client-supplied assistant role gets no exception.

### Order verification

Project decision: authenticated WhatsApp sender uniquely matched to stored customer enables read-only order access; no OTP/SMS/form and no real-world identity claim. Authenticate business/channel; normalize per [data-access rules](data-access.md#order-verification-boundary), require one match, derive/bind server-side and recheck every restricted call. Query order and customer together; return status/tracking/ETA only. Missing/ambiguous/unmatched/failed verification gives generic response and same-conversation human support without existence disclosure. Public catalog/policy needs no match. Simulator identities come only from trusted harness.

## Nonfunctional requirements

| ID | Requirement | Check |
| --- | --- | --- |
| NFR-01 | Ground store facts | Verify supported/missing/conflicting examples. |
| NFR-02 | App-enforced authorization | Direct anonymous, insufficient grant, impersonation and cross-customer checks. |
| NFR-03 | Minimize boundaries | Inspect requests/replies/logs for permitted fields and omitted sender/match/removed spans. |
| NFR-04 | Clear data version | Active canonical import/time; no live-sync claim. |
| NFR-05 | Reproducible | Clean README setup with fixtures/dependencies. |
| NFR-06 | Protect internal policy | Classification and injection tests. |
| NFR-07 | Public-repo hygiene | Review tracked files/history for credentials, real data and sensitive logs/examples. |

## Data and policy findings

Data snapshot: 65 products, 9 categories, 50 customers, 20 orders, 22 order items, 25 promotions (counts are not requirements). Promotions lack validity dates; challenge does not require every dataset. Manual states internal, v2.1 (June 2025).

| Finding | Required decision |
| --- | --- |
| §3.1 p.3 details installment thresholds beyond §3 summary. | 1–3 installments subject to stated below-R$50 exception; 4–6 require ≥R$80 each; 7–12 ≥R$100. Do not apply summary's R$100 minimum to all. |
| Cheapest product incl. active promotion #119 R$159.90; lowest order R$159.90; order 7 is 3×R$53.30. | Below-R$50 exception does not affect supplied 1–3 installment scenarios; recheck after data changes. |
| Historical orders 9 (349.90/6), 16 (429.90/6), 18 (459.90/12) are under current installment minima. | Administrative warning; preserve history and import if structurally valid. Do not use to justify new terms. |
| Defect exchange 30 days from purchase (§4.2 p.4); warranty 90 from receipt (§8.1 p.7). | State both and manufacturer/store-mediation-on-request route; clarify unspecified details. Difference alone is not conflict. |
| §7 p.6: (67) 3321-4500 remote WhatsApp; §1.2 p.2: (67) 3341-4444 company telephone/WhatsApp. | Use first for WhatsApp support, label both by source role; failed match routes to same-conversation human. Difference alone is not conflict. |
| §5.1 p.4: metro R$35 below R$500, free above; supplied values do not reach equality. | Current scenarios need no clarification; hypothetical R$500 fee is unspecified, ask store. Recheck after data changes. |

These are source interpretations, not legal conclusions.

## Acceptance coverage and traceability

Each case names requirement IDs, expected result and source evidence. Use deterministic checks for access, price and limits; score generated answers on facts/behavior, not identical wording. Passing supports only recorded coverage; see [validation](validation.md).

| Area | Minimum cases |
| --- | --- |
| Persona/hours (FR-01/02) | Correct Portuguese/contact roles; after-hours/fallback/handoff in `America/Campo_Grande`, Mon–Fri 09–18, Sat 09–13, closed Sundays/holidays (§2 p.2, §7.1 p.6). Test boundaries/holiday. Without reviewed calendar state regular hours and exception uncertainty; app adds notice if needed. |
| Channel/worker (FR-10/11/13; NFR-02/03) | Shared ingress/parser/worker/client; signed verification, senders, malformed/forged/batches/conflicts/duplicates, scoped replies, restart/interruption/delays, out-of-order status, rejected/unknown send, takeover/release. Ack after durable acceptance; callbacks cause zero model calls. Mock 24h and revalidated resumption. Live access unnecessary. |
| Budgets/dispatch (FR-08/10/14) | Queue-inclusive deadlines, 55/60s, operation timeouts, token/byte/page/rate bounds; restart/timeout/stale/unsafe produce fixed or durable operator notice, no unchecked draft/extra model call. |
| Prompt/context/races (FR-01/09/10/14) | Run three examples; retain constraints/candidates; clarify missing refs; malicious retrieval cannot change access. Change takeover/binding/ownership/source after draft; recheck before send. |
| Provider (FR-10; NFR-03/05) | Explicit provider/model/key isolation; paid OpenAI/Anthropic, non-free OpenRouter, and unreviewed Cloudflare models require `ALLOW_PAID_MODELS=true`; Cloudflare account/quota errors remain errors; no fallback; missing metadata unknown. Mocked wire compatibility is not live provider or answer-quality evidence. |
| Installments/products (FR-03–06) | 3/4 and 6/7 boundaries; 6×80 allowed, 7×80 denied; order 7; historical discrepancy warning. Availability states incl. products 136 discontinued/13, 130 coming-soon/2, 96 active/0; ambiguous/invalid. PIX nylon budget: #101 at 996.55 included, 996.54 excluded; card/unspecified excluded at 1,000. Promo not further PIX-discounted; payment changes re-filter. |
| Policy/delivery (FR-06; NFR-01/06) | Supported/missing/internal rules; exchange/warranty dates; 35 below/free above 500; hypothetical equality unspecified. |
| Source selection (FR-14) | [Observable cases](#observable-source-selection-cases), operation outcomes and source IDs/locators; include empty/errors and independently answer supported parts. |
| Maintenance/privacy/orders (FR-07/09/11–13; NFR-02/03/07) | Seven sources, removals, broken refs, stale drafts, pre/post-commit crash, rollback/pinned reader; 5%→3% PDF updates passage/prices/budget together; mismatch blocks. Independent grants, one handoff confirmation, persistent pause/release no replay. Direct API redaction, mixed questions, IDs/store contacts, size/rate/output failure and telemetry. Order normalization, duplicates, mismatch, changed sender, cross-customer denial, missing tracking, generic failure and synthetic boundary. |
| Scope/reproducibility (FR-08/10; NFR-04/05) | Accessories/out-of-scope, absent/conflicting sources, canonical version/time and clean README setup. |

For attacks, success is safe refusal/clarification. Evidence itself must obey minimization.

### Observable source-selection cases

Record consulted source types, outcomes and protected source IDs/locators; answer correctness alone is insufficient.

| Request | Expected behavior |
| --- | --- |
| Takamine GD20 price/availability | Catalog/promotion only. |
| Store hours | Public policy only. |
| Availability plus returns | Catalog and return policy; separate evidence, clarify eligibility. |
| Nylon ≤R$1,000, full PIX | Catalog/promotions and PIX/non-stacking policy (§3 p.3, §6.2 p.6); filter before rank; include #101 at R$996.55. |
| “E o mais barato?” after two recommendations | Resolve to candidates; preserve constraints/price; reuse relevant current evidence; no unnecessary policy lookup. |
| Same follow-up without candidates | Clarify before query/assertion. |
| Empty/error lookup | Record it; never infer absence or unavailability; answer supported parts and state unresolved facts. |

## Implementation readiness and evaluation

Automated evidence exists for source workflow/local integration; full context/operator/rate/resource acceptance remains. Unsupported policy semantics require compatibility before activation. Probe configured model for tool serialization, catalog/policy call and Portuguese terminal JSON; this tests integration, not quality. Historical OpenRouter probes: key diagnostic succeeded but 429 prevented capability result (2026-11-02); one authorized app request also received 429 before completion (2026-11-03). Neither proves incapability or persistent outage; see [probe](model-capability.md) and [evaluation](priority-evaluation.json). Five [scripted interactions](demo-interactions.json) show local source selection, not generated quality. Five [live recorded conversations](interactions.md) on local `qwen3.5:9b` gave grounded answers in 9 of 10 turns; they are development evidence, not an independent evaluation. When available, evaluate Portuguese answers, recommendations, injection, privacy, hours and failures with expected/actual evidence and model/provider/prompt. Live Meta testing is only needed for live-compatibility claim.

## Sources

- [Challenge brief](../desafio_tecnico_ai_eng_artefact.pdf); [README](../README.md); [policy manual](../data/políticas_da_loja.pdf)
- [Products](../data/desafio_tecnico_ai_eng%20-%20products.csv), [categories](../data/desafio_tecnico_ai_eng%20-%20categories.csv), [customers](../data/desafio_tecnico_ai_eng%20-%20customers.csv), [orders](../data/desafio_tecnico_ai_eng%20-%20orders.csv), [order items](../data/desafio_tecnico_ai_eng%20-%20order_items.csv), [promotions](../data/desafio_tecnico_ai_eng%20-%20promotions.csv)
