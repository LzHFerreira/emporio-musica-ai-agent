# Requirements — Empório da Música assistant

## Purpose and scope

Build a Python text-based customer-service assistant for the fictional Empório da Música.

This document defines the working requirements, assumptions and acceptance criteria. The challenge brief remains authoritative for the original assignment. Project decisions and proposed extensions are identified separately.

Django is the selected application framework. The agent architecture, model, provider and data-access approach remain undecided.

**Status:** Requirements analysis. No behavioral validation has been completed.

## Working assumptions

### Synthetic challenge data

All challenge-provided datasets are treated as synthetic fixtures representing a fictional business.

This working assumption follows the fictional scenario and mandatory public-repository deliverable. It is not an independently verified classification or general authorization to publish unrelated third-party data.

Under this assumption, supplied fixtures may be used for development, testing and repository reproducibility. Independent confirmation of synthetic status is not a prerequisite for implementation. Contradictory evidence requires reassessing the assumption and affected repository contents.

Synthetic fixtures do not remove the need to demonstrate application authorization, resource ownership and data minimization. Credentials and real production data remain outside this assumption.

### Snapshot semantics

The supplied CSV files are static snapshots.

Prices, stock, promotion flags and order statuses must be described as recorded information, without claiming live synchronization or independently verified present-day validity.

## Scope and scenarios

### Baseline

The assistant supports:

1. Contact information and opening-hours questions.
2. Product, price, availability and promotion questions.
3. Instrument recommendations based on customer needs and budget.
4. Customer-facing policy questions.
5. Missing, conflicting and out-of-scope information.
6. Attempts to override instructions or access restrictions.

### Proposed extensions

The following remain proposed, consistent with the README:

- A protected contributor interface for internal procedures and exact stock quantities.
- Customer-specific order-status access through simulated SMS verification.

Their requirements below define intended behavior **if included**. They are not represented as mandatory challenge requirements.

Real SMS delivery, production identity verification, account recovery, purchases, order changes, and stock or price updates are outside the prototype scope.

## Actors and access

- **Public client:** may access public store information, product prices and availability, recommendations and customer-facing policies without signing in.
- **Contributor, if implemented:** uses Django authentication and explicitly assigned permissions to access restricted operational information.
- **Verified customer context, if implemented:** grants temporary, narrowly scoped access to orders belonging to the corresponding synthetic customer.

A role or identity claimed in a message grants no permission.

Django authentication for contributors and simulated customer verification are separate mechanisms. Neither automatically grants the permissions of the other.

Before implementing restricted retrieval, define the permitted public fields, contributor permissions and customer-facing policy sections. Until classified, internal content is withheld from public responses.

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
| FR-01 | Receive and respond to text messages using the store persona. | Respond in Portuguese with a friendly, informal and professional tone appropriate to the request. | Challenge; Project |
| FR-02 | Answer contact and opening-hours questions from the policy. | Report recorded opening hours accurately. Acknowledge conflicting contact details instead of silently choosing one. | Challenge; Policy |
| FR-03 | Recommend instruments using customer needs and recorded product attributes. | Ask for missing preferences when needed. Recommendations respect the stated budget and explain their supporting attributes. Do not invent specifications. | README; Project |
| FR-04 | Report recorded product prices and availability. | Use the matching source record. Do not present zero stock as available. Suggest available alternatives only when supported by the data. Public responses do not disclose exact stock quantities under the proposed access policy. | Challenge; Data; Project |
| FR-05 | Report promotion information within snapshot limits. | Exclude inactive promotions from promotional offers. Describe active records as active in the supplied snapshot, without asserting present-day validity. For an unambiguous applicable promotion, show the recorded base price, discount percentage and calculated promotional price. | Challenge; Data; Project |
| FR-06 | Answer customer-facing policy questions. | Include applicable conditions and deadlines. Ask for missing facts and acknowledge material conflicts. Do not disclose internal-only procedures. | Challenge; Policy; Project |
| FR-07 | Provide a protected contributor interface, if selected. | Anonymous users cannot access it. Authenticated users receive only information allowed by their permissions. Tests cover internal procedures and exact stock quantities. | Proposed project extension |
| FR-08 | Handle out-of-scope requests. | Politely explain the supported scope. For accessories, use the manual’s stated sales scope once its exact source passage is confirmed. | Challenge; Policy |
| FR-09 | Resist instruction and access-control bypass attempts. | Conversational role claims and instructions embedded in messages, CSV fields or retrieved documents do not change permissions or expose protected information. Legitimate permitted requests remain answerable. | README; Project |
| FR-10 | Handle missing, ambiguous or conflicting information. | Ask for clarification when necessary. State when sources do not establish an answer. Do not invent store-specific facts. | README; Project |
| FR-11 | Minimize customer-related information exposure. | Return only fields needed for an authorized operation. Exclude unnecessary names, phone numbers, email addresses and unrelated order details from model inputs, responses and logs. | README; Project |
| FR-12 | Provide public customer interaction. | An anonymous user can ask permitted questions without signing in. Claimed contributor status does not expand access. | Project |
| FR-13 | Restrict order-status access, if selected. | Establish the simulated verification context, check order ownership server-side and return only permitted order information. Failed, unavailable or ambiguous verification discloses no order details. | Proposed project extension |

