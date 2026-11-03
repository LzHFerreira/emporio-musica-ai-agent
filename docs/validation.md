# Local validation record

Updated: 2026-11-03. This records local evidence for the synthetic-data implementation. It is not full challenge acceptance, live-provider qualification or production certification. Requirements remain in [requirements](requirements.md); workflow contracts are in [interfaces](interfaces.md).

## Implemented and exercised

- Signed local ingress, persistent worker, bounded tools, source-pinned catalog/policy reads, owned-order filtering and Meta HTTP client are exercised together using synthetic fixtures. `demo_chat` records five scripted interactions; scripted output is not model-quality evidence. `interact_chat` routes evaluator text through the local signed webhook, worker/tools and mock Meta boundary.
- Targeted integration cases cover signatures, scope, batches/deduplication, takeover, malformed inputs, minimization, ownership, stale authorization/source checks, acceptance, callbacks and uncertain sends. Full operator controls and all acceptance scenarios remain incomplete; see [interfaces](interfaces.md).
- The fixed 11-case retrieval set reports precision, recall and required-condition coverage 1.0, with no irrelevant or non-public results. Paraphrases were inspected during implementation, so this is regression evidence, not an independent generalization test. The recorded p95 applies only to that run ([results](retrieval-evaluation.json)).
- Source publication subprocess tests terminate after staging, during activation before commit, and after commit. A fresh process checks pointer, audit, hashes, policy provenance and pricing. This covers process termination, not physical power loss.
- Recovery tests cover pending deadlines, interrupted work, uncertain sends and accepted replies awaiting callbacks. Broad concurrent contention and every lease timing remain unverified.
- Targeted security tests support the findings in [security review](security-review.md); they are not a penetration test or proof about arbitrary prose.

## Model/provider evidence

On 2026-11-03, after the output-guard and retry fixes, five single-turn development questions (catalog price, PIX nylon budget, availability with returns, Saturday hours, out-of-scope) were each run three times through `run_turn` with live Cloudflare models. GLM-4.7 Flash passed 14 of 15; its single miss was the fixed failure reply. Gemma 4 passed 7 of 15; all misses were fixed safe replies, and some passing replies contained stray formatting artifacts. Pass/fail used substring checks against the source data, with each non-pass reviewed manually. These questions were inspected during development, so the result is regression evidence, not an independent paraphrase evaluation.

On 2026-11-03, an earlier two-request synthetic Cloudflare Gemma probe returned HTTP 200 with 4.33 estimated neurons. That narrow route probe does not qualify the tool loop, customer workflow, or answer quality. A later three-request app attempt returned HTTP 200 but repeatedly called `search_catalog` without a query and did not use the private reply-control function. After the Gemma-only query requirement was added, the final bounded app probe sent two requests; both returned HTTP 200, and the model requested the Takamine GD20 catalog data, looked up policy, then invoked the private reply-control function. The application still persisted its fixed failure reply, which the Meta mock accepted. The retained diagnostic omits the control arguments and raw response, so it does not show whether the terminal parser or evidence guard ran; the cause is unresolved. No full model workflow passed. OpenAI and Anthropic received no live probes.

Offline provider contracts cover Cloudflare, OpenAI Responses/Chat Completions, Anthropic Messages and native MCP stdio, including mocked wire behavior, credential isolation, Gemma terminal reply validation, four-tool MCP registration, trusted sender scope, per-call source dispatch, bounded results and clean EOF. A signed two-turn Gemma callback test completed catalog and policy lookups with a structured terminal response using mocked provider HTTP and the Meta mock. These offline checks establish application serialization and plumbing, not live model behavior or answer quality.

Historical OpenRouter requests received HTTP 429 before completion; local Ollama produced one greeting but a policy turn missed the work cutoff. A separate incomplete Groq experiment contains three prepared-evidence case records, with no application retrieval or Groq adapter. None qualifies the complete customer workflow. Preserve these distinct scopes when interpreting the [model capability record](model-capability.md) and [ADR-0004](adr/0004-free-model-and-provider-fallbacks.md).

## Automated checks

The final full suite on 2026-11-03 passed: **354 tests, 95.39% coverage** across 5,167 statements, with seven SQLite `ResourceWarning`s for unclosed database connections reported through Django internals. Loopback access was enabled for local transport tests. Provider responses in automated contracts are mocked; these results do not qualify generated answers or live Meta compatibility.

Final static checks passed: Ruff format/lint, ty, basedpyright (zero errors/warnings/notes), mypy (115 files), pydoclint, import-linter (164 files, 506 dependencies), code-size/Radon (193 Python files), Django checks, migration consistency, offline `uv` lock check, and `git diff --check`. Semgrep Pro passed with exit 0: 134 targets scanned, 1,201 rules run, zero findings (zero blocking), and 78 ignored files. The scan covered `manage.py` and Python/shell sources under `emporio/`, `scripts/` and `tests/`. An earlier attempt was blocked by automatic approval review pending source-export authorization; the user later authorized the scoped scan. The result does not cover ignored files or establish full challenge acceptance.

Configuration tests cover current-user role/schema isolation, safe `.env` defaults and subprocess environment behavior, not actual model compliance. The final documentation pass checked local paths and heading anchors across all 15 Markdown files successfully. Earlier table/fence and conversation/JSON checks remain historical evidence. A limited credential-pattern scan of 239 candidate files found no matches; ignored credentials, database and cache paths were excluded from the candidate snapshot.

## Isolated candidate snapshot

Earlier cleanup snapshot: 239 tracked/untracked, nonignored candidate files were copied into a temporary directory, excluding `.env`, virtual environment and runtime state. Using the then-installed dependencies and a fresh SQLite database, migrations, complete canonical-source import, all 11 retrieval regression cases, staff login/source index (HTTP 200) and five scripted conversations with mock acceptance/delivery passed. The active source version matched the recorded demonstration. This snapshot predates the provider/MCP feature and latest live Cloudflare application probe; it is not a clean-checkout validation of the current tree.

That earlier run establishes fresh-file/fresh-database execution for its copied candidate with existing dependencies, not a clean dependency installation or current Git checkout. The latest Cloudflare application probe is separately recorded above. A clean-install review remains part of final submission acceptance.

## Not established

Core challenge acceptance remains open: complete actual-model conversations, independently evaluated answer quality and known grounding/retrieval fixes need evidence. Separately, unfinished project extensions include full operator controls, structured preferences/candidates, after-hours/holiday behavior, some rate/queue/token/time ceilings and concurrency schedules. Model HTTP wall-time clipping and checks around counter writes are tested. Live Meta, deployment hardening, retention operations and physical power-loss behavior remain unverified.

## Submission priorities

Follow the [README delivery order](../README.md#development-roadmap): qualify the actual model, correct grounding/retrieval, demonstrate complete conversations and reproduce setup before expanding infrastructure. Existing staff/transport extensions remain available with their acceptance gaps explicit.
Review probes still accept unsupported Sunday opening and shipped-order claims, plus an unsupported warranty embedded in a clarification. The prior policy review also found missed defect, warranty and pickup evidence; these need focused regression tests and fixes, not a claim of complete grounding from high coverage.
The next submission evidence must include real model conversations and fresh paraphrases. Scripted examples and prepared-evidence provider experiments remain useful component evidence, not substitutes for that acceptance gate.
