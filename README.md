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

A protected staff interface remains under consideration; simulated SMS verification is required for customer-specific order access.

## Technical approach

Python is the only technology mandated by the challenge. Other choices will be justified against the requirements and available evidence.

| Concern | Initial decision |
|---|---|
| Language | Python |
| Web framework | Django |
| Authentication | Django authentication |
| Authorization | Application-enforced permissions and resource ownership |
| Agent architecture | Under evaluation |
| LLM and provider | Under evaluation |
| Structured data access | SQLite via Django ORM ([ADR-0001](docs/adr/0001-use-sqlite-for-structured-data.md)) |
| Policy retrieval | Under evaluation |
| Customer verification | Simulated SMS OTP workflow for customer-specific order access |
| Conversation persistence | To be determined |

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
| Contact numbers | Use [§7, p. 6](data/políticas_da_loja.pdf#page=6)'s (67) 3321-4500 as primary WhatsApp support, including verification-failure fallbacks. Retain [§1.2, p. 2](data/políticas_da_loja.pdf#page=2)'s (67) 3341-4444 as the listed company telephone/WhatsApp contact. Their stated roles support this mapping without treating either number as invalid. |
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

OpenAI Codex (**Luna 6, low reasoning effort**) supports the development workflow primarily through **mechanical execution and adversarial analysis**.

The project author owns requirements, architecture, system boundaries, assumptions, acceptance, and final responsibility for quality.

Codex may reason about delegated problems and propose alternatives, but its conclusions do not independently establish correctness or authorize engineering decisions.

### Work performed so far

Codex assisted with initial documentation, requirements organization, order-verification alternatives, and inspection of the supplied challenge datasets.

The project author selected Django, the intended authentication and authorization approach, the interaction scenarios, and simulated SMS verification for customer-specific order access.

### Verification and accountability

Generated output is subject to engineering review.

Adversarial findings are treated as hypotheses requiring investigation. Tests and deterministic tools provide evidence within their respective coverage and assumptions.

This section will be updated to reflect actual implementation contributions and verification practices.

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
