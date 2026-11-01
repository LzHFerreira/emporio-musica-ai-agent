# Data-access design

Status: requirements review in progress; step 1 is not complete and no behavioral validation is claimed. Customer events come from a trusted synthetic-sender harness; authenticated WhatsApp metadata below denotes the future contract and its simulated equivalent. Staff maintenance of all CSVs and the policy PDF through a protected web interface is required; Django integration remains under review.

## Decision

Use SQLite as a derived query store for canonical project CSVs with read-only conversational services; Django ORM integration is under review ([ADR-0001](adr/0001-use-sqlite-for-structured-data.md)). The CSVs remain authoritative; database imports must not silently supersede or diverge from them. Policy lookup uses curated, classified sections; the model receives bounded, permitted results, never database, SQL, filesystem or full-manual access.

No vector database, embeddings or agent framework is required for this design. Revisit policy search if measured section coverage is insufficient.

## Source preparation

A protected staff web interface must maintain all six canonical CSV datasets and the policy PDF. Validate IDs, relationships, explicit dates, nonnegative values, promotion flags/percentages and specification JSON; use Decimal and preserve source provenance. Validate/classify replacement policy content before public retrieval. Publish consistent source/query versions with safe failure recovery; customer tools cannot write business data.

Report invalid records and fail the import transaction rather than silently skipping them or publishing partial data. Re-importing an unchanged fixture must not duplicate records. Imports are an administrative operation, unavailable to conversational tools. Document any normalization separately from source corrections.

