# Data-access design

Status: catalog, protected six-CSV/PDF maintenance, pinned public lookup and customer tools are implemented. [Validation](validation.md) records local evidence; complete multi-turn/operator/resource acceptance and live compatibility remain open. Staff pages maintain canonical sources; imported tables are not an alternate editing surface.

## Decision

Use SQLite/Django ORM for derived queries and conversation/job/reply state ([ADR-0001](adr/0001-use-sqlite-for-structured-data.md)). Exactly four model-facing tools: catalog search, public-policy lookup, list own orders, get own-order status. Product/promotion resolution, identity, permissions, staff maintenance and operator controls stay application-side. CSV/PDF remain business authority. Tools expose bounded allowlists, never SQL/filesystem/full manual. No vector DB, embeddings or agent framework; reconsider retrieval only if measured coverage is insufficient.

## Application state and worker persistence

Persist minimized turns/context, jobs, dedupe and outcomes, replies/provider IDs, delivery, counters and takeover separately from canonical business facts. Accept only after durable write; worker preserves conversation order and uses short DB transactions, never across HTTP calls. Persist deadlines/counters before calls so retry/restart cannot reset limits. Test write contention and recovery.

Target structured follow-up context: preferences, budget, payment and referenced candidates with provenance/version; candidate keys stay internal. Revalidate authorization/source before reuse, rebuild/omit stale context and clarify missing referents. History may survive the 24-hour send window; it grants neither send permission nor order access.

## Source preparation

