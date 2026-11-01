# Empório da Música — AI Customer Service Agent

A Python-based AI customer service agent for **Empório da Música**, a fictional musical instrument store in Campo Grande, MS, Brazil.

Developed for the **Artefact AI Engineer Technical Challenge**.

> **Status:** Requirements analysis and solution design. The agent has not yet been implemented.

## Overview

The prototype addresses recurring questions about products, prices, availability, orders and store policies using operational data while handling uncertainty and access boundaries. The challenge prioritizes engineering reasoning and a functional demonstration over production-scale complexity.

## Scope

The agent is expected to:

- Answer product, pricing, availability, and order-related questions using structured operational data.
- Consult store policies for opening hours, payment methods, exchanges, returns, and related procedures.
- Provide contextual instrument recommendations.
- Adopt a communication style appropriate to the store.
- Handle missing, ambiguous, conflicting, and out-of-scope information.
- Respect authorization boundaries when accessing customer-specific information.

A protected staff interface remains under consideration. Customer-specific order access uses the authenticated WhatsApp sender number, a unique stored customer match and server-side ownership checks; no SMS verification is required.

## Technical approach

Python is the only technology mandated by the challenge. Other choices will be justified against the requirements and available evidence.

| Concern | Initial decision |
|---|---|
| Language | Python |
| Customer interface | WhatsApp Business; no customer website assumed |
| Backend framework | Under review; Django remains a candidate |
| Authentication | WhatsApp sender authentication; optional staff authentication remains under review |
| Authorization | Application-enforced permissions and resource ownership |
| Agent architecture | Under evaluation |
| LLM and provider | Under evaluation |
| Structured data access | SQLite retained; Django ORM integration under review ([ADR-0001](docs/adr/0001-use-sqlite-for-structured-data.md)) |
| Policy retrieval | Under evaluation |
| Customer verification | Authenticated sender number → unique customer match → owned orders; no SMS or verification form |
| Conversation persistence | To be determined |

The customer experience follows WhatsApp, the store's primary remote channel ([policy §7, p. 6](data/políticas_da_loja.pdf#page=6)). The [brief, p. 2](desafio_tecnico_ai_eng_artefact.pdf#page=2), permits simpler demonstration interfaces; live WhatsApp integration is not an assignment requirement. A simulator may demonstrate the intended channel contract, with its limits explicit. See the [revised channel requirements](docs/requirements.md#purpose-and-scope).

## Data sources

The challenge provides:

- Product and category CSV datasets.
- Customer, order, and order-item CSV datasets.
- Promotion records.
- An internal store-policy PDF.

For this project, the supplied CSV files are the canonical sources for product, category, customer, order, order-item, and promotion data. In a real-world deployment, the responsible business unit (BU) would own keeping these data up to date; the prototype does not imply live synchronization with operational systems. If time permits, an interface for the BU to review and update this information may be implemented.

### Synthetic-data assumption

For the purposes of this technical challenge, **all challenge-provided datasets are treated as synthetic fixtures representing a fictional business**.

This working assumption is based on two elements of the challenge:

1. Empório da Música is explicitly described as a fictional store.
2. The deliverable requires a public GitHub repository containing the project.

Under this assumption, the supplied datasets may be used as development and testing fixtures and included in the public repository to support reproducibility.

### Data handling

