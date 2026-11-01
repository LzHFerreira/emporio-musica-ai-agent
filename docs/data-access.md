# Data-access design

Status: proposed design, pending review. No implementation or validation is claimed. This design follows [requirements](requirements.md); customer order verification is required, while staff access remains optional.

## Decision

Use SQLite as a derived query store for canonical project CSVs, with Django ORM models and read-only conversational services, as accepted in [ADR-0001](adr/0001-use-sqlite-for-structured-data.md). The CSVs remain authoritative; database imports must not silently supersede or diverge from them. Policy lookup uses curated, classified sections; the model receives bounded, permitted results, never database, SQL, filesystem or full-manual access.

No vector database, embeddings or agent framework is required for this design. Revisit policy search if measured section coverage is insufficient.

## Source preparation

Import canonical project CSVs with a repeatable management command. Parse headers explicitly; validate required IDs, uniqueness, foreign keys, dates, nonnegative prices/stock, promotion percentages/flags and specification JSON. Use Decimal for money and explicit order-date formats, not locale inference. Preserve source IDs and source-file provenance. A future BU-facing interface, if time permits, must update the canonical source data through a validated workflow; it must not create database-only business facts.

Report invalid records and fail the import transaction rather than silently skipping them or publishing partial data. Re-importing an unchanged fixture must not duplicate records. Imports are an administrative operation, unavailable to conversational tools. Document any normalization separately from source corrections.

Historical installment-policy discrepancies ([orders 9, 16 and 18](requirements.md#data-and-policy-findings)) produce administrative warnings, not import failures when structural validation passes. Preserve their recorded totals and payment methods; do not recalculate them from current policy or use them to justify new installment offers. This does not expand model-facing order fields.

Link products to categories, promotions to products, orders to customers, and items to orders and products. Validate order-item identity at import; do not assume an undocumented composite key or reconstruct historical totals from current prices, since no historical unit price is supplied.

## Access contracts

The server derives access context from the Django request and server-side verification state. Tool arguments cannot supply trusted roles, permissions or a verified customer ID. Every service enforces its own authorization, including calls made outside the user interface.

| Operation | Inputs | Permitted result | Gate |
| --- | --- | --- | --- |
| Search catalog | Text, category, maximum price, optional requested payment method, availability filter, bounded page | Product ID, name, description, selected specifications, category, recorded base price, supported payable price, payment condition, pricing source locators and availability | Public |
| Product details | Product ID, optional requested payment method | Same public fields and applicable promotion result | Public |
| Promotion lookup | Product ID | Snapshot-active offer, original price, percentage, calculated price or explicit ambiguity | Public |
| Public policy lookup | Topic or question | Only classified customer-facing passages and source locators | Public |
| Stock lookup | Product ID | Exact recorded quantity and status | staff permission, if selected |
| Internal policy lookup | Topic or question | Passages classified for the assigned permission | staff permission, if selected |
| Request verification | Candidate order/customer locator | Generic acknowledgement; no existence confirmation | Public, rate limited |
| Submit verification | Code through a dedicated application flow | Success/failure and server-side session-bound verification state | Rate limited |
| Order status | Order ID | Status and relevant available tracking/estimated-delivery fields | Verified customer owns order |

Permission labels such as `view_exact_stock` and `view_internal_policy` are proposed logical capabilities; final Django permission names and assignment remain to be defined. staff authentication alone does not grant customer-order access.

Return structured outcomes (found, not found, ambiguous, unavailable, denied); map existence-revealing outcomes to one public failure response. Use explicit public-field allowlists, never full model serialization. Bound results and input lengths; set limits before implementation.

## Catalog and recommendations

Filter in the database, including budget and the availability table below. Clarify ambiguous names or return bounded candidates. Hide exact stock in public projections.

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

Store reviewed policy passages with page/section, topic, audience and conflict marker. Public lookup initially allows reviewed customer-facing contact, hours, payment, exchange/return, delivery, promotion and warranty passages; internal workflows and unclassified text are excluded.

Start with topic mapping and text search; filter by audience before ranking or model delivery. Apply the [documented policy interpretations](requirements.md#data-and-policy-findings); keep unresolved conflicting passages with conflict markers and return the manual version. The two listed store numbers follow the approved contact-channel mapping, without an automatic conflict marker. Treat retrieved instructions as untrusted.

## Order verification boundary

Customer and order tables are accessible only through narrowly scoped services. Locate candidates without returning customer records to the model. Generate and validate codes outside the model, with expiry, single use, issuance/attempt limits and session binding. Choose numerical limits before implementation.

Deliver simulated SMS only through a separate development-only reviewer channel, associated with the stored synthetic phone number. Never return codes or full contact details in chat, model context or ordinary logs. Do not enable the simulator as production authentication. Its association with the customer is an explicit synthetic-fixture assumption.

Scope the order query to the server-verified customer and requested order ID in the same query. Return only requested status and relevant tracking/delivery fields, excluding notes, payment details, totals and customer contacts. Clear expired verification state. Unsupported or failed verification leads to a generic explanation and the primary WhatsApp support route from the [contact-channel decision](requirements.md#data-and-policy-findings).

## Boundaries and provenance

The following ingress and replay rules are proposed and **to be re-evaluated before implementation**, together with their [requirements and acceptance cases](requirements.md#chat-ingress-retention-and-replay). Apply the contract independently of tool projections. Run its server-side gate before model-based routing or other model calls and before conversation retention; disable raw request-body capture across middleware, telemetry and errors. Reject matching code/contact messages with a fixed, non-echoing application response; gate failures block processing.

Keep verification-form values outside conversational tools and storage. If history is retained, record the ingress-policy version and revalidate before reuse; invalidate affected summaries and caches when source turns cannot pass the current gate. No history, retry or context-building path may bypass this check.

Return source type, record ID or policy locator, and source version or modification marker where available. Distinguish source update time from import time so users and operators can identify which canonical version backs an answer. By default, logs include operation and safe outcome only, excluding raw messages, codes, customer records and sensitive tool arguments.

Model-facing tools call these services and receive only their permitted projections. Application checks apply before retrieval and before disclosure; prompts provide an additional behavioral instruction rather than the authorization mechanism. No operational write tools are included.

## Verification before implementation completion

Trace tests to FR-03–FR-13 and NFR-01–NFR-06 as applicable. Cover transactional import failure and repeatability; public field allowlists; budget and availability filtering; promotion rounding and ambiguity; public policy filtering before ranking; direct unauthorized service calls; spoofed context; session expiry, cross-customer order requests, non-enumerating failures and absent codes in model inputs/logs.

## Decisions to close

- Confirm whether staff access is included.
- Review policy passage classification and exact source locators.
- Confirm promotion applicability and any normalization rules; product availability follows the table above.
- Set query bounds, verification lifetimes and rate limits.
- Define validated source-update and import/reconciliation semantics, including handling of records removed from canonical CSVs; assign BU ownership of source maintenance for any real-world deployment.
- Select the user-interface and model integration separately from these service contracts.
