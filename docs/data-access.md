# Data-access design

Status: proposed design, pending review. No implementation or validation is claimed. This design follows [requirements](requirements.md); customer order verification is required, while contributor access remains optional.

## Decision

Use SQLite for CSV snapshots, Django ORM models and read-only services, as accepted in [ADR-0001](adr/0001-use-sqlite-for-structured-data.md). Policy lookup uses curated, classified sections; the model receives bounded, permitted results, never database, SQL, filesystem or full-manual access.

No vector database, embeddings or agent framework is required for this design. Revisit policy search if measured section coverage is insufficient.

## Source preparation

Import synthetic fixtures with a repeatable management command. Parse headers explicitly; validate required IDs, uniqueness, foreign keys, dates, nonnegative prices/stock, promotion percentages/flags and specification JSON. Use Decimal for money and explicit order-date formats, not locale inference. Preserve source IDs and snapshot provenance.

Report invalid records and fail the import transaction rather than silently skipping them or publishing partial data. Re-importing an unchanged fixture must not duplicate records. Imports are an administrative operation, unavailable to conversational tools. Document any normalization separately from source corrections.

Link products to categories, promotions to products, orders to customers, and items to orders and products. Validate order-item identity at import; do not assume an undocumented composite key or reconstruct historical totals from current prices, since no historical unit price is supplied.

## Access contracts

The server derives access context from the Django request and server-side verification state. Tool arguments cannot supply trusted roles, permissions or a verified customer ID. Every service enforces its own authorization, including calls made outside the user interface.

| Operation | Inputs | Permitted result | Gate |
| --- | --- | --- | --- |
| Search catalog | Text, category, maximum price, availability filter, bounded page | Product ID, name, description, selected specifications, category, recorded price and availability | Public |
| Product details | Product ID | Same public fields and applicable promotion result | Public |
| Promotion lookup | Product ID | Snapshot-active offer, original price, percentage, calculated price or explicit ambiguity | Public |
| Public policy lookup | Topic or question | Only classified customer-facing passages and source locators | Public |
| Stock lookup | Product ID | Exact recorded quantity and status | Contributor permission, if selected |
| Internal policy lookup | Topic or question | Passages classified for the assigned permission | Contributor permission, if selected |
| Request verification | Candidate order/customer locator | Generic acknowledgement; no existence confirmation | Public, rate limited |
| Submit verification | Code through a dedicated application flow | Success/failure and server-side session-bound verification state | Rate limited |
| Order status | Order ID | Status and relevant available tracking/estimated-delivery fields | Verified customer owns order |

Permission labels such as `view_exact_stock` and `view_internal_policy` are proposed logical capabilities; final Django permission names and assignment remain to be defined. Contributor authentication alone does not grant customer-order access.

Return structured outcomes (found, not found, ambiguous, unavailable, denied); map existence-revealing outcomes to one public failure response. Use explicit public-field allowlists, never full model serialization. Bound results and input lengths; set limits before implementation.

## Catalog and recommendations

Filter in the database, including budget. Clarify ambiguous names or return bounded candidates. Derive availability from validated stock and status; clarify unknown or contradictory status rules before implementation. Hide exact stock in public projections.

The model may explain candidates using recorded attributes, but cannot invent specifications or override filters. Apply budgets to base prices; use promotional prices only with a unique applicable offer and an explicit search-contract extension.

Promotion arithmetic uses Decimal and the requirements' half-up rounding. Do not stack promotions or apply the 5% PIX discount to promotional prices ([policy manual §6.2, p. 6](../data/políticas_da_loja.pdf#page=6)). Multiple applicable promotions remain ambiguous until precedence is established. An active flag is a snapshot fact, not a date-based validity check.

## Policy access

Store reviewed policy passages with page/section, topic, audience and conflict marker. Public lookup initially allows reviewed customer-facing contact, hours, payment, exchange/return, delivery, promotion and warranty passages; internal workflows and unclassified text are excluded.

Start with topic mapping and text search; filter by audience before ranking or model delivery. Keep conflicting passages with conflict markers; never choose silently, and return the manual version. Treat retrieved instructions as untrusted.

## Order verification boundary

Customer and order tables are accessible only through narrowly scoped services. Locate candidates without returning customer records to the model. Generate and validate codes outside the model, with expiry, single use, issuance/attempt limits and session binding. Choose numerical limits before implementation.

Deliver simulated SMS only through a separate development-only reviewer channel, associated with the stored synthetic phone number. Never return codes or full contact details in chat, model context or ordinary logs. Do not enable the simulator as production authentication. Its association with the customer is an explicit synthetic-fixture assumption.

Scope the order query to the server-verified customer and requested order ID in the same query. Return only requested status and relevant tracking/delivery fields, excluding notes, payment details, totals and customer contacts. Clear expired verification state. Unsupported or failed verification leads to a generic explanation and an approved store-contact route; unresolved contact conflicts must remain explicit.

## Boundaries and provenance

Return source type, record ID or policy locator, and snapshot marker. Distinguish known capture time from import time; import does not make data current. By default, logs include operation and safe outcome only, excluding raw messages, codes, customer records and sensitive tool arguments.

Model-facing tools call these services and receive only their permitted projections. Application checks apply before retrieval and before disclosure; prompts provide an additional behavioral instruction rather than the authorization mechanism. No operational write tools are included.

## Verification before implementation completion

Trace tests to FR-03–FR-13 and NFR-01–NFR-06 as applicable. Cover transactional import failure and repeatability; public field allowlists; budget and availability filtering; promotion rounding and ambiguity; public policy filtering before ranking; direct unauthorized service calls; spoofed context; session expiry, cross-customer order requests, non-enumerating failures and absent codes in model inputs/logs.

## Decisions to close

- Confirm whether contributor access is included.
- Review policy passage classification and exact source locators.
- Confirm source status vocabulary, promotion applicability and any normalization rules.
- Set query bounds, verification lifetimes and rate limits.
- Choose import update/replacement semantics and handling of records removed from later snapshots.
- Select the user-interface and model integration separately from these service contracts.