### Promotion rules

For FR-05:

- Interpret `active` as a snapshot attribute, not proof of current validity.
- Calculate the promotional price as base price × (1 − discount percentage / 100), using decimal arithmetic and rounding half-up to two decimal places.
- Do not invent stacking or precedence rules for multiple promotions.
- Apply the proposed PIX non-stacking rule only after linking it to the supporting policy passage. If applicability remains unclear, explain the uncertainty rather than calculate a combined discount.
- If multiple records or conflicting rules prevent a unique calculation, report the ambiguity.

### Data minimization

PII tokenization is **not** a mandatory README requirement.

The prototype must define and test which fields may cross each boundary: data access, model input, user response and logs. Tokenization may be introduced if a concrete need justifies its additional complexity.

Access control must be enforced by application services and tools, independently of model instructions.

## Proposed order-verification extension

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

The reviewer obtains codes through a development-only test channel separate from the customer chat. Codes must not enter model context, ordinary application logs or customer-chat responses.

The simulator must be clearly labeled and excluded from any production authentication claim.

### Required properties

Codes must be unpredictable, single-use, expire and have issuance and verification-attempt limits. Verification state must remain server-side.

Before implementation, record the chosen code lifetime, attempt limits, issuance limits and verification-session lifetime as explicit configuration with acceptance tests.

Failed and ambiguous lookups must use responses that do not reveal whether a customer or order exists. Verification for one customer must not authorize another customer’s orders.

If the extension is omitted, order-specific requests receive an explanation of the unsupported capability and a store-contact route without disclosing order details.

## Nonfunctional requirements

| ID | Requirement | Verification |
| --- | --- | --- |
| NFR-01 | Ground store-specific factual answers in supplied sources. | Compare representative answers with identified source records or policy sections, including missing and conflicting cases. |
| NFR-02 | Enforce authorization independently of the conversation. | Test application and tool access directly, including anonymous users, insufficient permissions, impersonation and cross-customer requests where applicable. |
| NFR-03 | Minimize data crossing system boundaries. | Inspect model requests, responses and logs against the permitted-field definitions. Verify that verification codes and unnecessary customer fields are absent. |
| NFR-04 | Represent freshness honestly. | Stock, price, promotion and order answers do not claim live or independently confirmed current information. |
| NFR-05 | Make the project reproducible and reviewable. | A reviewer can configure and run the completed application and tests using documented dependencies, fixtures and environment settings. |
| NFR-06 | Restrict internal policy disclosure. | Public retrieval and response paths expose only classified customer-facing policy information. Test internal-content requests and prompt-injection attempts. |
| NFR-07 | Preserve public-repository boundaries. | Review tracked files and history for credentials, real production records and unintended sensitive logs or examples. Synthetic challenge fixtures remain governed by the documented working assumption. |

