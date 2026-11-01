# Requirements — Empório da Música assistant

## Purpose and scope

Build a Python text-based customer-service assistant for the fictional Empório da Música.

This document defines the working requirements, assumptions and acceptance criteria. The challenge brief remains authoritative for the original assignment. Project decisions and proposed extensions are identified separately.

Django is the selected framework, with SQLite accessed through the Django ORM ([ADR-0001](adr/0001-use-sqlite-for-structured-data.md)). The agent architecture, model and provider remain undecided.

**Status:** Requirements analysis. No behavioral validation has been completed.

## Working assumptions

### Synthetic challenge data

All supplied datasets are treated as synthetic fixtures under the [documented assumption](../README.md#synthetic-data-assumption); independent confirmation is not required for implementation, but contradictory evidence requires reassessment.

Synthetic fixtures do not remove the need to demonstrate application authorization, resource ownership and data minimization. Credentials and real production data remain outside this assumption.

### Canonical data and freshness

For this project, the supplied CSV files are the canonical sources for product, category, customer, order, order-item, and promotion data. The application database is a derived query store populated from those files; it must not become an independent authority. In a real-world scenario, the responsible business unit (BU) owns keeping the canonical CSVs current. If time permits, the project may engineer a BU-facing interface to review and update this information; otherwise updates remain outside the prototype workflow.

Answers must reflect the canonical project sources and may describe their values as current for the project data version in use. The prototype does not claim live synchronization with external operational systems. A promotion's active flag is authoritative for the project data version; no date-based validity is implied because the source contains no validity dates.

## Scope and scenarios

### Baseline

The assistant supports:

1. Contact information and opening-hours questions.
2. Product, price, availability and promotion questions.
3. Instrument recommendations based on customer needs and budget.
4. Customer-facing policy questions.
5. Missing, conflicting and out-of-scope information.
6. Attempts to override instructions or access restrictions.
7. Customer-specific order-status questions after simulated SMS verification.

### Proposed extensions

A protected staff interface for internal procedures and exact stock quantities remains an optional project extension. Its requirements below apply only if selected; it is not a challenge baseline requirement.

Real SMS delivery, production identity verification, account recovery, purchases, order changes, and direct conversational writes to stock or price are outside the prototype scope. A BU-facing source-maintenance interface is a possible time-permitting extension.

## Actors and access

- **Public client:** may access public store information, product prices and availability, recommendations and customer-facing policies without signing in.
- **staff, if implemented:** uses Django authentication and explicitly assigned permissions to access restricted operational information.
- **Verified customer context:** grants temporary, narrowly scoped access to orders belonging to the corresponding synthetic customer.

A role or identity claimed in a message grants no permission.

Django authentication for staff and simulated customer verification are separate mechanisms. Neither automatically grants the permissions of the other.

Before implementing restricted retrieval, define the permitted public fields, staff permissions and customer-facing policy sections. Until classified, internal content is withheld from public responses.

All supported operational access is read-only.

## Requirement provenance

Origin labels distinguish requirements from implementation choices:

- **Challenge:** attributed to the assignment in the current analysis.
- **README:** established project direction.
- **Project:** an author-defined interpretation or acceptance rule.
- **Policy/Data:** dependent on the supplied manual or CSV contents.

Challenge and policy claims require exact page, section or field references before the baseline is finalized. The source list alone does not establish requirement-level traceability.

## Functional requirements

| ID | Requirement | Acceptance criterion | Origin |
| --- | --- | --- | --- |
| FR-01 | Respond as the store persona. | Use friendly, informal, professional Portuguese appropriate to the request. | Challenge; Project |
| FR-02 | Answer contact and opening-hours questions from policy. | Report recorded hours accurately and apply the [contact-channel decision](#data-and-policy-findings). | Challenge; Policy; Project |
| FR-03 | Recommend instruments from customer needs and recorded attributes. | Ask for needed preferences; respect the budget using the supported payable price (unique applicable snapshot-active promotional price, otherwise recorded base price), identify the price used, explain supporting attributes and do not invent specifications. | README; Project |
| FR-04 | Report product prices and availability from matching records. | Apply the [availability table](data-access.md#availability--fr-03-fr-04): only `active` with positive stock is sellable; distinguish temporary stockouts, coming-soon and discontinued items. Suggest only supported available alternatives; public responses omit exact quantities. | Challenge; Data; Project |
| FR-05 | Report promotions within snapshot limits. | Exclude inactive offers; describe active flags as snapshot records, not proof of current validity. For a unique applicable offer, show recorded base price, discount percentage and calculated price. | Challenge; Data; Project |
| FR-06 | Answer customer-facing policy questions. | Give applicable conditions and deadlines; ask for missing facts, acknowledge material conflicts and withhold internal procedures. | Challenge; Policy; Project |
| FR-07 | Provide a protected staff interface only if selected. | Deny anonymous users; limit authenticated users to permitted information. Test internal procedures and exact stock quantities. | Proposed project extension |
| FR-08 | Handle out-of-scope requests. | Politely redirect accessory requests: per [policy §1, p. 2](../data/políticas_da_loja.pdf#page=2), accessories are not sold; per [§7.1, p. 6](../data/políticas_da_loja.pdf#page=6), suggest partner stores only when sources support it. Explain other out-of-scope requests politely. | Challenge; Policy |
| FR-09 | Resist instruction and access-control bypass. | Role claims or instructions in messages, CSV fields or retrieved documents cannot change permissions or expose protected data; legitimate permitted requests remain answerable. | README; Project |
| FR-10 | Handle missing, ambiguous or conflicting information. | Clarify when needed, state when sources are inconclusive and never invent store-specific facts. Empty or failed lookups cannot support factual claims about the requested data. | README; Project |
| FR-11 | Minimize customer information exposure. | Return only fields required for an authorized operation; omit unnecessary names, phone numbers, emails and unrelated order details from model inputs, responses and logs. | README; Project |
| FR-12 | Allow public customer interaction. | Anonymous users may ask permitted questions; claimed staff status grants no added access. | Project |
| FR-13 | Restrict order-status access through simulated verification. | Establish a verification context, check order ownership server-side and return permitted fields only. Failed, unavailable or ambiguous verification reveals no order details. | README; Project |
| FR-14 | Select operational data, policies or both using the current request and conversation context. | Demonstrate the source-selection cases below, preserving relevant constraints and clarifying unresolved references. | [Challenge, p. 1](../desafio_tecnico_ai_eng_artefact.pdf#page=1); Project |

### Promotion rules

For FR-05:

- Interpret `active` as a snapshot attribute, not proof of current validity.
- Calculate the promotional price as base price × (1 − discount percentage / 100), using decimal arithmetic and rounding half-up to two decimal places.
- Do not invent precedence rules for multiple promotions.
- For FR-03 budget filtering, treat a unique applicable snapshot-active promotional price as the supported payable price; when none exists, use the recorded base price. Apply the same amount in database filtering and the explanation. Do not claim an ambiguous promotion makes a product fit the budget.
- Do not stack promotions or apply the 5% PIX discount to promotional prices ([policy manual §6.2, p. 6](../data/políticas_da_loja.pdf#page=6)).
- If multiple records or conflicting rules prevent a unique calculation, report the ambiguity.

### Data minimization

PII tokenization is **not** a mandatory README requirement.

The prototype must define and test which fields may cross each boundary: data access, model input, user response and logs. Tokenization may be introduced if a concrete need justifies its additional complexity.

Access control must be enforced by application services and tools, independently of model instructions.

### Chat ingress, retention and replay

**Status: proposed; to be re-evaluated before implementation.** Review detection coverage, false positives and the effect of whole-message rejection on legitimate questions; the rules and acceptance cases below remain provisional.

Every chat submission, including direct API calls, must pass a deterministic server-side gate before any model call (including routing, classification or embeddings), conversation storage, cache, telemetry or request-body logging. The gate itself must not use a model or retain raw input.

Reject the entire message if it contains a verification-code candidate, phone-number or email pattern; do not extract or forward the remaining text. Return a fixed application response without echoing the input, directing verification details to the dedicated form and asking the user to resend the question without them. Chat input never submits or validates a code.

Before implementation, specify code formats, contact patterns and normalization, including Unicode digits and spacing/separator variants. Treat every matching code candidate as sensitive, regardless of issuance or expiry; ambiguous matches (including prices or order IDs) are rejected. Gate failure or unavailable validation blocks processing. Supported formats and tested normalization bound this protection; universal detection of arbitrarily encoded secrets is not claimed.

Rejected text must not enter transcripts, summaries, caches, analytics, traces, error reports or logs; only a safe rejection outcome may be retained. Verification forms process identifiers and codes outside conversation storage and model context, under the same logging exclusions.

If conversation retention is implemented, store only accepted turns with their ingress-policy version. Revalidate retained messages before replay, retries or context assembly; derived summaries and caches must use only revalidated inputs. Missing/stale validation, a rejected historical turn or gate failure blocks reuse until the affected content and its derivatives are discarded or safely rebuilt. Never replay raw rejected input.

## Order verification

### Intended flow

1. Locate a candidate customer or order without revealing whether it exists.
2. Generate a code associated server-side with the stored synthetic customer phone number.
3. Deliver the code through a separate development-only simulator.
4. Validate the submitted code and establish a customer verification context bound to the requesting session.
5. Check that the requested order’s `customer_id` matches the verified customer.
6. Return only the requested status and relevant available tracking or estimated-delivery information, identified as snapshot data.

A name, order date, order ID, email address or phone number supplied in chat is not proof of ownership. A conversation-supplied phone number must not replace the stored verification destination.

### Simulator boundary

The simulator demonstrates application behavior. It does not establish actual phone possession or real-world identity.

The reviewer obtains codes through a development-only test channel separate from the customer chat. Generated codes must not enter model context, ordinary application logs or customer-chat responses; pasted chat content follows the [ingress contract and its detection limits](#chat-ingress-retention-and-replay).

The simulator must be clearly labeled and excluded from any production authentication claim.

### Required properties

Codes must be unpredictable, single-use, expire and have issuance and verification-attempt limits. Verification state must remain server-side.

Before implementation, record the chosen code lifetime, attempt limits, issuance limits and verification-session lifetime as explicit configuration with acceptance tests.

Failed and ambiguous lookups must use responses that do not reveal whether a customer or order exists. Verification for one customer must not authorize another customer’s orders.

Failed or unavailable verification receives a generic failure response and a store-contact route without disclosing order details.

## Nonfunctional requirements

| ID | Requirement | Verification |
| --- | --- | --- |
| NFR-01 | Ground store-specific factual answers in supplied sources. | Compare representative answers with identified source records or policy sections, including missing and conflicting cases. |
| NFR-02 | Enforce authorization independently of the conversation. | Test application and tool access directly, including anonymous users, insufficient permissions, impersonation and cross-customer requests where applicable. |
| NFR-03 | Minimize data crossing system boundaries. | Inspect model requests, responses and logs against the permitted-field definitions. Verify that verification codes and unnecessary customer fields are absent. |
| NFR-04 | Represent data version clearly. | Treat project CSVs as canonical; answers reflect the imported canonical version and identify its update/import time where available. Do not claim live synchronization with external operational systems. |
| NFR-05 | Make the project reproducible and reviewable. | A reviewer can configure and run the completed application and tests using documented dependencies, fixtures and environment settings. |
| NFR-06 | Restrict internal policy disclosure. | Public retrieval and response paths expose only classified customer-facing policy information. Test internal-content requests and prompt-injection attempts. |
| NFR-07 | Preserve public-repository boundaries. | Review tracked files and history for credentials, real production records and unintended sensitive logs or examples. Synthetic challenge fixtures remain governed by the documented working assumption. |

## Data and policy findings

Inspection found 65 products, 9 categories, 50 customers, 20 orders, 22 order items and 25 promotions; these counts are not requirements and must be confirmed against implementation fixtures.

Product records include price, stock, status and specifications. Promotion records include a product reference, percentage and active flag, but no validity dates. The challenge does not require every dataset to be used.

The policy manual is reported as version 2.1, June 2025, and identifies itself as internal.

The following policy interpretations and unresolved questions require explicit handling:

| Finding | Required behavior |
| --- | --- |
| Project decision: [§3.1, p. 3](../data/políticas_da_loja.pdf#page=3) details §3's credit-card summary; their installment thresholds are not treated as a contradiction. | Apply §3.1's interest-free tiers: up to 3 installments subject to the stated below-R$50 exception; 4–6 installments require at least R$80 each; 7–12 require at least R$100 each. Do not apply the summary's R$100 minimum across all tiers. |
| The cheapest [product](../data/desafio_tecnico_ai_eng%20-%20products.csv), including snapshot-active promotions, is product 119 at R$159.90. The lowest [order total](../data/desafio_tecnico_ai_eng%20-%20orders.csv) is also R$159.90; order 7 records 3 installments of R$53.30. | The below-R$50 exception does not affect 1–3 installment answers for the supplied data and is not an implementation blocker. Do not request clarification for these supported amounts. Recheck this conclusion when canonical prices, promotions or order totals change. |
| Historical orders 9 (R$349.90 / 6), 16 (R$429.90 / 6) and 18 (R$459.90 / 12) have installment amounts below §3.1's respective R$80/R$100 minimums. | Report these fixture-policy discrepancies administratively; preserve recorded totals and payment methods and allow import when structural validation passes. Historical terms do not authorize equivalent new installment offers. Existing order-access and field restrictions still apply. |
| The [30-day defect-exchange period (§4.2, p. 4)](../data/políticas_da_loja.pdf#page=4) starts at purchase; the [90-day warranty (§8.1, p. 7)](../data/políticas_da_loja.pdf#page=7) starts at receipt. The unresolved question is how store mediation after the exchange window handles claims within the 90-day warranty. | Report both periods and §4.2's stated route: contact the manufacturer; store mediation is available on request. Seek store clarification for unspecified mediation details; the different periods alone do not establish a conflict or justify refusing supported guidance. |
| Project decision: [§7, p. 6](../data/políticas_da_loja.pdf#page=6) identifies (67) 3321-4500 as the primary remote-service WhatsApp channel; [§1.2, p. 2](../data/políticas_da_loja.pdf#page=2) lists (67) 3341-4444 as the company telephone/WhatsApp contact. | Use (67) 3321-4500 for WhatsApp support and store-contact fallbacks, including failed verification. Retain (67) 3341-4444 as the listed company telephone/WhatsApp contact. Label both by their source roles when explaining the difference; these numbers alone do not trigger conflict or refusal. |
| [§5.1, p. 4](../data/políticas_da_loja.pdf#page=4) specifies free metropolitan delivery above R$500 and R$35 below R$500; equality is a missing boundary rule, not a contradiction. None of the 20 recorded orders or product-price combinations reaches exactly R$500, including snapshot-active promotions and the permitted PIX discount. | Apply the stated fees to supported amounts; the missing equality rule does not block current data scenarios or require clarification for them. For an explicit hypothetical R$500 order, explain that the fee is unspecified and seek store clarification. Recheck reachability when canonical prices, promotions, discount rules or order totals change. |

These findings describe supplied policy text; they do not establish legal conclusions.

## Acceptance coverage and traceability

Each test or evaluation case must reference the requirement IDs it checks and identify its expected result.

| Coverage | Minimum cases |
| --- | --- |
| Persona and contact — FR-01, FR-02 | Portuguese response; recorded hours; primary WhatsApp support uses (67) 3321-4500; company telephone/WhatsApp listing retains (67) 3341-4444; explain both source roles when asked about the difference without treating it as an unresolved conflict. |
| Installments — FR-06 | Apply §3.1 at the 3/4 and 6/7 installment boundaries; permit R$480 in 6 installments of R$80; reject 7 installments of R$80; order 7 supports 3 installments of R$53.30 without clarification about the R$50 exception. |
| Historical installment discrepancies — FR-06, NFR-04 | Import orders 9, 16 and 18 unchanged with administrative discrepancy reporting; preserve structural validation; do not use historical payment terms to justify offers below §3.1's tier minimums or expand permitted order fields. |
| Recommendations and products — FR-03, FR-04 | Suitable recommendation; missing preferences; base-price budget constraint; snapshot-active promotional price within budget despite base price exceeding it; all availability-table combinations; products 136 (`discontinued`, 13), 130 (`coming_soon`, 2), 96 (`active`, 0); unknown/invalid availability inputs; ambiguous product name. Explanations identify the amount used for budget filtering. |
| Promotions — FR-05 | Inactive flag; snapshot-active flag; decimal calculation and rounding; conflicting promotions; no promotion stacking or PIX discount on promotional prices. Preserve ambiguity when multiple promotions apply. |
| Policies — FR-06, NFR-06 | Supported rule; missing facts; distinct 30-day exchange and 90-day warranty periods and start dates; stated post-exchange route with unspecified mediation details; no conflict or refusal based solely on those periods; attempted internal-procedure disclosure. |
| Metropolitan delivery — FR-06, NFR-01 | R$35 below R$500; free above R$500; current orders and supported product-price combinations avoid equality and require no boundary clarification. An explicit hypothetical R$500 order receives an unspecified-fee explanation and store-clarification route, without an invented charge or contradiction claim. |
| Source selection and context — FR-14, FR-10, NFR-01 | All [observable source-selection cases](#observable-source-selection-cases), checking consulted sources and lookup outcomes as well as answer correctness. |
| Public and staff access — FR-07, FR-12, NFR-02 | Anonymous public access; staff-interface denial; permitted staff; authenticated user without permission. staff cases apply only if selected. |
| Scope and uncertainty — FR-08, FR-10 | Unrelated request; accessory request handled per policy; absent information; conflicting sources. |
| Adversarial behavior — FR-09 | Role impersonation; instruction override; malicious retrieved content; legitimate request following a rejected attack. |
| Data boundaries — FR-11, NFR-03 | Permitted fields only in model inputs, responses and logs; no verification codes in those channels. |
| Chat ingress and replay — FR-11, FR-13, NFR-03 | Paste a code alone and within a legitimate question, phone and email patterns, Unicode/separator variants, expired/unissued code candidates and numeric false positives; repeat through direct API calls. Assert zero model calls and no raw retention or echoes on rejection. Inject gate failure; inspect request/error logs and telemetry. Recheck historical turns, summaries, caches and retries after a policy change or missing validation; prevent unsafe reuse. A clean question still succeeds. |
| Data version — NFR-04 | Answers reflect canonical CSV values; source/import timing is identified where available; no claim of live synchronization with external operational systems. |
| Order verification — FR-13 | Successful verification; different verified customer; invalid, expired and reused codes; issuance and attempt limits; session binding and expiry; failed or unavailable verification offers WhatsApp support at (67) 3321-4500 without order disclosure; ambiguous match; missing tracking data; non-enumerating failures. |
| Reproducibility — NFR-05 | Clean setup using the completed README and documented fixtures. |

For adversarial and unsupported requests, success means the expected refusal, clarification or safe handling—not completion of the requested attack.

Use deterministic tests for permissions, ownership, verification state and price calculations. Evaluate generated answers against source facts and explicit behavioral criteria rather than requiring identical wording.

Passing tests support claims only within their recorded coverage. No validation results are claimed at this stage.

### Observable source-selection cases

For each case, capture the consulted source types, operation outcomes and supporting record IDs or policy locators in the evaluation evidence, within the existing data-minimization rules. A correct answer alone does not establish correct source selection; internal model reasoning is not required.

| Case | Expected observable behavior |
| --- | --- |
| Catalog only: “Quanto custa o Takamine GD20 e ele está disponível?” | Consult matching catalog and applicable promotion records; do not consult policies. Ground price and public availability in returned records. |
| Policy only: “Qual é o horário de funcionamento?” | Consult customer-facing policy sections; do not query operational tables. Answer from the identified passage. |
| Both: “O Takamine GD20 está disponível e quais são as regras de devolução?” | Consult catalog records and customer-facing return policies. Support availability and return conditions with their respective sources; ask for missing eligibility facts. |
| Follow-up: after two supported recommendations, “E o mais barato?” | Resolve the comparison to those candidates, retain budget and preferences, and use supported payable prices under FR-03. Record the candidate IDs and operational evidence used, including any reuse from the prior turn; no policy lookup is needed. |
| Unresolved follow-up: “E o mais barato?” without identifiable candidates | Ask which products to compare before querying or asserting a price. Do not invent a referent. |
| Empty or failed lookup: repeat catalog-only, policy-only and combined requests with empty results and, separately, injected errors/timeouts for each required source | Evidence records the empty/error outcome. State that the affected facts cannot be confirmed; do not invent price, availability or policy, treat an error as absence, or turn missing availability evidence into “unavailable.” In combined requests, independently supported facts may still be answered with the unresolved part explicit. |

## Decisions still required

Before the relevant implementation begins:

- Confirm whether staff access is included in the prototype.
- Define public fields, staff permissions and policy-disclosure boundaries.
- Add exact source locators for challenge and policy claims.
- Choose verification limits and record them as configuration.
- Select and justify the agent, model and provider.

These decisions must remain consistent with the README.

## Sources

- [Challenge brief](../desafio_tecnico_ai_eng_artefact.pdf)
- [Project README](../README.md)
- [Store policy manual](../data/políticas_da_loja.pdf)
- [Products](../data/desafio_tecnico_ai_eng%20-%20products.csv)
- [Categories](../data/desafio_tecnico_ai_eng%20-%20categories.csv)
- [Customers](../data/desafio_tecnico_ai_eng%20-%20customers.csv)
- [Orders](../data/desafio_tecnico_ai_eng%20-%20orders.csv)
- [Order items](../data/desafio_tecnico_ai_eng%20-%20order_items.csv)
- [Promotions](../data/desafio_tecnico_ai_eng%20-%20promotions.csv)