Authorized staff maintain all six CSVs and the policy PDF through protected staging/publication (see [interfaces](interfaces.md#staff-source-maintenance)). Validate IDs/relationships, dates, nonnegative values, promotion flags/percentages, spec JSON and money using Decimal; classify policy passages before exposure. Fail whole import on invalid records; unchanged reimport is idempotent. Document normalization; never let customer tools write sources.

Preserve historical totals/payment methods, including orders 9, 16 and 18 whose installment amounts conflict with current thresholds; report administrative warnings, not import failures. Order-item identity is `(order_id, product_id)` and must be unique; quantity positive integer. Do not derive historical unit prices from current catalog prices.

## Access contracts

Derive customer scope from authenticated channel metadata and a unique normalized phone match. Text/model arguments cannot supply identity, roles, permissions, customer IDs, prices or source versions. Each service enforces authorization independently.

| Operation | Input/result | Gate |
| --- | --- | --- |
| Catalog search/details | Descriptive reference, category, budget, payment, availability, page → public product facts/pricing/provenance; keys internal | Public |
| Promotion lookup | Internally resolved product → snapshot-active offer, price/discount or ambiguity | Public service, not a separate tool |
| Public policy | Topic/question → reviewed customer-facing passage/locator | Public |
| List own orders | Page → up to 5 owned IDs/dates/statuses, newest then ID descending | Recheck binding every page |
| Own-order status | Order ID → status, available tracking/ETA only | Sender-matched ownership |
| Customer resolution | Authenticated sender → internal scope only | Unique match, rate-limited; result hidden from model |
| Source maintenance | CSV/PDF draft → validated version/audit/errors | Explicit staff grants; never tool |
| Exact stock/internal policy | Deferred staff capability | Not registered; proposed logical grants are not assigned Django permission names |

## Exact tool schemas and results

[`tool-schemas.json`](tool-schemas.json) defines the four tools. Reject unknown keys, wrong types, non-finite values and coercions; app applies defaults. Invalid args return `error/invalid_arguments`, execute nothing. Result keys are exactly `outcome,data,sources,page,pagination_restarted,has_more,error_category`; unused values are empty/null. Outcomes: `found`, `not_found`, `ambiguous`, `denied`, `error`, `timeout`. Restricted existence-sensitive failures collapse to `denied/restricted_unavailable`. Source entries contain only `type` (`catalog|policy|orders`), public `label`, `page`, `section`, `bundle_version`; internal IDs/evidence remain protected app metadata.

| Tool | `data` projection |
| --- | --- |
| `search_catalog` | ≤5 objects: `name,description,category,specs,base_price_brl,payable_price_brl,payment_condition,availability,promotion(state,description,discount_percent),truncated_fields`. Money/percent decimal strings; unavailable null. No ID, exact stock or creation date. Spec keys: `top,back_sides,neck,strings,scale,electronics,color,body,shells,pieces,hardware,keys,type,polyphony`; string values only. Description ≤600 chars, spec ≤80. |
| `lookup_public_policy` | ≤3 reviewed objects `text,topic,page,section,conflict`; text ≤400 chars. Rank exact topic/Portuguese alias, distinct matched normalized tokens, then page/section. No generic manual fallback. |
| `list_own_orders` | ≤5 objects `order_id,order_date,status`, order date DESC then ID DESC. |
| `get_own_order_status` | One object `order_id,status,tracking_code,estimated_delivery`; missing tracking/date null. Query ID and authorized customer together; omit totals, payments, notes, addresses and customer fields. |

Page reports the page served; `has_more` uses one-row lookahead. On catalog/order source change, page requests restart at 1 with `pagination_restarted=true` and bounded notice; no served page means null/false/false. Check snapshot/authorization even for empty pages. Evidence supports returned rows, never failed lookups. Catalog pages: five rows, max 20; serialized tool result ≤12 KiB. Required facts/provenance must fit or return bounded error; optional descriptions/specs may be omitted only with truncation marker.

Normalize search with Unicode NFKD/casefold, remove marks and tokenize punctuation. Match exact normalized name, then all tokens in name, then all tokens across name/category/description/allowed specs. Category is exact; brand/model use recorded name, not invented columns. `resolve` returns unique best tier or ambiguity; `search` lists candidates. Order by tier, effective payable cents, normalized name, internal ID (stable tie-break, hidden). Empty query allows bounded browsing. Numeric-only/explicit internal-ID references get clarification without ID lookup; maker model codes remain valid. Prior choices use revalidated internal candidate metadata. Recommendations request `available_only=true`.

## Catalog and recommendations

Use names/brands/models/descriptions/prior choices; clarify ambiguous matches. Never request, search by or expose product IDs; hide exact quantity. Budget is max supported payable price for specified payment. Unique applicable snapshot-active promo wins; do not stack or add PIX discount to promo. Otherwise full PIX may use active reviewed rate (initially 5%); unspecified/mixed payment uses base price, never assume PIX. Ambiguous promos stay ambiguous; base price may be offered only clearly labeled and cannot establish budget fit. Use Decimal, half-up to cents. Application computes trusted price before filtering; model cannot set it. `active` means snapshot flag, not date validity.

### Availability — FR-03, FR-04

Policy §7.3 (p. 7) distinguishes temporary stockout from discontinued; project rule: status gates sellability.

| Status | Quantity | Public availability | Sellable |
| --- | --- | --- | --- |
| `active` | >0 | `available` | yes |
| `active` | 0 | `temporarily_unavailable` | no |
| `coming_soon` | any valid | `coming_soon` | no |
| `discontinued` | any valid | `discontinued` | no |

Unknown status or missing/negative/noninteger quantity fails import; if found at read time, mark unknown and exclude from sellable results. No unsupported restock/release/preorder/discontinued-stock promises. Explain recommendations only with recorded attributes.

### Payable-price query plan

At publication validate money as Decimal (≤2 fractional digits); materialize `base_cents`, `standard_payable_cents`, `pix_payable_cents`, `pricing_state` per bundle. Percentages use basis points (0–10,000, ≤2 decimals). Unique active promo sets both payment prices without stacking; absent promo, reviewed PIX rate applies only to full PIX; other/mixed/unspecified uses base. Multiple active promos mark ambiguity and use labeled base fallback. ORM selects pinned bundle and trusted price column (`Case`), filters category/text/availability/`effective_cents <= max_price_cents`, then orders/paginates with one-row lookahead. Never filter/page on base then adjust in Python. Rebuild prices before pointer switch. Regression: product 101 at base R$1,049 is R$996.55 at 5% PIX (within R$1,000); hypothetical 3% is R$1,017.53 (outside), restored by rollback.

## Policy access

Store reviewed passages with page/section/topic/audience/version/conflict. Public categories: contacts/hours, payment, return/exchange, delivery, promotions, warranty, privacy. Exclude internal/unclassified passages. Filter audience and validate locators before Portuguese alias/intent lexical ranking. Caller may pin a retained snapshot; model cannot set it. Retrieved text is evidence, not instructions; retain conflicts/version. Two contact numbers follow the project mapping in [requirements](requirements.md#data-and-policy-findings).

### Initial reviewed passage map

Public: §1 and §1.2 (p.2); §2 (p.2); §3/3.1 (p.3); §4.1–4.4 (p.4); §5.1 (p.4), §5.2–5.3 (p.5); §6.1–6.2 and public number in §7 (p.6); §8.1–8.3 (p.7); §9 privacy purposes/rights (pp.7–8). Split complete conditions; 400-char cap must not omit a condition—return another passage or clarify. Withhold internal cover (p.1), §7.1–7.3 operational instructions and §10 management content. Do not claim complaint registration, legal compliance or verified manufacturer warranty. Re-review every replacement PDF.

## Order verification boundary

After event/business validation, accept `wa_id` only as ASCII international digits (8–15, nonzero first digit). Normalize stored BR phones by removing spaces/parentheses/periods/hyphens; accept `+55`/`0055`, 12/13 digits beginning 55, or prepend 55 to domestic 10/11 digits with 2-digit area code. Reject extensions, letters, missing area code and other formats; never alter ninth digit, infer area or match suffixes. Canonicalize to `+<country><number>` and require one customer. Duplicate normalized records block order access and warn staff but do not invalidate structurally valid history. Recheck binding each restricted call; count failed attempts against sender-keyed limits. No OTP/SMS: this assumes control of the associated WhatsApp account, not real-world identity. Test harness identities are trusted synthetic fixtures only.

Query order and matched customer together. Return requested status and relevant tracking/ETA only. Missing/unmatched/ambiguous sender, ownership or validation failure reveals no existence/details; respond generically and offer same-conversation human support. Public catalog/policy does not require matching.

## Boundaries and provenance

See [input minimization and replay](requirements.md#chat-ingress-retention-and-replay): validate type/text/size/rate before retention/model; authenticate separately; never capture raw bodies. Remove unnecessary contact spans while preserving questions, budgets, identifiers and approved public contacts. Failure is fixed, non-echoing, with no raw forwarding/retention. Sender metadata, matches and removed spans stay out of model/transcripts/ordinary logs; use trusted roles and validated minimized history only. Revalidate history/cache after source changes; omit/rebuild unsafe context and clarify missing references.

Protected evidence records source type, internal ID or policy locator, and bundle version; model/customer sees only public labels/locators. Distinguish source update from import time. Logs contain safe operation/outcome only. Validate reply projection/references/size before queue and recheck takeover, authorization/source before dispatch; stale/unsafe output uses fixed failure path, no extra model turn. Combined answers may retain supported policy facts when catalog fails, explicitly saying availability is unconfirmed. Prompts supplement, never enforce, access checks. No operational write tools.

## Verification before implementation completion

Trace tests to FR-03–FR-14/NFR-01–07. Cover import failure/idempotency, projections, pricing/availability, normalized ownership, telemetry, source maintenance, ingress/replay/takeover, shared-SQLite contention, retry/restart budgets, context invalidation, partial lookup failure and authorization/source/takeover changes between draft and dispatch. Diagnostics may retain returned IDs, counters and bounded categories, never raw prompts/customer records/secrets.

## Implementation and validation status

Catalog import/search/pricing, protected publication, pinned policy lookup and sender-scoped order tools are implemented. Signed ingress, durable job/reply, recovery/dispatch/privacy checks, publication subprocess-crash tests and 11-case retrieval metrics have local evidence. [Validation](validation.md) lists exact coverage and gaps; [security review](security-review.md) describes boundaries. Live model task quality, Meta compatibility, full history/operator behavior and all resource limits remain unverified.