Follow [actor and access](docs/requirements.md#actors-and-access) and [data minimization](docs/requirements.md#data-minimization) for authentication, verification, ownership, tool exposure and instruction boundaries.

### Reasoning about incomplete or apparently conflicting sources

The [challenge, p. 3](desafio_tecnico_ai_eng_artefact.pdf#page=3), asks for reasonable interpretations, documented assumptions and continued progress when information is incomplete. My approach is to check each rule's scope and the supplied data, record a justified decision, and seek clarification only when the remaining gap affects the answer.

| Case | Reasoning and project decision |
| --- | --- |
| Installments | [§3.1, p. 3](data/políticas_da_loja.pdf#page=3) expands §3's summary: apply its tiers rather than a universal R$100 minimum. The below-R$50 exception does not affect current 1–3 installment scenarios: the cheapest product, including active promotions, and the smallest order are R$159.90, or 3 × R$53.30. |
| Historical payment terms | Orders 9, 16 and 18 fall below §3.1's tier minimums. Preserve these canonical historical records and report administrative warnings when structural validation passes. Their recorded terms do not justify equivalent new installment offers. |
| Exchanges and warranty | [§4.2, p. 4](data/políticas_da_loja.pdf#page=4) allows defect exchanges within 30 days of purchase; [§8.1, p. 7](data/políticas_da_loja.pdf#page=7) describes a 90-day warranty from receipt. Different remedies and start dates do not establish a contradiction. Explain the stated post-exchange route—manufacturer contact, with store mediation on request—and clarify unspecified mediation details only when needed. |
| Contact numbers | Use [§7, p. 6](data/políticas_da_loja.pdf#page=6)'s (67) 3321-4500 as primary WhatsApp support, with failed customer matching routed to a human within the conversation. Retain [§1.2, p. 2](data/políticas_da_loja.pdf#page=2)'s (67) 3341-4444 as the listed company telephone/WhatsApp contact. Their stated roles support this mapping without treating either number as invalid. |
| Metropolitan delivery | [§5.1, p. 4](data/políticas_da_loja.pdf#page=4) specifies R$35 below R$500 and free delivery above it. Equality is omitted, not contradicted. No recorded order or combination of supplied product prices reaches exactly R$500, including active promotions and permitted PIX discounts, so this gap does not block current scenarios. In a real word scenario, to avoid confusion with customer and staff, I would argue with the store that the equality should be included and treat the case as free delivery. |

These are project interpretations of supplied sources, not legal conclusions or claims of live business validation. Recheck the data-dependent conclusions when canonical data or discount rules change. [Requirements and acceptance coverage](docs/requirements.md#data-and-policy-findings) define the resulting behavior; implementation and behavioral validation remain pending.

## Documentation

- [Requirements](docs/requirements.md) — Functional requirements, assumptions, constraints, and acceptance criteria.

Architecture, technical decisions, and evaluation evidence will be documented as they become concrete.

## Development roadmap

1. Complete initial requirements analysis and document assumptions.
2. Select and justify the agent architecture, model, and provider.
3. Implement a minimal working customer interaction.
4. Integrate structured data lookups and policy retrieval.
5. Implement necessary authorization and verification controls.
6. Test functional behavior, failure modes, and security boundaries.
7. Record the required interaction examples and finalize documentation.

The implementation scope may change as new evidence emerges.

## Running the project

**Not yet available.**

Python version, environment setup, configuration, execution commands, and test instructions will be documented once the application is implemented.

## Testing and evaluation

Required coverage is defined in [requirements](docs/requirements.md#acceptance-coverage-and-traceability). No behavioral validation has been completed.

## AI-assisted development

I use OpenAI Codex for source inspection, requirements analysis, design alternatives, documentation and adversarial review. I define the problem, evaluate tradeoffs, approve decisions and remain responsible for the result.

### Workflow

1. I define customer scenarios, scope and constraints, then ask Codex to inspect the challenge brief, policy manual and CSVs before developing requirements or recommending an architecture.
2. Codex drafts requirements, acceptance cases and design alternatives. I request focused reviews against the original sources, sometimes through separate sessions or delegated agents, to find contradictions, missing behavior and weak assumptions.
3. I challenge the findings: which passage supports the claim, which records demonstrate it, and does the disputed case affect the supplied scenarios? Codex checks passages, calculations and concrete counterexamples; I choose the business interpretation or leave the uncertainty explicit.
4. Once I accept a decision, Codex updates the README, requirements, data-access design and ADRs as applicable. I revisit earlier choices when the business context or customer experience calls for it, and request another consistency review after changes.
5. Changes are kept small and reviewable, preserving unrelated work. Codex checks the diff and runs relevant deterministic checks; I authorize commits and pushes. Findings, edits and check results are reported separately so a proposed correction is not confused with verified behavior.

### Work performed so far

Earlier sessions used this cycle to refine budgets based on payable prices, product availability, policy interpretations, ownership of canonical data and cases for selecting operational data or policies. I questioned apparent policy conflicts and asked whether missing boundary rules were reachable with the supplied data before deciding how to handle them.

The same process led me to reconsider my initial Django preference after recognizing WhatsApp as the store's customer channel, replace SMS verification with authenticated sender matching and order ownership checks, and replace blanket contact rejection with input minimization. Codex supplied analysis, alternatives and artifact revisions; I set and approved these directions.

### Verification and accountability

Adversarial findings are hypotheses to investigate. Agreement across sessions or agents does not establish correctness; source checks and tests support claims only within their demonstrated coverage.

Checks completed so far cover source inspection, data calculations, documentation consistency, local links, whitespace and change scope. The agent has not been implemented; runtime behavior, live integrations and security properties have not been validated.

For executable changes, my configured workflow requires focused tests before implementation, with separate test and implementation agents. That phase has not begun in this project; this disclosure will be updated with the work performed and evidence obtained.

## Deliverables

The final submission will include:

- A public GitHub repository with meaningful development history.
- Reproducible execution instructions.
- Justification in this README of the selected architecture, model, retrieval strategy, prompt strategy, and consequential technical decisions ([challenge, p. 2](desafio_tecnico_ai_eng_artefact.pdf#page=2)).
- Known limitations and potential improvements.
- Three to five recorded agent interactions, including at least one nontrivial data or policy consultation.
- Documentation of coding-assistant usage.

The repository will remain unchanged after the submission deadline specified by Artefact.

## Architecture decisions

- [ADR-0001: Use SQLite for structured operational data](docs/adr/0001-use-sqlite-for-structured-data.md)