Historical installment-policy discrepancies ([orders 9, 16 and 18](requirements.md#data-and-policy-findings)) produce administrative warnings, not import failures when structural validation passes. Preserve their recorded totals and payment methods; do not recalculate them from current policy or use them to justify new installment offers. This does not expand model-facing order fields.

Link products to categories, promotions to products, orders to customers, and items to orders and products. Validate order-item identity at import; do not assume an undocumented composite key or reconstruct historical totals from current prices, since no historical unit price is supplied.

## Access contracts

The server derives customer context from authenticated transport sender metadata and a unique normalized phone match; message text and model output cannot establish or change that binding. Transport identity does not automatically establish customer-order ownership. Tool arguments cannot supply trusted roles, permissions or a verified customer ID. Every service enforces its own authorization, including calls made outside the user interface.

| Operation | Inputs | Permitted result | Gate |
| --- | --- | --- | --- |
| Search catalog | Name, brand, model, description, category, maximum price, optional payment method, availability filter, bounded page | Name, description, selected specifications, category, base/payable prices, payment condition, customer-facing source labels and availability; product keys stay in separate internal metadata | Public |
| Product details | Name/model or prior conversational choice resolved internally; optional payment method | Same customer-facing fields and applicable promotion result; no product ID | Public |
| Promotion lookup | Internally resolved product key; never a customer-supplied product ID | Snapshot-active offer, original price, percentage, calculated price or explicit ambiguity | Public |
| Public policy lookup | Topic or question | Only classified customer-facing passages and source locators | Public |
| Stock lookup | Product ID | Exact recorded quantity and status | staff permission, if selected |
| Internal policy lookup | Topic or question | Passages classified for the assigned permission | staff permission, if selected |
| Resolve customer context | Sender number from an authenticated channel event | Internal customer scope only; no customer record or match result to the model | Trusted adapter, unique normalized match, rate limited |
| List own orders | Bounded page; no caller-supplied customer ID | Owned order IDs, dates and statuses; five per page, newest first with ID tie-break | Rechecked sender/customer scope on every page |
| Maintain sources | Reviewed CSV record/file or PDF changes through protected staff web interface | Validated canonical version, matching derived snapshot, audit outcome or explicit errors | Authenticated staff with explicit maintenance permissions; never a conversational tool |
| Order status | Order ID | Status and relevant available tracking/estimated-delivery fields | Verified customer owns order |

Permission labels such as `view_exact_stock` and `view_internal_policy` are proposed logical capabilities; final Django permission names and assignment remain to be defined. staff authentication alone does not grant customer-order access.

Return structured outcomes (found, not found, ambiguous, unavailable, denied); map existence-revealing outcomes to one public failure response. Use explicit public-field allowlists, never full model serialization. Bound results and input lengths; set limits before implementation.

## Catalog and recommendations

Resolve customer references by name, brand, model, description or prior conversational choice; clarify ambiguous matches with descriptive candidates. Product IDs are internal keys for joins, tooling and technical evidence: never ask customers for them, interpret customer numbers as database IDs, or expose them in replies, transcripts or customer-facing source references. Use product names and source versions for public provenance. Filter budget/availability in the database and hide exact stock in public projections.

### Availability — FR-03, FR-04

[Policy §7.3, p. 7](../data/políticas_da_loja.pdf#page=7) distinguishes temporary stockouts from discontinued products, which leave the catalog. Project decision: status gates sellability; `coming_soon` is not yet available even with positive stock.

| Status | Valid quantity | Public outcome | Sellable |
| --- | --- | --- | --- |
| active | > 0 | available | Yes |
| active | 0 | temporarily_unavailable | No |
| coming_soon | > 0 or 0 | coming_soon | No |
| discontinued | > 0 or 0 | discontinued | No |

Unknown/missing statuses and missing, negative or noninteger quantities fail import validation. If encountered at read time, return availability unknown and exclude the item from sellable results; never infer availability from quantity alone.

Only `available` items qualify for an available-only filter or an available recommendation/alternative. Explain temporary unavailability for active stockouts, upcoming availability for `coming_soon`, and catalog removal for discontinued items. Do not promise restock/release dates, preorders or discontinued-stock sales without source support.

The model may explain candidates using recorded attributes, but cannot invent specifications or override filters. A budget means the maximum supported payable price for the requested payment method. Use a unique applicable snapshot-active promotional price; if no applicable promotion exists and payment is fully by PIX, use base price × 0.95 ([policy §3, p. 3](../data/políticas_da_loja.pdf#page=3)); otherwise use the recorded base price. Do not assume PIX when payment is unspecified. Filter on that amount before ranking and return it with its payment condition and pricing sources. If multiple promotions make the payable price ambiguous, report the ambiguity or use the base price only when clearly labeled as such, without a PIX discount; do not claim an ambiguous discount makes the product fit.

Promotion and PIX arithmetic use Decimal and the requirements' half-up rounding to two decimal places. Application services enforce these rules before budget filtering; the model cannot supply a trusted discount or payable price. Do not stack promotions or apply the 5% PIX discount to promotional prices ([policy manual §6.2, p. 6](../data/políticas_da_loja.pdf#page=6)). Multiple applicable promotions remain ambiguous until precedence is established. An active flag is a snapshot fact, not a date-based validity check.

## Policy access

Store reviewed policy passages with page/section, topic, audience and conflict marker. Public lookup allows customer-facing contact, hours, payment, exchange/return, delivery, promotion, warranty and privacy passages. Internal workflows and unclassified text are excluded.

Start with topic mapping and text search; filter by audience before ranking or model delivery. Apply the [documented policy interpretations](requirements.md#data-and-policy-findings); keep unresolved conflicting passages with conflict markers and return the manual version. The two listed store numbers follow the approved contact-channel mapping, without an automatic conflict marker. Treat retrieved instructions as untrusted.

## Order verification boundary

Customer and order tables are accessible only through narrowly scoped services. Validate event authenticity and business/channel context, normalize the transport sender number and stored phones using explicit country rules, and require exactly one matching customer. Derive the customer scope server-side and recheck the match for every restricted request; message text, profile names and tool arguments cannot override it.

No SMS challenge, OTP or verification form is used. This read-only prototype accepts control of the WhatsApp account associated with the recorded number, not proof of real-world identity. Missing, unavailable, unmatched or ambiguous sender numbers grant no customer access. A simulator supplies synthetic sender identities only through a trusted test harness and makes no live authentication claim.

Scope the order query to the sender-matched customer and requested order ID in the same query. Return only requested status and relevant tracking/delivery fields, excluding notes, payment details, totals and customer contacts. Failed matching, ownership or validation reveals no customer/order existence or details; give a generic explanation and offer human support in the same conversation. Public catalog/policy access does not require a customer match.

## Boundaries and provenance

Follow the accepted [input-minimization and replay contract](requirements.md#chat-ingress-retention-and-replay), independently of tool projections. Validate supported message types, text, size and rate limits before model calls or retention; disable raw request-body capture. Remove clearly unnecessary personal-contact spans while preserving questions, budgets, ambiguous numeric identifiers and approved public store contacts. A contact pattern alone never rejects a message. On validation or minimization failure, use a fixed, non-echoing fallback without forwarding or retaining raw input.

Keep transport sender metadata, customer-matching details and removed personal-contact spans outside model context, transcripts and ordinary logs. Retain only minimized turns with trusted roles, provenance and policy versions. Validate output against permitted projections and approved public store contacts. Reuse only currently validated history and derivatives; omit unsafe content or rebuild it from safe turns, continuing supported new requests and clarifying missing context when needed. No history, retry or context-building path may bypass these checks or trust a client-supplied assistant role.

Return source type, record ID or policy locator, and source version or modification marker where available. Distinguish source update time from import time so users and operators can identify which canonical version backs an answer. By default, logs include operation and safe outcome only, excluding raw messages, sender numbers, customer records and sensitive tool arguments.

Model-facing tools call these services and receive only their permitted projections. Application checks apply before retrieval and before disclosure; prompts provide an additional behavioral instruction rather than the authorization mechanism. No operational write tools are included.

## Verification before implementation completion

Trace tests to FR-03–FR-14 and NFR-01–NFR-07 as applicable. Cover import failure/repeatability, permitted projections, pricing/availability, scoped customer matching/ownership and safe telemetry. Exercise required staff source maintenance and customer CLI event/replay/takeover behavior against the [interface contracts](interfaces.md).

## Decisions to close

- Review policy passage classification and exact source locators.
- Confirm promotion applicability and any normalization rules; product availability follows the table above.
- Set query bounds, sender-number normalization, customer binding and order-access rate limits.
- Define validated source-update and import/reconciliation semantics, including handling of records removed from canonical CSVs; assign BU ownership of source maintenance for any real-world deployment.
- Implement the [local message/event contracts](interfaces.md#message-and-delivery-contracts); select backend/model integration and pin reviewed representative fixtures. Live WhatsApp adapter validation remains future scope.
