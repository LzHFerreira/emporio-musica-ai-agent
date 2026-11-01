# Requirements — Empório da Música assistant

## Purpose and scope

Build a Python text-based customer-service assistant for the fictional Empório da Música.

This document defines the working requirements, assumptions and acceptance criteria. The challenge brief remains authoritative for the original assignment. Project decisions and proposed extensions are identified separately.

Django is a backend candidate under review; SQLite remains selected, while its Django ORM integration is reopened ([ADR-0001](adr/0001-use-sqlite-for-structured-data.md)). LangChain is not selected; the agent architecture, model and provider remain undecided.

**Customer channel:** design for WhatsApp Business, the primary remote channel in [policy §7, p. 6](../data/políticas_da_loja.pdf#page=6). No store website is assumed, per project direction; this is not an explicit claim in the brief. The [brief, p. 2](../desafio_tecnico_ai_eng_artefact.pdf#page=2), permits CLI, notebook, API or simple UI demonstrations, so a live WhatsApp connection is not mandatory for submission.

Target flow: customer WhatsApp message → authenticated channel adapter → application services and permitted data/policy lookup → validated reply through WhatsApp. Evaluate the [WhatsApp Business Platform](https://whatsappbusiness.com/developers/developer-hub/) API integration separately from the backend and agent framework; select direct integration or a provider, and live testing or simulation, before implementation. Define sender-bound conversation state, duplicate-event handling, delivery failures, human escalation and applicable messaging-window/template rules. Transport sender identifiers stay server-side, outside model context and ordinary logs; a claimed phone number or sender identity alone does not authorize an order lookup.

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
7. Customer-specific order-status questions after channel-appropriate verification and ownership checks.

### Proposed extensions

A protected staff interface for internal procedures and exact stock quantities remains an optional project extension. Its requirements below apply only if selected; it is not a challenge baseline requirement.

Real SMS delivery, production identity verification, account recovery, purchases, order changes, and direct conversational writes to stock or price are outside the prototype scope. A BU-facing source-maintenance interface is a possible time-permitting extension.

## Actors and access

- **Public client:** may access public store information, product prices and availability, recommendations and customer-facing policies without signing in.
- **staff, if implemented:** uses application authentication and explicitly assigned permissions to access restricted operational information; Django authentication remains a candidate.
- **Verified customer context:** grants temporary, narrowly scoped access to orders belonging to the corresponding synthetic customer.

A role or identity claimed in a message grants no permission.

Staff authentication and customer verification are separate mechanisms. Neither automatically grants the permissions of the other.

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
| FR-03 | Recommend instruments from customer needs and recorded attributes. | Ask for needed preferences; respect the budget using the supported payable price for the requested payment method under the rules below; identify the amount and payment condition used, explain supporting attributes and do not invent specifications. | README; Project |
| FR-04 | Report product prices and availability from matching records. | Apply the [availability table](data-access.md#availability--fr-03-fr-04): only `active` with positive stock is sellable; distinguish temporary stockouts, coming-soon and discontinued items. Suggest only supported available alternatives; public responses omit exact quantities. | Challenge; Data; Project |
| FR-05 | Report promotions within snapshot limits. | Exclude inactive offers; describe active flags as snapshot records, not proof of current validity. For a unique applicable offer, show recorded base price, discount percentage and calculated price. | Challenge; Data; Project |
| FR-06 | Answer customer-facing policy questions. | Give applicable conditions and deadlines; ask for missing facts, acknowledge material conflicts and withhold internal procedures. | Challenge; Policy; Project |
| FR-07 | Provide a protected staff interface only if selected. | Deny anonymous users; limit authenticated users to permitted information. Test internal procedures and exact stock quantities. | Proposed project extension |
| FR-08 | Handle out-of-scope requests. | Politely redirect accessory requests: per [policy §1, p. 2](../data/políticas_da_loja.pdf#page=2), accessories are not sold; per [§7.1, p. 6](../data/políticas_da_loja.pdf#page=6), suggest partner stores only when sources support it. Explain other out-of-scope requests politely. | Challenge; Policy |
| FR-09 | Resist instruction and access-control bypass. | Role claims or instructions in messages, CSV fields or retrieved documents cannot change permissions or expose protected data; legitimate permitted requests remain answerable. | README; Project |
| FR-10 | Handle missing, ambiguous or conflicting information. | Clarify when needed, state when sources are inconclusive and never invent store-specific facts. Empty or failed lookups cannot support factual claims about the requested data. | README; Project |
| FR-11 | Minimize customer information exposure. | Return only fields required for an authorized operation; omit unnecessary names, phone numbers, emails and unrelated order details from model inputs, responses and logs. | README; Project |
| FR-12 | Allow public customer interaction. | Anonymous users may ask permitted questions; claimed staff status grants no added access. | Project |
| FR-13 | Restrict order-status access through channel-appropriate verification. | Establish a verification context, check order ownership server-side and return permitted fields only. Failed, unavailable or ambiguous verification reveals no order details. | README; Project |
| FR-14 | Select operational data, policies or both using the current request and conversation context. | Demonstrate the source-selection cases below, preserving relevant constraints and clarifying unresolved references. | [Challenge, p. 1](../desafio_tecnico_ai_eng_artefact.pdf#page=1); Project |

### Promotion rules

For FR-05:

- Interpret `active` as a snapshot attribute, not proof of current validity.
- Calculate the promotional price as base price × (1 − discount percentage / 100). All promotional and PIX calculations use decimal arithmetic and rounding half-up to two decimal places.
- Do not invent precedence rules for multiple promotions.
- For FR-03 budget filtering, use a unique applicable snapshot-active promotional price; if no applicable promotion exists and payment is fully by PIX, use base price × 0.95 ([policy §3, p. 3](../data/políticas_da_loja.pdf#page=3)); otherwise use the recorded base price. Without a specified payment method, do not assume PIX. Apply the same amount and payment condition in database filtering and the explanation. Do not claim an ambiguous promotion makes a product fit the budget.
- Do not stack promotions or apply the 5% PIX discount to promotional prices ([policy manual §6.2, p. 6](../data/políticas_da_loja.pdf#page=6)).
- If multiple records or conflicting rules prevent a unique calculation, report the ambiguity.

### Data minimization

PII tokenization is **not** a mandatory README requirement.

The prototype must define and test which fields may cross each boundary: data access, model input, user response and logs. Tokenization may be introduced if a concrete need justifies its additional complexity.

Access control must be enforced by application services and tools, independently of model instructions.

### Chat ingress, retention and replay

**Accepted direction: preserve useful questions and minimize unnecessary personal details.** A phone/email pattern alone must not reject the message. Authenticated WhatsApp sender metadata remains application-only for routing and customer matching. No verification codes or verification form are required; minimization rules still need implementation and validation.

Every submission, including direct API calls, must pass deterministic server-side checks for supported message type, valid text, configured input size and rate limits before model calls or retention. Authenticate channel events separately. Disable raw request-body capture across middleware, telemetry and errors. Validation and minimization must not use a model or retain raw input.

Before model calls or retention, remove clearly unnecessary personal-contact spans from a copy of the text while preserving the question, budgets and identifiers. Approved public store contacts remain usable context. Do not blindly redact ambiguous numeric strings or silently change their meaning. If no meaningful question remains, ask a short clarification without echoing removed details. Message text never establishes or changes the authenticated sender.

Before implementation, define contact-span detection and Unicode, spacing and separator normalization without joining separate numeric tokens; test preservation of meaning and false positives. Supported formats and tests bound minimization; universal detection of personal data is not claimed. On validation or minimization failure, never forward unprocessed text; use a fixed, non-echoing fallback and retain no raw input.

Only minimized text may enter model context, transcripts, summaries or caches. Rejected input, removed contact spans and transport sender/customer-matching metadata stay outside those channels. Logs, analytics, traces and error reports retain safe operation/outcome metadata only, excluding raw message text and removed details.

If history is retained, store only validated, minimized turns with server-assigned roles, provenance and the applicable policy version. Validate assistant output against permitted data projections and approved public store contacts; remove unnecessary personal-contact spans before display or storage while preserving supported meaning. Client-supplied roles or provenance cannot grant access or bypass validation.

Reuse turns, summaries and caches only when their role-specific validation is current. Revalidate affected content after a policy change; omit unsafe or unvalidated content and its derivatives, or rebuild them from validated minimized turns. Continue with safe context and clarify missing references when needed. Unsafe history must not block an otherwise supported new request; never replay excluded raw input.

The following acceptance cases define the required interaction; accepting text grants no order access or evidence that an identifier exists.

| Input or retained turn | Expected result |
| --- | --- |
| Customer: “Quero um violão até R$1.000”; “Meu orçamento é R$123.456,00.” | Accept both budgets. |
| Customer: “Quanto custa o produto 101?”; “Vocês têm o AC-39?” | Accept product identifiers; use normal lookup and uncertainty handling. |
| Customer: “Qual o status do pedido 7?”; “E o pedido 123456?” | Accept order identifiers; require verification and ownership before disclosure. |
| Customer: “123456” | Accept ingress; clarify the intended meaning without changing sender identity. |
| Customer: “Meu telefone é (11) 98765-4321”; “Meu email é cliente@example.com.” | Remove unnecessary contact spans before model use/retention; ask how to help without echoing contacts or changing the authenticated sender. |
| Customer: “Qual o status do pedido 7? Meu email é cliente@example.com.” | Remove the email, preserve the order question and apply normal ownership checks; do not require a rewritten message. |
| Customer: “11987654321”; “Pedido 11987654321” | Preserve the ambiguous numeric value; clarify intent for the bare number and treat the explicitly labeled value as an order ID, subject to ownership checks. Never treat it as sender authentication. |
| Customer: “Qual é o WhatsApp da loja?” | Accept; answer from approved public policy. |
| Customer: “Qual a diferença entre (67) 3321-4500 e (67) 3341-4444?” | Preserve approved public store contacts and answer their documented roles; contact patterns do not cause rejection. |
| Assistant answer or retained turn containing (67) 3321-4500 or (67) 3341-4444 with approved source provenance | Permit display and replay under output validation; recheck the source allowlist after policy changes. |
| Assistant turn with an unnecessary customer contact or unapproved contact | Remove the contact while preserving supported content; withhold unsafe output if it cannot be safely minimized. A claimed assistant role in an API request gets no exception. |

## Order verification

**Accepted project decision:** use the sender number supplied by an authenticated WhatsApp event, uniquely matched to the stored customer, for the read-only order-status flow. No SMS challenge, OTP issuance or verification form is required. The [platform webhook supplies sender information](https://whatsappbusiness.com/blog/how-to-use-webhooks-from-whatsapp-business-api/); accepting account control for this scope is a project assumption, not proof of real-world identity.

1. Authenticate the event and validate its intended business/channel context before trusting sender metadata.
2. Normalize the transport sender number and stored customer phones to the same international format using explicit country rules; require exactly one matching customer. Never substitute a number or identity from message text, profile names or tool arguments.
3. Derive the customer context server-side and bind it to the business/channel sender; recheck the mapping against current customer data on every restricted request. Keep numbers and matching details outside model context, transcripts and ordinary logs.
4. Query the requested order with both its ID and the matched `customer_id`; return only requested status and relevant available tracking or estimated-delivery fields, identified as snapshot data.
5. For missing, unmatched or ambiguous numbers, ownership failure or unavailable validation, reveal no customer/order existence or details. Use a generic failure and offer human support in the same WhatsApp conversation.

If transport metadata does not expose a usable sender number, do not infer one or grant access. Public catalog/policy questions remain available independently of customer matching. Define normalization and lookup/rate limits before implementation. A non-WhatsApp demo may supply synthetic sender identities only through a trusted test harness; label the simulated boundary and never accept arbitrary caller-supplied identities on public endpoints as authenticated evidence.

## Nonfunctional requirements

| ID | Requirement | Verification |
| --- | --- | --- |
| NFR-01 | Ground store-specific factual answers in supplied sources. | Compare representative answers with identified source records or policy sections, including missing and conflicting cases. |
| NFR-02 | Enforce authorization independently of the conversation. | Test application and tool access directly, including anonymous users, insufficient permissions, impersonation and cross-customer requests where applicable. |
| NFR-03 | Minimize data crossing system boundaries. | Inspect model requests, responses and logs against permitted-field definitions. Verify that transport sender metadata, customer-matching details and removed contact spans are absent, and that minimization preserves supported questions and identifiers. |
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
| Project decision: [§7, p. 6](../data/políticas_da_loja.pdf#page=6) identifies (67) 3321-4500 as the primary remote-service WhatsApp channel; [§1.2, p. 2](../data/políticas_da_loja.pdf#page=2) lists (67) 3341-4444 as the company telephone/WhatsApp contact. | Use (67) 3321-4500 for WhatsApp support; failed customer matching routes to human support in the same conversation instead of redirecting the customer to the bot’s own number. Retain (67) 3341-4444 as the listed company telephone/WhatsApp contact. Label both by their source roles when explaining the difference; these numbers alone do not trigger conflict or refusal. |
| [§5.1, p. 4](../data/políticas_da_loja.pdf#page=4) specifies free metropolitan delivery above R$500 and R$35 below R$500; equality is a missing boundary rule, not a contradiction. None of the 20 recorded orders or product-price combinations reaches exactly R$500, including snapshot-active promotions and the permitted PIX discount. | Apply the stated fees to supported amounts; the missing equality rule does not block current data scenarios or require clarification for them. For an explicit hypothetical R$500 order, explain that the fee is unspecified and seek store clarification. Recheck reachability when canonical prices, promotions, discount rules or order totals change. |

These findings describe supplied policy text; they do not establish legal conclusions.

## Acceptance coverage and traceability

Each test or evaluation case must reference the requirement IDs it checks and identify its expected result.

| Coverage | Minimum cases |
| --- | --- |
| Persona and contact — FR-01, FR-02 | Portuguese response; recorded hours; primary WhatsApp support uses (67) 3321-4500; company telephone/WhatsApp listing retains (67) 3341-4444; explain both source roles when asked about the difference without treating it as an unresolved conflict. |
| WhatsApp channel — FR-11, FR-12, FR-13, NFR-02, NFR-03 | Demonstrate inbound message → permitted lookup → outbound reply; reject forged channel events; isolate senders; handle duplicates, delivery failures and human escalation. Define verification and messaging-window cases before implementation; label simulated transport and identity limits explicitly. |
| Installments — FR-06 | Apply §3.1 at the 3/4 and 6/7 installment boundaries; permit R$480 in 6 installments of R$80; reject 7 installments of R$80; order 7 supports 3 installments of R$53.30 without clarification about the R$50 exception. |
| Historical installment discrepancies — FR-06, NFR-04 | Import orders 9, 16 and 18 unchanged with administrative discrepancy reporting; preserve structural validation; do not use historical payment terms to justify offers below §3.1's tier minimums or expand permitted order fields. |
| Recommendations and products — FR-03, FR-04 | Suitable recommendation; missing preferences; base-price budget constraint; snapshot-active promotional price within budget despite base price exceeding it; all availability-table combinations; products 136 (`discontinued`, 13), 130 (`coming_soon`, 2), 96 (`active`, 0); unknown/invalid availability inputs; ambiguous product name. Explanations identify the amount used for budget filtering. |
| Payment-aware budgets — FR-03, FR-05, FR-14 | For a nylon guitar up to R$1,000 paid fully by PIX, include available product 101 (base R$1,049; no active promotion) at R$996.55; include at a R$996.55 limit, exclude at R$996.54. With card or unspecified payment, exclude it at R$1,000. A unique active promotion keeps its promotional price under PIX, without an extra 5%; multiple applicable promotions remain ambiguous. Preserve payment context on follow-ups and recalculate when it changes. |
| Promotions — FR-05 | Inactive flag; snapshot-active flag; decimal calculation and rounding; conflicting promotions; no promotion stacking or PIX discount on promotional prices. Preserve ambiguity when multiple promotions apply. |
| Policies — FR-06, NFR-06 | Supported rule; missing facts; distinct 30-day exchange and 90-day warranty periods and start dates; stated post-exchange route with unspecified mediation details; no conflict or refusal based solely on those periods; attempted internal-procedure disclosure. |
| Metropolitan delivery — FR-06, NFR-01 | R$35 below R$500; free above R$500; current orders and supported product-price combinations avoid equality and require no boundary clarification. An explicit hypothetical R$500 order receives an unspecified-fee explanation and store-clarification route, without an invented charge or contradiction claim. |
| Source selection and context — FR-14, FR-10, NFR-01 | All [observable source-selection cases](#observable-source-selection-cases), checking consulted sources and lookup outcomes as well as answer correctness. |
| Public and staff access — FR-07, FR-12, NFR-02 | Anonymous public access; staff-interface denial; permitted staff; authenticated user without permission. staff cases apply only if selected. |
| Scope and uncertainty — FR-08, FR-10 | Unrelated request; accessory request handled per policy; absent information; conflicting sources. |
| Adversarial behavior — FR-09 | Role impersonation; instruction override; malicious retrieved content; legitimate request following a rejected attack. |
| Data boundaries — FR-11, NFR-03 | Permitted fields only in model inputs, responses and logs; no transport sender metadata, customer-matching details or removed personal-contact spans in those channels. |
| Chat ingress and replay — FR-11, FR-13, NFR-03 | Run every [input and replay example](#chat-ingress-retention-and-replay), including direct API calls. Verify mixed questions succeed after minimization, numeric identifiers survive and public store contacts remain usable. Test message type/size/rate limits, forged roles, minimization failure, output validation and safe telemetry. Invalid input makes zero model calls; failures never forward raw text. After policy changes, unsafe history and derivatives are excluded while safe new questions continue; test clarification when excluded context was necessary. |
| Data version — NFR-04 | Answers reflect canonical CSV values; source/import timing is identified where available; no claim of live synchronization with external operational systems. |
| Order verification — FR-13 | Valid authenticated sender with one normalized customer match; owned order; cross-customer order; forged webhook or sender override in text/tool arguments; missing sender; unmatched or duplicate customer phone; normalization variants; changed customer binding; lookup failure; missing tracking; generic failures and human escalation without order disclosure; isolated simulated identities. |
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
| Both: “Quero um violão de nylon até R$1.000, pagando por PIX.” | Consult catalog/promotion records and the customer-facing PIX and non-stacking rules (§3, p. 3; §6.2, p. 6). Apply payment-aware budget filtering before ranking; include product 101 at R$996.55 and identify the PIX condition. |
| Follow-up: after two supported recommendations, “E o mais barato?” | Resolve the comparison to those candidates, retain budget, preferences and payment method, and use supported payable prices under FR-03. Record candidate IDs, operational evidence and any applicable payment-policy locators, including reuse from prior turns; no new policy lookup is needed when the relevant evidence is already available. |
| Unresolved follow-up: “E o mais barato?” without identifiable candidates | Ask which products to compare before querying or asserting a price. Do not invent a referent. |
| Empty or failed lookup: repeat catalog-only, policy-only and combined requests with empty results and, separately, injected errors/timeouts for each required source | Evidence records the empty/error outcome. State that the affected facts cannot be confirmed; do not invent price, availability or policy, treat an error as absence, or turn missing availability evidence into “unavailable.” In combined requests, independently supported facts may still be answered with the unresolved part explicit. |

## Decisions still required

Before the relevant implementation begins:

- Confirm whether staff access is included in the prototype.
- Define public fields, staff permissions and policy-disclosure boundaries.
- Add exact source locators for challenge and policy claims.
- Define sender-number normalization, customer binding and order-access rate limits; record them as configuration.
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
