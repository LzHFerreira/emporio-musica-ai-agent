# Empório da Música — AI Customer Service Agent

Python customer-service prototype for the fictional Empório da Música in Campo Grande/MS, built for the [Artefact AI Engineer challenge](desafio_tecnico_ai_eng_artefact.pdf).

## What the application does

The assistant answers Portuguese customer messages about catalog products, prices, stock, promotions, public store policy (hours, contacts, returns, warranty, delivery) and the customer's own orders. Each message enters through a signed local webhook and is processed by a worker, where the model may call bounded read-only tools. Every reply passes deterministic checks before it is sent. Out-of-scope questions get a fixed redirect. Replies go only to a local Meta mock; live WhatsApp delivery is not verified.

**Status:** the deterministic application and its tests work. Answer quality with a live model has only small, development-stage evidence (see [Current results](#current-results)). This is not full challenge acceptance.

## Running the project

Run every command from the repository root. `.env` sets `EMPORIO_DB_PATH=.emporio.sqlite3`, which is relative to the working directory. Plain Python does not load `.env`, so **every** `uv run --env-file .env` command below needs that file present.

### Shortest reproducible demo (no account, no credentials)

1. Install uv once. macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`. Then open a new terminal.
2. Get the code: `git clone https://github.com/LzHFerreira/emporio-musica-ai-agent.git` and `cd emporio-musica-ai-agent`, or click **Code → Download ZIP** on the GitHub page, unzip it, and open a terminal in that folder.
3. Create the settings file: `cp .env.example .env` (Windows PowerShell: `Copy-Item .env.example .env`).
4. Run:

```bash
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py load_sources --source-dir data
uv run --env-file .env python manage.py demo_chat
uv run --locked pytest
```

`load_sources` validates the six CSVs and the policy PDF in `data/` before activating one snapshot. `demo_chat` answers five sample questions with a scripted model; expect `"model_mode": "scripted"` and `"accepted_count": 5`. Provider responses in tests are mocked.

| Message | Fix |
| --- | --- |
| `uv: command not found` or `uv is not recognized` | Open a new terminal after installing uv. |
| `no such table` or an empty catalog | Run the `migrate` and `load_sources` commands again. |
| `Set a valid CLOUDFLARE_ACCOUNT_ID` or `Set CLOUDFLARE_API_KEY` | Check `.env` for the live model (see below); no spaces around `=`. |
| `Não consegui concluir sua consulta agora…` | The model gave no checked answer, or the quota ran out. Try again later. |

### Live model

Choose one provider in `.env`. `MODEL_PROVIDER` defaults to `cloudflare`; selection is explicit and errors never switch providers. The full variable list is in [.env.example](.env.example). OpenAI, Anthropic, non-free OpenRouter routes and Cloudflare models outside the reviewed list also need `ALLOW_PAID_MODELS=true`; that flag does not cap costs.

**Ollama (local, no account; recommended first).** Install Ollama, run `ollama pull qwen3.5:9b`, then set in `.env`:

```
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_TIMEOUT_SECONDS=180
TURN_DEADLINE_SECONDS=900
```

`OLLAMA_TIMEOUT_SECONDS` (default 180) bounds one model request; cloud providers keep 60 s. `TURN_DEADLINE_SECONDS` defaults to 60, the WhatsApp reply target, which slow local hardware may not meet; the recorded conversations used 900. The `.env.example` default `qwen3:4b` did not finish a policy turn within the 55-second cutoff in an earlier probe, so use the model above.

**Cloudflare Workers AI (default provider, free account).**

1. Create a free account at [dash.cloudflare.com](https://dash.cloudflare.com/sign-up).
2. In the left menu, open **AI → Workers AI** and choose **Use REST API**. Copy your **Account ID**, then click **Create a Workers AI API Token** and copy the token.
3. In `.env`, set `CLOUDFLARE_ACCOUNT_ID=` and `CLOUDFLARE_API_TOKEN=` on separate lines, with no spaces around `=`. Keep `.env` private.

The free plan has a daily allowance; the default model, `@cf/zai-org/glm-4.7-flash`, is on Cloudflare's free-eligible list. Without credentials, `interact_chat` stops with `CommandError: Set a valid CLOUDFLARE_ACCOUNT_ID before using Cloudflare` before any model request. To use Ollama instead, set `MODEL_PROVIDER=ollama`.

**Talk to the assistant:**

```bash
uv run --env-file .env python manage.py interact_chat --message "Quanto custa o Takamine GD20?"
```

Omit `--message` for interactive input until `/quit` or EOF. The CLI uses a synthetic sender unless `--sender` gives a customer's WhatsApp digits (for example `5567996547821`, synthetic customer 2), which scopes order lookups to that customer. A local Meta mock accepts replies; nothing is sent to Meta.

**Other providers.** Each provider needs its own account and credential. Cost figures are per million input/output tokens.

| Provider | Default model and cost per 1M input/output tokens (USD) | Setup and billing |
| --- | --- | --- |
| Cloudflare Workers AI (default) | Reviewed free-eligible `@cf/zai-org/glm-4.7-flash` — $0.0605 / $0.40 (default; 13/15 live development runs). `@cf/google/gemma-4-26b-a4b-it` — $0.10 / $0.30 (alternative; 11/15). | Set `MODEL_PROVIDER=cloudflare`, `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_KEY` (or `CLOUDFLARE_API_TOKEN`); optionally set `CLOUDFLARE_MODEL`. Selecting a model outside the reviewed list requires `ALLOW_PAID_MODELS=true`; the flag accepts cost risk, not model quality. The direct Gemma adapter adds a private `respond_to_customer` function so its final reply uses the app's structured terminal parser; it is not a catalog or MCP tool. For Gemma requests, `search_catalog.query` is required; use an empty string only for general browsing. Gemma's Wrangler guide documents disabling thinking with `enable_thinking=false`. Workers AI has a 10,000 Neurons/day free allocation; exceeding it on Workers Free stops requests, while paid usage is billed. [Gemma pricing](https://developers.cloudflare.com/ai/models/%40cf/google/gemma-4-26b-a4b-it/) · [GLM pricing](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/) · [disable thinking](https://developers.cloudflare.com/workers-ai/get-started/workers-wrangler/) · [plan and quota](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| OpenAI | `gpt-6-luna` — $0.10 / $0.50. | Set `MODEL_PROVIDER=openai`, `ALLOW_PAID_MODELS=true` and `OPENAI_API_KEY`; optionally set `OPENAI_MODEL`, `OPENAI_API_MODE` (`responses` by default), and `OPENAI_REASONING_EFFORT` (unset by default). `chat_completions` forces `reasoning_effort=none` for GPT-6 Luna compatibility. API billing is separate from ChatGPT subscriptions. [Model, endpoints and price](https://developers.openai.com/api/docs/models/gpt-6-luna) · [API pricing](https://developers.openai.com/api/docs/pricing) · [billing separation](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform) |
| Anthropic | `claude-haiku-5-5` — $0.10 / $0.50 for prompts up to 100k tokens; $0.50 / $2.50 above 100k. Optional higher-cost alternative: Claude Sonnet 5.5 — $2 / $10. | Set `MODEL_PROVIDER=anthropic`, `ALLOW_PAID_MODELS=true` and `ANTHROPIC_API_KEY`; optionally set `ANTHROPIC_MODEL`. API billing is usage-based. [Model IDs and pricing](https://platform.claude.com/docs/en/models/haiku-5-5/overview) · [all model prices](https://platform.claude.com/docs/en/about-claude/pricing) |
| Ollama | `qwen3:4b` is the `.env.example` starting point; the recorded runs used `qwen3.5:9b`. No provider token charge. | See [Live model](#live-model). Compute, electricity and speed depend on the host. [Ollama API](https://docs.ollama.com/api/openai-compatibility) · [local evidence](docs/model-capability.md#local-ollama-2026-11-03) |
| OpenRouter | Existing explicit adapter; model and price depend on the selected route. | Set `MODEL_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. Only a route ending in `:free` is selectable without `ALLOW_PAID_MODELS=true`, and a `:free` route is not a guaranteed entitlement. The previously probed `google/gemma-4-26b-a4b-it:free` returned HTTP 429 before inference. [OpenRouter model catalog](https://openrouter.ai/api/v1/models) · [probe evidence](docs/model-capability.md) |

Prices were checked on 2026-11-03 and can change. Caching, long context, account plan and other provider charges change the total; Cloudflare free use consumes a daily neuron quota, not a fixed number of tokens. Prices do not predict answer quality. No live OpenAI or Anthropic probe has been run. [Validation](docs/validation.md) separates interface implementation from provider and answer-quality qualification.

### Other interfaces

**MCP tools.** To expose the four catalog, public-policy and owned-order tools to an MCP client, run `uv run --env-file .env python manage.py mcp_server` from the repository root. This local stdio server uses the locked `mcp==1.30.0` SDK. The client chooses its own model; this command does not use the app's provider selection. The optional `EMPORIO_MCP_SENDER` is trusted server configuration for the owned-order tools; if unset, those tools return a generic denial. A client or model argument cannot set or impersonate the sender. Each call reads the active source bundle and reports `bundle_version`; compare it before combining results. See [interfaces](docs/interfaces.md#mcp-server).

**Staff source maintenance.** Run `uv run --env-file .env python manage.py createsuperuser` and `... runserver`, then sign in at `http://127.0.0.1:8000/accounts/login/` and open `/equipe/fontes/`. Staff can stage, preview, publish and roll back CSV/PDF sources; ordinary staff need the [documented source grants](docs/interfaces.md#staff-source-maintenance). PDF passage review currently requires JSON input. Run one worker-backed CLI command at a time against a database; a separate process may wait five seconds for the singleton lease to expire.

## Current results

Measured on 2026-11-04 on a clean checkout of commit `dd6f5ae` (the last code commit), unless stated otherwise:

- `uv run --locked pytest`: 490 passed, 0 failed; coverage 96% (gate: 95%).
- `demo_chat` on a fresh database: 5 of 5 scripted cases accepted and delivered.
- `ruff check`, `ruff format --check`, `mypy .` and `lint-imports`: clean. The full `scripts/run_quality_gates.sh` (also Radon, Semgrep Pro, Django and migration checks) was not rerun for this summary; see [validation](docs/validation.md).
- Fresh clone of `2cc6835`: the [shortest demo](#shortest-reproducible-demo-no-account-no-credentials) completed; `demo_chat` accepted 5 and `pytest` passed 472 tests at that commit.
- Retrieval ([ADR-0005](docs/adr/0005-retrieval-refactoring.md), deterministic, 11 development cases plus 4 condition-critical probes): the full manual gave 15/15 required conditions at about 15,200 characters per call; ranked lookup gave 14/15 at about 750–1,700 characters (about 13× smaller) and missed manual §4.2 for a defect question. The full manual is primary; ranked lookup stays available.
- Live model: no live run was made on the submitted revision. Earlier, narrower evidence, labeled historical (recorded before the facts and JSON-only reply contract):
  - 2026-11-03, Cloudflare: five single-turn development questions, three runs each. GLM-4.7 Flash passed 13/15 and Gemma 4 11/15. These questions were inspected during development, so they are regression evidence. The four probe cases added later have not been run on Cloudflare.
  - 2026-11-04, Ollama `qwen3.5:9b` at commit `5750de3`: five recorded two-turn conversations, with 9 of 10 turns grounded. See [recorded conversations](docs/interactions.md).

```bash
uv run --env-file .env python manage.py evaluate_retrieval
uv run --env-file .env python manage.py evaluate_model --runs 3
```

`evaluate_model` sends the nine cases in `tests/fixtures/model_quality.json` to the configured live model and prints every reply; it consumes provider quota. Review non-passing replies manually.

## Recorded conversations (submitted revision)

No fresh recordings were made for the submitted revision. The only recordings are historical and predate the facts and JSON-only reply contract: [five live conversations with `qwen3.5:9b`, 2026-11-04, commit `5750de3`](docs/interactions.md). `docs/demo-interactions.json` is likewise a historical scripted recording; run `demo_chat` for current output.

## Architecture decisions and tradeoffs

- **Django 5.2 and SQLite.** Django supplies authentication, CSRF, migrations and staff pages; SQLite keeps local state without a database service. This is more infrastructure than a minimal CLI needs, and broad write contention is unqualified.
- **Bounded tool loop.** At most three model requests and four tool executions per turn. Every final reply must be the terminal JSON object; prose is rejected and retried within the same budget, ending in a fixed failure reply if no attempt recovers. The model never writes SQL. Prices, promotions, PIX rules, availability and customer identity come from application code.
- **Application-rendered facts.** Catalog rows and own-order rows carry turn-scoped references (`catalog-N`, `order-N`). A reply selects them in a `facts` list, which the Cloudflare reply tool also supports. The app renders product name, availability, payable price and payment condition, or order id, status, tracking code and estimated delivery, from evidence. In any turn with catalog evidence, the model's own text may not state prices or stock at all. Unknown references, references leaked into text and such claims are rejected through the bounded retry.
- **Output checks for the remaining text.** Availability is bound to the named product; PIX is not stacked on promotions (manual §6.2); return entitlement is denied for used items and business-day units (§4.1); opening hours must be ordered; prices are bound to their product. These are phrase and number rules, not semantic understanding.
- **Retrieval.** The full manual is the primary policy source, accepted in [ADR-0005](docs/adr/0005-retrieval-refactoring.md) on 2026-11-04. It adds about 5k input tokens per request, which uses free-tier quota faster. Catalog wording fixes: shared Portuguese stop words, hyphenless model codes, price and payment words ignored in budgeted searches, and description-only matches dropped when stronger matches exist. Catalog search stays deterministic.
- **Evaluator.** A declared critical false claim is classified INCORRECT. `assess()` reports factual, lexical, execution and uncertainty (expected clarification or abstention) dimensions separately. Held-out scenarios declare their critical claims. The evaluator's checks do not import the production output guards, so a guard defect cannot also hide in the score.
- **Rejection feedback.** A rejected draft names the unsupported number or the missing source tool, so the bounded retry can correct that specific problem.
- **Source interpretations.** These are project decisions on the supplied sources, not legal conclusions:
  - Installments follow the §3.1 tiers, not the summary's universal R$100 minimum.
  - Historical orders 9, 16 and 18 are below current installment minima; they are kept and flagged as warnings, and do not justify new terms.
  - Defect exchange (§4.2, 30 days from purchase) and warranty (§8.1, 90 days from receipt) differ in remedy and start date, so they are not a conflict. Both are explained, with manufacturer contact and store mediation on request.
  - WhatsApp support (§7, (67) 3321-4500) and the company telephone/WhatsApp (§1.2, (67) 3341-4444) are labeled by their stated roles.
  - Metropolitan delivery is R$35 below R$500 and free above it. Equality is unspecified, and no supplied price reaches R$500, so this does not affect current scenarios; ask the store before relying on it.

### Synthetic-data assumption

The supplied datasets are treated as synthetic fixtures because the challenge describes a fictional store and requires a public repository. Credentials and runtime databases remain excluded. Authorization and minimization still apply; customer and model tools are read-only.

## Known limitations

- **Facts depend on the model choosing them.** The rule removes the model's ability to state catalog prices or stock, but a model that does not select facts produces retries and fallback replies, not better answers. No live model has been run against this contract.
- **Policy claims** (deadlines, conditions) are still free text checked by phrase and number rules; pronouns and sentence-level negation can slip through. Structured policy rules (milestone 5) are not done.
- **Order status** renders verbatim from the source data (for example `delivered`), not translated.
- **Customer-stated numbers,** such as "recebeu há 3 dias", are rejected by the numbers check even when the reply is correct.
- **Clarifying questions** can contain invented facts, which the checks do not catch.
- **Spec values** are not accent-folded in catalog matching.
- **Multi-turn source freshness** is untested.
- **Evaluator patterns** for critical claims are narrow.
- **Evidence is small:** five development questions and five two-turn conversations on one host. Independently written paraphrases and a Cloudflare run of the four probe cases are still needed.
- **Not done:** structured policy rules (milestone 5), multi-turn state (8), independent qualification (10), browser chat (11) and CI. Operator inbox and release controls, live Meta onboarding and delivery, deployment hardening, retention operations and physical power-loss durability are also unestablished. Handoff state does not establish a live human transfer.

## Development roadmap

1. **Qualify the model:** add fresh paraphrases and run the four probe cases on Cloudflare.
2. **Correct answers:** fix the limitations above test-first.
3. **Complete conversations:** retain preferences, resolve ambiguous references, handle missing eligibility and owned-order boundaries with the actual model.
4. **Challenge evidence:** reproduce setup from the submitted checkout and tie validation to the reviewed commit.
5. **Extension acceptance:** finish operator controls, staff usability and remaining resource and concurrency checks. Keep the existing staff and transport code.

Live Meta remains outside challenge acceptance.

## Development context

Most of this project was built during the Dia de Finados holiday (2 November). My two daughters were at home until they went back to school on 4 November, so I worked in short, interrupted sessions and did not commit as I went. As a result, commit `8b0090e` (3 November) bundles about 21,000 changed lines of application code, tests and tooling into one commit, which is hard to review. That was a process failure on my part, not a design choice.

The commits dated 4 November show how I deliver under strong time pressure: small, test-first changes, each verified by the full test suite, with the remaining gaps listed under [Known limitations](#known-limitations).

## AI-assisted development

I used OpenAI Codex throughout requirements analysis, implementation, test generation, documentation and adversarial review. I directed the work by defining customer scenarios, setting acceptance criteria, comparing alternatives and deciding which changes to retain. I own the architecture, scope and submitted result, including the limitations documented here.

My decisions included evaluating recommendations against payable prices, keeping PIX discounts from stacking with promotions, distinguishing product status from stock quantity, and enforcing customer identity and order ownership outside the model. I challenged apparent policy contradictions against the original passages and supplied records before accepting an interpretation.

The final model-quality phase used Claude Code with Claude Opus 5.5 as planner, coordinator and reviewer, and Claude Haiku 5.5 subagents at low reasoning effort for implementation, tests, investigations and live validation runs. GPT-6 Luna, the delegation model named first in my agent instructions, was not available in that environment. Those commits carry a `Co-Authored-By: Claude Opus 5.5` trailer. A test agent wrote a focused failing test, a separate implementation agent made the smallest change, and the coordinator reviewed the diff and reran checks before I approved each commit. Batches were limited to 50 changed lines unless I approved more.

Review caught several agent errors before they were accepted: a proposed newline split that would have accepted swapped product prices, tests that passed for the wrong reason because they omitted catalog or policy sources, validation ground truth that left out parts of the policy PDF, and a Radon complexity regression. Live runs showed that most early failures came from the harness rather than the models, and they were fixed test-first.

This iteration (commits from `9e311d7` to `dd6f5ae`) was planned and reviewed by Claude (Anthropic) as coordinator. Implementation and tests were delegated to separate test and implementation subagents, test-first, under the repository owner's review and approval. Every commit was verified by the full test suite. [Validation](docs/validation.md) records the evidence and remaining gaps; I remain accountable for the submission's correctness.

## Architecture decision records

- [ADR-0001: SQLite through Django ORM](docs/adr/0001-use-sqlite-for-structured-data.md)
- [ADR-0002: PDF ingestion and policy retrieval](docs/adr/0002-pdf-ingestion-and-retrieval.md)
- [ADR-0003: Protected source maintenance and rollback](docs/adr/0003-protected-source-maintenance.md)
- [ADR-0004: Explicit model selection and provider compatibility](docs/adr/0004-free-model-and-provider-fallbacks.md)
- [ADR-0005: Retrieval refactoring (accepted)](docs/adr/0005-retrieval-refactoring.md)

## Evidence index

| Requirement area | Code | Tests | Docs |
| --- | --- | --- | --- |
| Application-rendered facts | `emporio/agent_render.py`, `emporio/agent_tools.py` | `tests/test_rendered_facts_contract.py`, `tests/test_order_facts_contract.py` | [requirements](docs/requirements.md) |
| Output checks | `emporio/agent_consistency.py`, `emporio/agent_availability.py` | `tests/test_critical_claims_contract.py`, `tests/test_claim_binding_contract.py`, `tests/test_claim_scope_contract.py`, `tests/test_return_eligibility_contract.py` | [requirements](docs/requirements.md) (§4.1, §6.2) |
| JSON-only reply protocol | `emporio/agent_protocol.py`, `emporio/chat/cloudflare_reply.py` | `tests/test_terminal_protocol_contract.py`, `tests/test_cloudflare_gemma_protocol_contract.py` | [interfaces](docs/interfaces.md) |
| Rejection feedback | `emporio/agent_feedback.py` | `tests/test_rejection_feedback_contract.py` | [validation](docs/validation.md) |
| Evaluator | `emporio/model_evaluation.py`, `emporio/evaluation_claims.py`, `emporio/evaluation_dimensions.py` | `tests/test_evaluator_dimensions_contract.py`, `tests/test_evaluator_outcomes_contract.py`, `tests/test_evaluator_uncertainty_contract.py` | [validation](docs/validation.md) |
| Retrieval | `emporio/catalog/query.py`, `emporio/policy.py`, `emporio/policy_lookup.py` | `tests/test_catalog_wording_contract.py`, `tests/test_read_store_manual_contract.py` | [ADR-0005](docs/adr/0005-retrieval-refactoring.md) |
| Acceptance | — | — | [requirements](docs/requirements.md), [validation](docs/validation.md) |

[Requirements](docs/requirements.md) · [Interface contracts](docs/interfaces.md) · [Security review](docs/security-review.md) · [Recorded interactions (historical)](docs/interactions.md)
