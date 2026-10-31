# Empório da Música — AI Customer Service Agent

A Python-based AI customer service agent for **Empório da Música**, a fictional musical instrument store in Campo Grande, MS, Brazil.

Developed for the **Artefact AI Engineer Technical Challenge**.

> **Status:** Requirements analysis and solution design. The agent has not yet been implemented.

## Overview

Empório da Música's customer service team is overloaded with recurring questions about products, prices, availability, orders, and store policies.

The goal is to prototype an LLM-based assistant that can answer these questions using the store's operational data and policies, while handling uncertainty and respecting information-access boundaries.

The challenge prioritizes engineering reasoning, technical decisions, and a functional demonstration over production-scale complexity.

## Scope

The agent is expected to:

- Answer product, pricing, availability, and order-related questions using structured operational data.
- Consult store policies for opening hours, payment methods, exchanges, returns, and related procedures.
- Provide contextual instrument recommendations.
- Adopt a communication style appropriate to the store.
- Handle missing, ambiguous, conflicting, and out-of-scope information.
- Respect authorization boundaries when accessing customer-specific information.

Additional scenarios under consideration include a protected contributor interface, simulated customer verification, and adversarial access-control tests.

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
| Structured data access | Under evaluation |
| Policy retrieval | Under evaluation |
| Customer verification | Proposed simulated SMS OTP workflow |
| Conversation persistence | To be determined |

### Engineering principles

- **Requirements first:** Identify the problem, constraints, and acceptance criteria before selecting implementation mechanisms.
- **Deterministic where possible:** Use application logic for authorization, validation, and structured operations.
- **Explicit trust boundaries:** Model outputs and retrieved content must not override application permissions.
- **Data minimization:** Expose only the information necessary for each operation.
- **Evidence-driven validation:** Tests and observations support correctness claims within their coverage and limitations.
- **Proportional complexity:** Introduce dependencies and abstractions only when their benefits justify their costs.
- **Human-owned decisions:** Coding assistants may execute tasks and challenge assumptions, but engineering decisions and acceptance remain the author's responsibility.

## Data sources

The challenge provides:

- Product and category CSV datasets.
- Customer, order, and order-item CSV datasets.
- Promotion records.
- An internal store-policy PDF.

These files are static snapshots, not live operational systems.

### Synthetic-data assumption

For the purposes of this technical challenge, **all challenge-provided datasets are treated as synthetic fixtures representing a fictional business**.

This working assumption is based on two elements of the challenge:

1. Empório da Música is explicitly described as a fictional store.
2. The deliverable requires a public GitHub repository containing the project.

Under this assumption, the supplied datasets may be used as development and testing fixtures and included in the public repository to support reproducibility.

This is a documented project assumption, not an independently verified classification or a general authorization to publish third-party data. If contradictory evidence emerges, the assumption and affected repository contents must be reassessed.

### Data handling

Although the challenge data is treated as synthetic, the application is designed around security boundaries that would also matter in a real-world environment.

- Authentication and authorization are enforced by the application, not by the LLM.
- Customer-specific operations require appropriate verification and resource ownership checks.
- Tools expose only the information necessary to fulfill an authorized request.
- Retrieved documents and user inputs cannot override application permissions.
- Credentials and secrets must never be committed to the repository.
- Real production data would require separate classification, authorization, and appropriate privacy controls before use with coding assistants or external model providers.

The prototype does not claim production-grade privacy or security assurance.

### Data freshness

The supplied datasets represent snapshots.

Product prices, stock availability, promotions, and order statuses must not be represented as independently verified real-time information.

## Documentation

- [Requirements](docs/requirements.md) — Functional requirements, assumptions, constraints, and acceptance criteria.

Architecture, technical decisions, and evaluation evidence will be documented as they become concrete.

The challenge brief remains the authoritative source for the original assignment. Project-specific interpretations and decisions are maintained separately.

## Development roadmap

1. Complete initial requirements analysis and document assumptions.
2. Select and justify the agent architecture, model, and data-access mechanisms.
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

Testing will cover:

- Functional correctness and grounded responses.
- Appropriate tool selection and retrieval.
- Handling of missing or conflicting information.
- Authorization and resource ownership enforcement.
- Failure handling and out-of-scope requests.
- Prompt-injection and adversarial access attempts.

Actual test results and reproducible execution commands will be added as implementation progresses.

**No behavioral validation has been completed yet.**

## AI-assisted development

OpenAI Codex (**Luna 6, low reasoning effort**) supports the development workflow primarily through **mechanical execution and adversarial analysis**.

The workflow separates engineering authority from delegated work.

### Engineer responsibilities

The project author retains ownership of:

- Problem formulation and requirements interpretation.
- Architectural decisions and technical trade-offs.
- System boundaries, interfaces, and invariants.
- Assumptions, risks, and acceptance criteria.
- Evaluation and acceptance of implementation changes.
- Final responsibility for correctness, security, and deliverable quality.

### Codex responsibilities

**Mechanical execution**

- Documentation and repetitive implementation work.
- Repository and dataset inspection.
- Execution of tests, linters, and static analyzers.
- Collection and organization of verification evidence.
- Consistency checks across code, tests, and documentation.

**Adversarial analysis**

- Searching for contradictions and incomplete requirements.
- Challenging engineering assumptions.
- Identifying failure modes and edge cases.
- Searching for authorization bypasses and security weaknesses.
- Proposing counterexamples and identifying missing tests.

Codex may reason about delegated problems and propose alternatives, but its conclusions do not independently establish correctness or authorize engineering decisions.

### Work performed so far

Codex assisted with initial documentation, requirements organization, order-verification alternatives, and inspection of the supplied challenge datasets.

The project author selected Django, the intended authentication and authorization approach, the interaction scenarios, and the proposed simulated SMS verification workflow.

The inspected datasets are treated as synthetic under the project's documented challenge assumption.

### Verification and accountability

Generated output is subject to engineering review.

Adversarial findings are treated as hypotheses requiring investigation. Tests and deterministic tools provide evidence within their respective coverage and assumptions.

**The engineer defines what must be true and why. Codex assists with execution and searches for counterexamples. Tools provide evidence. The engineer evaluates that evidence and makes the final decisions.**

This section will be updated to reflect actual implementation contributions and verification practices.

## Deliverables

The final submission will include:

- A public GitHub repository with meaningful development history.
- Reproducible execution instructions.
- Justification of the selected architecture, model, retrieval strategy, and consequential technical decisions.
- Known limitations and potential improvements.
- Three to five recorded agent interactions, including at least one nontrivial data or policy consultation.
- Documentation of coding-assistant usage.

The repository will remain unchanged after the submission deadline specified by Artefact.

---

**Project:** Artefact AI Engineer Technical Challenge  
**Primary language:** Python  
**Current phase:** Requirements analysis and solution design