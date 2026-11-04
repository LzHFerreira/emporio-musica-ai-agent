# Empório da Música — AI Customer Service Agent

Python customer-service prototype for the fictional Empório da Música in Campo Grande/MS, built for the [Artefact AI Engineer challenge](desafio_tecnico_ai_eng_artefact.pdf).

**Status:** the local application and deterministic integration tests work. With the default Cloudflare model, GLM-4.7 Flash, five single-turn development questions passed 13 of 15 live runs through the full agent and output checks; Gemma 4 passed 11 of 15; every miss but one was a fixed safe reply, and no passing reply stated a wrong fact. These questions were used during development, so they are regression evidence, not an independent evaluation. Recorded multi-turn conversations remain open. See [validation](docs/validation.md).

## Running the project

No programming experience is needed. You will type a few commands into a terminal: **Terminal** on macOS or Linux, **PowerShell** on Windows (press the Windows key, type `PowerShell`, press Enter). Copy each command, paste it, and press Enter.

### 1. Install uv (one time)

`uv` installs the right Python version and every library the project needs.

- **macOS or Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Close the terminal and open a new one so the `uv` command is found.

### 2. Download the project

On the [GitHub page](https://github.com/LzHFerreira/emporio-musica-ai-agent), click **Code → Download ZIP**, unzip it, then open a terminal in the unzipped folder. (With Git installed: `git clone https://github.com/LzHFerreira/emporio-musica-ai-agent.git` and `cd emporio-musica-ai-agent`.)

### 3. Set up the store data (one time)

Create your settings file:

- **macOS or Linux:** `cp .env.example .env`
- **Windows (PowerShell):** `Copy-Item .env.example .env`

Then run these three commands. The first may take a minute while it downloads Python and the libraries:

```bash
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py load_sources --source-dir data
```

The last command checks the six spreadsheets and the store policy PDF in `data/` and loads them into a local database.

### 4. Try the demo (no account needed)

```bash
uv run --env-file .env python manage.py demo_chat
```

This runs five sample customer questions through the real store data with a scripted model and prints the answers. Seeing `"accepted_count": 5` means everything is installed correctly.

### 5. Talk to the AI assistant (free Cloudflare account)

1. Create a free account at [dash.cloudflare.com](https://dash.cloudflare.com/sign-up).
2. In the left menu, open **AI → Workers AI** and choose **Use REST API**. Copy your **Account ID**, then click **Create a Workers AI API Token** and copy the token.
3. Open the `.env` file in any text editor (Notepad works) and fill in the two lines:
   ```
   CLOUDFLARE_ACCOUNT_ID=paste-your-account-id
   CLOUDFLARE_API_TOKEN=paste-your-token
   ```
4. Ask a question:
   ```bash
   uv run --env-file .env python manage.py interact_chat
   ```
   Type questions in Portuguese, such as `Quanto custa o Takamine GD20?`, and type `/quit` to leave.

The free plan includes a daily allowance; the default model, GLM-4.7 Flash, is on Cloudflare's free-eligible list, and the app refuses paid models unless you opt in. Keep `.env` private: it contains your token.

### If something goes wrong

| Message | Fix |
| --- | --- |
| `uv: command not found` or `uv is not recognized` | Open a new terminal after step 1, or repeat step 1. |
| `no such table` or an empty catalog | Run the two commands from step 3 that start with `uv run`. |
| `Set a valid CLOUDFLARE_ACCOUNT_ID` or `Set CLOUDFLARE_API_KEY` | Check both lines in `.env` from step 5, with no spaces around `=`. |
| `Não consegui concluir sua consulta agora…` | The model did not produce a checked answer or the daily quota ran out; try again or later. |

### Other model providers (advanced)

Source import validates all six CSVs and the policy PDF before activating one snapshot. No Meta credentials are needed for the local harness. Default webhook credentials are local test values, unsuitable for deployment.

Choose one provider in `.env` before model interaction. The complete variable template is in [.env.example](.env.example). `MODEL_PROVIDER` defaults to `cloudflare`; selection is explicit and errors never switch providers. Cloud inference requires a provider account and credential. `ALLOW_PAID_MODELS` must be `true` for OpenAI or Anthropic, non-free OpenRouter routes, and Cloudflare models outside the reviewed free-model list. This application guard does not guarantee that an account incurs no charges: quota, account plan, route eligibility and provider billing controls remain external.

| Provider | Default model and cost per 1M input/output tokens (USD) | Setup and billing |
| --- | --- | --- |
| Cloudflare Workers AI (default) | Reviewed free-eligible `@cf/zai-org/glm-4.7-flash` — $0.0605 / $0.40 (default; 13/15 live development runs). `@cf/google/gemma-4-26b-a4b-it` — $0.10 / $0.30 (alternative; 11/15). | Set `MODEL_PROVIDER=cloudflare`, `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_KEY` (or `CLOUDFLARE_API_TOKEN`); optionally set `CLOUDFLARE_MODEL`. These two model IDs are the reviewed free-eligible list. Selecting a model outside it requires `ALLOW_PAID_MODELS=true`; the flag accepts cost risk, not model quality. The direct Gemma adapter adds a private `respond_to_customer` function so its final reply uses the app's structured terminal parser; this function is not a catalog or MCP tool. For Gemma requests, `search_catalog.query` is required; use an empty string only for general browsing. Gemma's Wrangler guide documents disabling thinking with `enable_thinking=false`. Workers AI has a 10,000 Neurons/day free allocation; exceeding it on Workers Free stops requests, while paid usage is billed. Availability is account- and quota-dependent. [Gemma pricing](https://developers.cloudflare.com/ai/models/%40cf/google/gemma-4-26b-a4b-it/) · [GLM pricing](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/) · [disable thinking](https://developers.cloudflare.com/workers-ai/get-started/workers-wrangler/) · [plan and quota](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| OpenAI | `gpt-6-luna` — $0.10 / $0.50. | Set `MODEL_PROVIDER=openai`, `ALLOW_PAID_MODELS=true` and `OPENAI_API_KEY`; optionally set `OPENAI_MODEL`, `OPENAI_API_MODE` (`responses` by default), and `OPENAI_REASONING_EFFORT` (unset by default). When unset, Responses omits the reasoning parameter. `chat_completions` forces `reasoning_effort=none` for GPT-6 Luna compatibility. API billing is separate from ChatGPT subscriptions. [Model, endpoints and price](https://developers.openai.com/api/docs/models/gpt-6-luna) · [API pricing](https://developers.openai.com/api/docs/pricing) · [billing separation](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform) |
| Anthropic | `claude-haiku-5-5` — $0.10 / $0.50 for prompts up to 100k tokens; $0.50 / $2.50 above 100k. Optional higher-cost alternative: Claude Sonnet 5.5 — $2 / $10. | Set `MODEL_PROVIDER=anthropic`, `ALLOW_PAID_MODELS=true` and `ANTHROPIC_API_KEY`; optionally set `ANTHROPIC_MODEL`. API billing is usage-based. [Model IDs and pricing](https://platform.claude.com/docs/en/models/haiku-5-5/overview) · [all model prices](https://platform.claude.com/docs/en/about-claude/pricing) |
| Ollama | `qwen3:4b` is the configured local starting point; no provider token charge. | Set `MODEL_PROVIDER=ollama`, `OLLAMA_BASE_URL`, and `OLLAMA_MODEL`; install and run the model locally. `OLLAMA_TIMEOUT_SECONDS` (default 180) allows for slower local prompt processing; cloud providers keep 60 s. Compute, electricity, storage and speed depend on the host. A local probe succeeded for one greeting but missed the policy-turn deadline; this is not a quality or hardware guarantee. [Ollama API](https://docs.ollama.com/api/openai-compatibility) · [local evidence](docs/model-capability.md#local-ollama-2026-11-03) |
| OpenRouter | Existing explicit adapter; model and price depend on the selected route. | Set `MODEL_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. Only a route ending in `:free` is selectable without `ALLOW_PAID_MODELS=true`. The previously probed `google/gemma-4-26b-a4b-it:free` returned HTTP 429 before inference; a `:free` route is not a guaranteed entitlement. [OpenRouter model catalog](https://openrouter.ai/api/v1/models) · [probe evidence](docs/model-capability.md) |

Token prices were checked on 2026-11-03 and can change. Costs are per million input/output tokens; caching, long context, account plan and other provider charges may change the total. Cloudflare free use consumes a daily neuron quota, not a fixed number of tokens. These prices do not predict answer quality. A two-request Gemma probe on Cloudflare returned HTTP 200 with 4.33 estimated neurons; it does not qualify a customer workflow. No live OpenAI or Anthropic probe was run. Historical OpenRouter and Ollama probes are also narrow and do not qualify a full customer workflow. [Validation](docs/validation.md) separates interface implementation from provider and answer-quality qualification.

### MCP tools

To expose the four existing catalog, public-policy and owned-order tools to an MCP client, run:

```bash
uv run --env-file .env python manage.py mcp_server
```

This starts a local stdio server using the locked `mcp==1.30.0` SDK. In the MCP client configuration, run the command from the repository root. The client chooses its own model and connects that model to these tools; this command does not route inference through the app's model-provider selection. The optional `EMPORIO_MCP_SENDER` is trusted server configuration for the two owned-order tools. If it is unset, those tools return a generic denial. A client or model argument cannot set or impersonate the sender. Each tool call uses the currently active source bundle, and successful results report `bundle_version`; compare that value before combining separate results. The four tools use existing application authorization and source checks; see [interfaces](docs/interfaces.md#mcp-server).

Plain Python does not load `.env`; the commands use `uv --env-file` to supply process environment variables. Child processes may inherit them. Keep `.env` private. `EMPORIO_DB_PATH` selects the SQLite file; use a fresh path for an isolated database.

### Customer interaction

```bash
uv run --env-file .env python manage.py interact_chat --message "Quanto custa o Takamine GD20?"
```

Omit `--message` for interactive input until `/quit` or EOF. The selected model receives each turn through signed local ingress, a persistent worker and bounded tools. A local Meta mock accepts the reply; nothing is sent to Meta. The CLI uses a synthetic sender and is not the complete operator interface.

To exercise the application without a model service:

```bash
uv run --env-file .env python manage.py demo_chat
```

This scripted demo exercises actual source lookups, pricing, worker processing and simulated delivery. Its report identifies `model_mode: "scripted"`. The [five recorded conversations](docs/interactions.md) are integration fixtures; they do not satisfy the remaining real-model evidence gate.

### Staff source maintenance

```bash
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
```

Sign in at `http://127.0.0.1:8000/accounts/login/`, then open `/equipe/fontes/`. Staff can stage, preview, publish and roll back CSV/PDF sources. Superusers have all permissions; ordinary staff need the [documented source grants](docs/interfaces.md#staff-source-maintenance). PDF passage review currently requires JSON input, a known usability limitation.

Run one worker-backed CLI command at a time against a database. A separate process may need to wait five seconds for the singleton lease to expire after the preceding command.

## Technical approach

The challenge permits a CLI and requires Python. WhatsApp simulation, durable messaging and protected source maintenance are project extensions. They remain available, while completion work prioritizes the customer agent.

| Decision | Reason and tradeoff |
| --- | --- |
| Django 5.2 and SQLite | Django supplies authentication, CSRF, migrations and staff pages; SQLite supports relational queries and local state without a database service. This is more infrastructure than a minimal CLI needs; broad write contention remains unqualified. |
| Bounded Python tool loop | Four allowlisted tools cover catalog, public policy and owned orders. At most three model requests and four tool executions per turn; terminal JSON is validated. No agent framework or model-generated SQL is needed. |
| Deterministic business calculations | Application code computes prices, promotion/PIX rules and availability. Budget filtering uses supported payable prices before pagination. The model cannot invent a trusted price or customer identity. |
| Reviewed lexical policy retrieval | pypdfium2 extracts the small manual in-process (no system install); reviewed public passages retain page/section provenance. This avoids an embedding service, but unfamiliar phrasing can miss relevant evidence and needs independent evaluation. I considered exactly the alternative from the start: extracting the whole manual with pdfplumber and letting the model read it, with no pre-indexing. I first decided against it because sending the whole manual on every request seemed too blunt and costly; live probes have since shown that maintaining the lexical index costs more than the roughly 5k extra input tokens per request, and [ADR-0005](docs/adr/0005-retrieval-refactoring.md) proposes that switch. |
| Explicit model configuration | Cloudflare Workers AI, OpenAI, Anthropic, OpenRouter and local Ollama have explicit adapters. Provider/model selection is fixed per app request; there is no automatic fallback. Protocol support and mocked tests do not establish live acceptance or answer quality. |
| Application-owned history and access | Accepted history is bounded and revalidated. Authenticated sender matching and order ownership stay outside the model; structured preference/candidate replay is incomplete. |

The main path is customer text → local signed webhook → durable job → model/tool loop → checked reply → mock acceptance/delivery. [Interfaces](docs/interfaces.md) distinguishes implemented behavior from full acceptance targets.

The prompt asks for friendly, informal, professional Portuguese; appropriate catalog/policy consultation; brief clarification; and polite redirection outside store scope. Retrieved text is evidence, not instructions. Historical prices, stock and policies must be queried again before reuse. Prompts supplement application controls; selected lexical/numeric output checks do not prove arbitrary prose truthful.

The six CSVs and policy PDF remain canonical. SQLite contains derived business snapshots and authoritative application conversation state. Protected publication binds source files, reviewed passages and calculated prices to a version; rollback restores a retained compatible bundle. See [data access](docs/data-access.md) and the ADRs below.

### Synthetic-data assumption

The supplied datasets are treated as synthetic fixtures because the challenge describes a fictional store and requires a public repository. Credentials and runtime databases remain excluded. Authorization and minimization still apply; customer/model tools are read-only.

### Reasoning about incomplete or apparently conflicting sources

The [challenge, p. 3](desafio_tecnico_ai_eng_artefact.pdf#page=3), asks for reasonable interpretations, documented assumptions and continued progress when information is incomplete. My approach is to check each rule's scope and the supplied data, record a justified decision, and seek clarification only when the remaining gap affects the answer.

| Case | Reasoning and project decision |
| --- | --- |
| Installments | [§3.1, p. 3](data/políticas_da_loja.pdf#page=3) expands §3's summary: apply its tiers rather than a universal R$100 minimum. The below-R$50 exception does not affect current 1–3 installment scenarios: the cheapest product, including active promotions, and the smallest order are R$159.90, or 3 × R$53.30. |
| Historical payment terms | Orders 9, 16 and 18 fall below §3.1's tier minimums. Preserve these canonical historical records and report administrative warnings when structural validation passes. Their recorded terms do not justify equivalent new installment offers. |
| Exchanges and warranty | [§4.2, p. 4](data/políticas_da_loja.pdf#page=4) allows defect exchanges within 30 days of purchase; [§8.1, p. 7](data/políticas_da_loja.pdf#page=7) describes a 90-day warranty from receipt. Different remedies and start dates do not establish a contradiction. Explain the stated post-exchange route—manufacturer contact, with store mediation on request—and clarify unspecified mediation details only when needed. |
| Contact numbers | Use [§7, p. 6](data/políticas_da_loja.pdf#page=6)'s (67) 3321-4500 as primary WhatsApp support, with failed customer matching routed to a human within the conversation. Retain [§1.2, p. 2](data/políticas_da_loja.pdf#page=2)'s (67) 3341-4444 as the listed company telephone/WhatsApp contact. Their stated roles support this mapping without treating either number as invalid. |
| Metropolitan delivery | [§5.1, p. 4](data/políticas_da_loja.pdf#page=4) specifies R$35 below R$500 and free delivery above it. Equality is omitted, not contradicted. No recorded order or combination of supplied product prices reaches exactly R$500, including active promotions and permitted PIX discounts, so this gap does not block current scenarios. In a real-world scenario, to avoid confusion with customer and staff, I would argue with the store that the equality should be included and treat the case as free delivery. |

These are project interpretations of supplied sources, not legal conclusions or claims of live business validation. Recheck the data-dependent conclusions when canonical data or discount rules change. [Requirements and acceptance coverage](docs/requirements.md#data-and-policy-findings) define the resulting behavior. Installment and PIX pricing are implemented and covered by automated tests, and live-model runs now provide regression evidence (see [validation](docs/validation.md)); behavioral validation of the remaining interpretations stays partial.

## Testing and evaluation

```bash
uv run --locked pytest
uv run --env-file .env python manage.py evaluate_retrieval
```

The tests exercise SQLite services, ownership, staff permissions, source publication/rollback, ingress, worker behavior and simulated delivery/recovery. Coverage must reach 95%. Provider responses in these tests are mocked. The eleven-case retrieval set was inspected during implementation; it is regression coverage rather than an independent generalization test.

```bash
uv run --env-file .env python manage.py evaluate_model --runs 3
```

This sends the five development questions in `tests/fixtures/model_quality.json` to the configured live model and prints a JSON pass-rate report with every reply; it consumes provider quota. Pass/fail uses substring checks against source data, so review non-passing replies manually.

```bash
bash scripts/run_quality_gates.sh
```

This also checks formatting, lint, types, docstrings, dependency boundaries, complexity/size, Django and migration drift. Semgrep Pro requires its external rules/engine and appropriate access; a failed or unavailable scan is not a pass. [Validation](docs/validation.md) records the latest outcomes and the exact scope of fresh-environment checks.

## Known limitations

- Live model evidence covers five single-turn development questions (GLM-4.7 Flash 13/15, Gemma 4 11/15). Recorded multi-turn conversations and independently written paraphrases remain required.
- Output checks now reject factual replies with no tool evidence, but a reply backed by some evidence can still state something that evidence does not support. Retrieval misses inflections, synonyms and catalog queries containing stop words; see [ADR-0005](docs/adr/0005-retrieval-refactoring.md). These are product blockers, despite high test coverage.
- Operator inbox/reply/release controls, structured conversation context and some resource/deadline/concurrency acceptance remain unfinished. Handoff state does not establish a live human transfer.
- Live Meta onboarding/delivery, deployment hardening, retention operations and physical power-loss durability have not been established.

## Development roadmap

1. **Qualify the model:** done for five single-turn development questions on GLM-4.7 Flash (13/15). Extend to multi-turn conversations and new paraphrases.
2. **Correct answers:** establish failing tests for known grounding/retrieval errors, implement focused fixes, then evaluate fresh paraphrases and policy conditions.
3. **Complete conversations:** demonstrate retained preferences, ambiguous references, missing eligibility, owned-order boundaries and useful partial/failure responses with the actual model.
4. **Finish challenge evidence:** record three to five real conversations and reproduce setup from the submitted checkout. Tie validation to the reviewed code and preserve meaningful commits.
5. **Close extension acceptance:** finish declared operator controls, staff usability and remaining resource/concurrency checks separately. Preserve the existing staff and transport implementation.

Live Meta remains outside challenge acceptance. Additional provider or infrastructure work should follow evidence from the core customer-agent gates, not replace them.

## AI-assisted development

I used OpenAI Codex throughout requirements analysis, implementation, test generation, documentation and adversarial review. I directed the work by defining customer scenarios, setting acceptance criteria, comparing alternatives and deciding which changes to retain. I own the architecture, scope and submitted result, including the limitations documented here.

My decisions included evaluating recommendations against payable prices, keeping PIX discounts from stacking with promotions, distinguishing product status from stock quantity, and enforcing customer identity and order ownership outside the model. I challenged apparent policy contradictions against the original passages and supplied records before accepting an interpretation. These decisions shaped the application contracts and regression cases.

For executable changes, I required separate test and implementation agents: establish a failing focused test, implement the change, then verify the result. I requested independent reviews to expose weak assumptions and checked findings against source evidence and executable behavior. I treat generated proposals as material to evaluate, and report automated checks, scripted demonstrations and actual model results separately. [Validation](docs/validation.md) records the evidence and remaining gaps; I remain accountable for the submission's correctness.

The final model-quality phase used Claude Code with Claude Opus 5.5 as planner, coordinator and reviewer, and Claude Haiku 5.5 subagents at low reasoning effort for implementation, tests, investigations and live validation runs. GPT-6 Luna, the delegation model named first in my agent instructions, was not available in that environment. Each change followed the same sequence: a test agent wrote a focused test and confirmed it failed for the stated reason; a separate implementation agent made the smallest change; the coordinator reviewed the diff, reran the relevant checks and reported the results before I approved each commit. Batches were limited to 50 changed lines unless I approved more, as I did for the evaluator command. These commits carry a `Co-Authored-By: Claude Opus 5.5` trailer.

That phase started from the open gate that no configured model had completed a customer workflow. Live runs showed that most failures came from the harness rather than the models: strict terminal JSON parsing, an integer budget rejected by the tool schema, the customer's own budget treated as an unsupported number, list markers and multi-line lists breaking price-to-product binding, and discarded handoff text still being checked. The resulting changes extract the last terminal JSON object, retry rejected replies with corrective feedback, reject repetition loops, cut-off replies, leaked control tokens and English leaks, add a fixed out-of-scope reply, retry invalid Gemma terminal replies instead of failing, make GLM-4.7 Flash the default and add the reproducible `evaluate_model` command.

Review caught several agent errors before they were accepted: a proposed newline split that would have accepted swapped product prices, tests that passed for the wrong reason because they omitted catalog or policy sources, validation ground truth that left out parts of the policy PDF and misclassified correct answers, and a Radon complexity regression introduced by earlier commits. The five live evaluation questions were written and inspected during this work, so the reported pass rates (GLM-4.7 Flash 13/15, Gemma 4 11/15) are regression evidence. Independent paraphrases and recorded multi-turn conversations remain open.

## Architecture decisions

- [ADR-0001: SQLite through Django ORM](docs/adr/0001-use-sqlite-for-structured-data.md)
- [ADR-0002: PDF ingestion and policy retrieval](docs/adr/0002-pdf-ingestion-and-retrieval.md)
- [ADR-0003: Protected source maintenance and rollback](docs/adr/0003-protected-source-maintenance.md)
- [ADR-0004: Explicit model selection and provider compatibility](docs/adr/0004-free-model-and-provider-fallbacks.md)
- [ADR-0005: Retrieval refactoring (proposed)](docs/adr/0005-retrieval-refactoring.md)

[Requirements](docs/requirements.md) · [Interface contracts](docs/interfaces.md) · [Security review](docs/security-review.md) · [Recorded interactions](docs/interactions.md)