## Data and policy findings

The supplied analysis reports:

- 65 products.
- 9 categories.
- 50 customers.
- 20 orders.
- 22 order items.
- 25 promotions.

These counts are inspection findings, not fixed application requirements. Confirm them against the fixtures used for implementation.

Product records include price, stock, status and specifications. Promotion records include a product reference, percentage and active flag, but no validity dates. The challenge does not require every dataset to be used.

The policy manual is reported as version 2.1, June 2025, and identifies itself as internal.

The following reported ambiguities require exact source references and explicit handling:

| Finding | Required behavior |
| --- | --- |
| Credit-card installment thresholds differ between the summary and detailed rules. | Do not invent a precedence rule or give an unsupported installment calculation. |
| Defect-exchange and warranty sections describe potentially conflicting deadlines and routes. | Explain the source ambiguity and avoid definitive eligibility decisions based on conflicting text. |
| Contact details differ across sections. | Acknowledge the discrepancy; do not silently select a preferred contact. |
| Metropolitan delivery charges distinguish amounts above and below R$500 but leave exactly R$500 unclear. | Identify the missing boundary rule rather than infer a fee. |

These findings describe supplied policy text; they do not establish legal conclusions.

## Acceptance coverage and traceability

Each test or evaluation case must reference the requirement IDs it checks and identify its expected result.

| Coverage | Minimum cases |
| --- | --- |
| Persona and contact — FR-01, FR-02 | Portuguese response; recorded hours; conflicting contact details. |
| Recommendations and products — FR-03, FR-04 | Suitable recommendation; missing preferences; budget constraint; unavailable product; ambiguous product name. |
| Promotions — FR-05 | Inactive flag; snapshot-active flag; decimal calculation and rounding; conflicting promotions; unresolved stacking rule. Test PIX non-stacking once its source is confirmed. |
| Policies — FR-06, NFR-06 | Supported rule; missing facts; conflicting deadlines; exactly R$500 delivery boundary; attempted internal-procedure disclosure. |
| Public and contributor access — FR-07, FR-12, NFR-02 | Anonymous public access; contributor-interface denial; permitted contributor; authenticated user without permission. Contributor cases apply only if selected. |
| Scope and uncertainty — FR-08, FR-10 | Unrelated request; accessory request after source confirmation; absent information; conflicting sources. |
| Adversarial behavior — FR-09 | Role impersonation; instruction override; malicious retrieved content; legitimate request following a rejected attack. |
| Data boundaries — FR-11, NFR-03 | Permitted fields only in model inputs, responses and logs; no verification codes in those channels. |
| Freshness — NFR-04 | No live-data claims for prices, stock, promotions or order statuses. |
| Order verification — FR-13, if selected | Successful verification; different verified customer; invalid, expired and reused codes; issuance and attempt limits; session binding and expiry; failed or unavailable verification; ambiguous match; missing tracking data; non-enumerating failures. |
| Reproducibility — NFR-05 | Clean setup using the completed README and documented fixtures. |

For adversarial and unsupported requests, success means the expected refusal, clarification or safe handling—not completion of the requested attack.

Use deterministic tests for permissions, ownership, verification state and price calculations. Evaluate generated answers against source facts and explicit behavioral criteria rather than requiring identical wording.

Passing tests support claims only within their recorded coverage. No validation results are claimed at this stage.

## Decisions still required

Before the relevant implementation begins:

- Confirm whether contributor access and simulated order verification are included in the prototype.
- Define public fields, contributor permissions and policy-disclosure boundaries.
- Add exact source locators for challenge and policy claims.
- Confirm promotion stacking rules.
- Choose verification limits if the order extension is selected.
- Select and justify the agent, model, provider and data-access approach.

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