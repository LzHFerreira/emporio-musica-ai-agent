# Empório da Música — AI Customer Service Agent

Empório da Música is a Python and Django customer-service agent for a fictional music store in Campo Grande, Brazil. It answers customer questions using catalog, order, and store-policy tools.

**Status:** The application runs locally, with automated checks covering data access, authorization, and message processing. Model answer quality remains under evaluation; see the recorded results and limitations below.

## Running the project

No programming experience is needed. Use Terminal on macOS or Linux, or PowerShell on Windows. Copy each command, paste it, and press Enter.

### 1. Install uv (one time)

`uv` installs the right Python version and every library the project needs.

- **macOS or Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Close the terminal and open a new one so the `uv` command is found.

### 2. Download the project

On the [GitHub page](https://github.com/LzHFerreira/emporio-musica-ai-agent), click **Code → Download ZIP**, extract it, and open a terminal in the extracted folder.

Alternatively, with Git installed:

```bash
git clone https://github.com/LzHFerreira/emporio-musica-ai-agent.git
cd emporio-musica-ai-agent
```

### 3. Set up the store data (one time)

Copy the example settings file to create `.env`:

- **macOS or Linux:** `cp .env.example .env`
- **Windows (PowerShell):** `Copy-Item .env.example .env`

Then run these commands to install the dependencies, create the database, and load the store data:

```bash
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py load_sources --source-dir data
```

The last command validates the six supplied CSV files and store policy PDF, then loads them into a local database.

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
| Ollama | `qwen3:4b` is the configured local starting point; no provider token charge. | Set `MODEL_PROVIDER=ollama`, `OLLAMA_BASE_URL`, and `OLLAMA_MODEL`; install and run the model locally. `OLLAMA_TIMEOUT_SECONDS` (default 180) allows for slower local prompt processing; cloud providers keep 60 s. On slow hardware also raise `TURN_DEADLINE_SECONDS` (default 60, the WhatsApp reply target). Compute, electricity, storage and speed depend on the host. The [recorded conversations](docs/interactions.md) used `qwen3.5:9b` on a Ryzen 5 8600G with integrated graphics at 10–70 s per request; this is not a quality or hardware guarantee. [Ollama API](https://docs.ollama.com/api/openai-compatibility) · [local evidence](docs/model-capability.md#local-ollama-2026-11-03) |
| OpenRouter | Existing explicit adapter; model and price depend on the selected route. | Set `MODEL_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. Only a route ending in `:free` is selectable without `ALLOW_PAID_MODELS=true`. The previously probed `google/gemma-4-26b-a4b-it:free` returned HTTP 429 before inference; a `:free` route is not a guaranteed entitlement. [OpenRouter model catalog](https://openrouter.ai/api/v1/models) · [probe evidence](docs/model-capability.md) |

Token prices were checked on 2026-11-03 and can change. Costs are per million input/output tokens; caching, long context, account plan and other provider charges may change the total. Cloudflare free use consumes a daily neuron quota, not a fixed number of tokens. These prices do not predict answer quality. A two-request Gemma probe on Cloudflare returned HTTP 200 with 4.33 estimated neurons; it does not qualify a customer workflow. No live OpenAI or Anthropic probe was run. Historical OpenRouter and Ollama probes are also narrow; the later `qwen3.5:9b` recordings cover five conversations on one host. [Validation](docs/validation.md) separates interface implementation from provider and answer-quality qualification.

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

Omit `--message` for interactive input until `/quit` or EOF. The selected model receives each turn through signed local ingress, a persistent worker and bounded tools. A local Meta mock accepts the reply; nothing is sent to Meta. The CLI uses a synthetic sender unless `--sender` gives a customer's WhatsApp digits (for example `5567996547821`, synthetic customer 2), which scopes order lookups to that customer. It is not the complete operator interface.

To exercise the application without a model service:

```bash
uv run --env-file .env python manage.py demo_chat
```

This scripted demo exercises actual source lookups, pricing, worker processing and simulated delivery. Its report identifies `model_mode: "scripted"`. The [recorded conversations](docs/interactions.md) are live model output, not this demo.

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
| Bounded Python tool loop | Four allowlisted tools cover catalog, public policy and owned orders. At most three model requests and four tool executions per turn; terminal JSON is validated, and a plain-text final reply counts as an answer that passes the same evidence checks. No agent framework or model-generated SQL is needed. |
| Deterministic business calculations | Application code computes prices, promotion/PIX rules and availability. Budget filtering uses supported payable prices before pagination. The model cannot invent a trusted price or customer identity. |
| Reviewed lexical policy retrieval | pypdfium2 extracts the small manual in-process (no system install); reviewed public passages retain page/section provenance. This avoids an embedding service, but unfamiliar phrasing can miss relevant evidence and needs independent evaluation. I considered exactly the alternative from the start: extracting the whole manual with pdfplumber and letting the model read it, with no pre-indexing. I first decided against it because sending the whole manual on every request seemed too blunt and costly; live probes have since shown that maintaining the lexical index costs more than the roughly 5k extra input tokens per request, and [ADR-0005](docs/adr/0005-retrieval-refactoring.md) proposes that switch. A first step, `read_store_manual`, returns every reviewed public passage with provenance; internal sections stay withheld. |
| Explicit model configuration | Cloudflare Workers AI, OpenAI, Anthropic, OpenRouter and local Ollama have explicit adapters. Provider/model selection is fixed per app request; there is no automatic fallback. Protocol support and mocked tests do not establish live acceptance or answer quality. |
| Application-owned history and access | Accepted history is bounded and revalidated. Authenticated sender matching and order ownership stay outside the model; structured preference/candidate replay is incomplete. |

The main path is customer text → local signed webhook → durable job → model/tool loop → checked reply → mock acceptance/delivery. [Interfaces](docs/interfaces.md) distinguishes implemented behavior from full acceptance targets.

The prompt asks for friendly, informal, professional Portuguese; appropriate catalog/policy consultation; brief clarification; and polite redirection outside store scope. Retrieved text is evidence, not instructions. Historical prices, stock and policies must be queried again before reuse. Prompts supplement application controls; selected lexical/numeric output checks do not prove arbitrary prose truthful.

The six CSVs and policy PDF remain canonical. SQLite contains derived business snapshots and authoritative application conversation state. Protected publication binds source files, reviewed passages and calculated prices to a version; rollback restores a retained compatible bundle. See [data access](docs/data-access.md) and the ADRs below.

### Synthetic-data assumption

The supplied datasets are treated as synthetic fixtures because the challenge describes a fictional store and requires a public repository. Credentials and runtime databases remain excluded. Authorization and minimization still apply; customer/model tools are read-only.

### Reasoning about incomplete or apparently conflicting sources

The [challenge, p. 3](desafio_tecnico_ai_eng_artefact.pdf#page=3), asks for reasonable interpretations when information is incomplete. I checked each rule against the [store policy](data/políticas_da_loja.pdf) and supplied records, then chose an explicit reading so I could proceed.

For installments, I treated [§3.1, p. 3](data/políticas_da_loja.pdf#page=3) as a detailed expansion of §3's summary, applying its tiers rather than a universal R$100 minimum. I checked the below-R$50 exception: product 119 is the lowest-priced, and order 7 the smallest; both are R$159.90, or R$53.30 in three installments. The exception does not change current one-to-three-installment cases.

Orders 9, 16 and 18 have recorded terms below those tiers. I kept them as historical transactions; those terms do not establish what the store should offer for a new purchase.

I treated exchange and warranty as different protections, not a conflict: [§4.2, p. 4](data/políticas_da_loja.pdf#page=4) allows defect exchanges within 30 days of purchase; [§8.1, p. 7](data/políticas_da_loja.pdf#page=7) starts a 90-day warranty on receipt. After the exchange period, the policy points to the manufacturer, with store mediation on request; it gives no further mediation details.

I kept both numbers in their stated roles: [§7, p. 6](data/políticas_da_loja.pdf#page=6) names (67) 3321-4500 for primary WhatsApp support; [§1.2, p. 2](data/políticas_da_loja.pdf#page=2) lists (67) 3341-4444 as company phone/WhatsApp. I did not declare either number wrong.

I kept calculations and access decisions in the application: budget filtering uses the supported payable price; promotions do not stack with PIX; product status stays separate from stock quantity; and application context, not model input, establishes sender identity and order ownership. This ties prices to the actual offer and access to the sender established by the application.

I would argue with the store that orders of exactly R$500 should qualify for free delivery, giving customers and staff a clear rule and avoiding confusion.

For the resulting contracts and validation evidence, see [requirements and acceptance coverage](docs/requirements.md#data-and-policy-findings) and [validation](docs/validation.md).

## Testing and evaluation

```bash
uv run --locked pytest
uv run --env-file .env python manage.py evaluate_retrieval
```

The tests exercise SQLite services, ownership, staff permissions, source publication/rollback, ingress, worker behavior and simulated delivery/recovery. Coverage must reach 95%. Provider responses in these tests are mocked. The eleven-case retrieval set was inspected during implementation; it is regression coverage rather than an independent generalization test.

```bash
uv run --env-file .env python manage.py evaluate_model --runs 3
```

This sends the nine development questions in `tests/fixtures/model_quality.json` to the configured live model and prints a JSON pass-rate report with every reply; it consumes provider quota. Pass/fail uses substring checks against source data, so review non-passing replies manually.

```bash
bash scripts/run_quality_gates.sh
```

This also checks formatting, lint, types, docstrings, dependency boundaries, complexity/size, Django and migration drift. Semgrep Pro requires its external rules/engine and appropriate access; a failed or unavailable scan is not a pass. [Validation](docs/validation.md) records the latest outcomes and the exact scope of fresh-environment checks.

## Known limitations

- Live model evidence is small: five single-turn development questions on cloud models (GLM-4.7 Flash 13/15, Gemma 4 11/15, before the four probe cases were added) and five recorded two-turn conversations on a local model. Independently written paraphrases remain required.
- Output checks catch known kinds of error, not general falsehood. They bind numbers to units (so "7 anos" fails where the manual says "7 dias"), prices to products, and addresses and contacts to evidence; they reject a fixed list of absolute and praise phrases ("vitalícia", "qualquer valor", "bem avaliado") and opening on closed days unless the evidence says so. Other unsupported descriptive claims, wrong conditions phrased in new words, and omitted eligibility rules can still pass, so an accepted reply is not proof of correctness. A reply can also omit results beyond the first page of five without saying so.
- Policy retrieval is lexical and hand-tuned; common phrasings were added, but unseen inflections and synonyms can still miss. See [ADR-0005](docs/adr/0005-retrieval-refactoring.md).
- A small local model sometimes fails the three-request turn budget and returns the fixed safe-failure reply (1 of 10 recorded turns).
- Operator inbox/reply/release controls, structured conversation context and some resource/deadline/concurrency acceptance remain unfinished. Handoff state does not establish a live human transfer.
- Live Meta onboarding/delivery, deployment hardening, retention operations and physical power-loss durability have not been established.

## Development roadmap

1. **Qualify the model:** done for five single-turn development questions on GLM-4.7 Flash (13/15). Five multi-turn conversations are recorded on a local model; new paraphrases and a cloud run of the four probe cases remain.
2. **Correct answers:** establish failing tests for known grounding/retrieval errors, implement focused fixes, then evaluate fresh paraphrases and policy conditions.
3. **Complete conversations:** demonstrate retained preferences, ambiguous references, missing eligibility, owned-order boundaries and useful partial/failure responses with the actual model.
4. **Finish challenge evidence:** done for five live recorded conversations; reproduce setup from the submitted checkout. Tie validation to the reviewed code and preserve meaningful commits.
5. **Close extension acceptance:** finish declared operator controls, staff usability and remaining resource/concurrency checks separately. Preserve the existing staff and transport implementation.

Live Meta remains outside challenge acceptance. Additional provider or infrastructure work should follow evidence from the core customer-agent gates, not replace them.

## Development context

I built most of this project during the Dia de Finados holiday (2 November), while my two daughters were home until school resumed on 4 November. I worked in short, interrupted sessions and did not commit as I went. The result was `8b0090e` (3 November): 21,116 changed lines across 246 files in one commit, which is hard to review. That was a process failure on my part, not a design choice.

On 4 November, I moved to smaller, test-first changes and reviewed them individually. The remaining gaps stay visible in [Known limitations](#known-limitations).

## AI-assisted development

I used Codex throughout requirements analysis, implementation, tests, documentation and review. I set customer scenarios and acceptance criteria, checked recommendations against the supplied sources and executable behavior, and decided which changes to keep. I reviewed and approved the work; I remain responsible for the submitted result and its limitations.

During the final model-quality phase, I used Claude Code with Claude Opus 5.5 coordinating and reviewing, and Claude Haiku 5.5 subagents handling tests, implementation, investigations and live validation. GPT-6 Luna was unavailable in that environment. For that phase, I required separate test and implementation agents: one established a focused failure, another made the change, and the coordinator reviewed the diff and checks before I approved it.

Those reviews caught concrete mistakes before acceptance: a proposed newline split would have allowed swapped product prices; tests passed for the wrong reason when they omitted catalog or policy sources; validation ground truth missed parts of the policy; and an earlier change caused a Radon complexity regression. I checked those findings against the sources and executable behavior before approving the changes.

## Architecture decisions

- [ADR-0001: SQLite through Django ORM](docs/adr/0001-use-sqlite-for-structured-data.md)
- [ADR-0002: PDF ingestion and policy retrieval](docs/adr/0002-pdf-ingestion-and-retrieval.md)
- [ADR-0003: Protected source maintenance and rollback](docs/adr/0003-protected-source-maintenance.md)
- [ADR-0004: Explicit model selection and provider compatibility](docs/adr/0004-free-model-and-provider-fallbacks.md)
- [ADR-0005: Retrieval refactoring (proposed)](docs/adr/0005-retrieval-refactoring.md)

[Requirements](docs/requirements.md) · [Interface contracts](docs/interfaces.md) · [Security review](docs/security-review.md) · [Recorded interactions](docs/interactions.md)
