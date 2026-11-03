# ADR-0004: Explicit model selection and provider compatibility

- Status: Accepted. Live qualification of the customer workflow remains open.
- Reviewed: 2026-11-03.

## Context

The original provider choices were OpenRouter and local Ollama. An OpenRouter request for `google/gemma-4-26b-a4b-it:free` returned HTTP 429 before inference. The Ollama setup returned one greeting but missed the work deadline on a policy turn. Neither probe established answer quality or completed workflow acceptance; see [model capability evidence](../model-capability.md).

The project now supports an explicit provider matrix for Cloudflare Workers AI, OpenAI, Anthropic, OpenRouter and local Ollama. The customer agent uses one provider and model per request. Provider compatibility is not permission to retry a failed request through another provider: routing changes data handling and billing, so errors do not trigger automatic fallback or share credentials.

## Decision

`MODEL_PROVIDER` defaults to `cloudflare`. Its default and recommended model is `@cf/google/gemma-4-26b-a4b-it`, accessed through the Cloudflare OpenAI-compatible chat-completions route. It requires `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_KEY` or `CLOUDFLARE_API_TOKEN`; `CLOUDFLARE_MODEL` can select another model. The reviewed free-eligible allowlist contains `@cf/google/gemma-4-26b-a4b-it` and `@cf/zai-org/glm-4.7-flash`. Gemma has one narrow HTTP probe; GLM has not completed customer-workflow qualification. Other model IDs require `ALLOW_PAID_MODELS=true` to acknowledge cost risk. This does not assert a charge or establish model quality: Cloudflare's account eligibility, plan and remaining daily neuron quota remain external and can change. Only the Gemma route adds the private `respond_to_customer` function alongside the four bounded business tools, with `tool_choice=required`; the application then validates the function arguments using its exact terminal parser and evidence guard. Its Gemma-only copy of the `search_catalog` schema requires a string query while allowing an empty string for general browsing; missing queries are rejected before tool execution. The private function has no lookup or order access and is not part of the public MCP schema. The documented Gemma `chat_template_kwargs.enable_thinking=false` setting is sent only for that exact model. A two-step synthetic HTTP probe returned 200 with an estimated 4.33 neurons. That narrow probe is not a completed customer workflow or answer-quality evaluation.

Other explicit choices:

| Provider | Model/API default | Configuration and boundary |
| --- | --- | --- |
| OpenAI | `gpt-6-luna`; Responses API | Requires `ALLOW_PAID_MODELS=true` and `OPENAI_API_KEY`. `OPENAI_REASONING_EFFORT` is optional and unset by default; Responses omits reasoning configuration when unset. `OPENAI_API_MODE=chat_completions` is also supported and forces `reasoning_effort=none` for GPT-6 Luna compatibility. |
| Anthropic | `claude-haiku-5-5`; Messages API | Requires `ALLOW_PAID_MODELS=true` and `ANTHROPIC_API_KEY`. Uses `anthropic-version: 2026-10-21`. System content maps to top-level `system`; native assistant blocks and tool-use IDs are preserved in the Messages tool cycle. |
| OpenRouter | Existing selected model | Requires `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. A `:free` route is not a durable entitlement or price guarantee. |
| Ollama | `qwen3:4b` starting tag | Uses configured `OLLAMA_BASE_URL`/`OLLAMA_MODEL`; it sends only to the configured local endpoint and does not borrow cloud credentials. Local compute, memory, electricity and performance depend on host hardware. |

`ALLOW_PAID_MODELS=true` is an application-level opt-in required for OpenAI and Anthropic and for any OpenRouter route or Cloudflare model outside the reviewed free-model list. It does not cap provider spending, determine account credits, or guarantee that no charge is incurred. A provider's free plan, account eligibility, quota and usage metering are external to this application. Model prices and provider quotas are shown in the [README](../../README.md#running-the-project), checked against official pages on 2026-11-03. They can change; actual bills also depend on context size, caching, processing tier, account and provider plan.

Provider adapters are specified against a shared application-facing assistant-message/tool-call contract, while each wire API keeps its native format. OpenAI Responses function calls and outputs are correlated by `call_id`; opaque reasoning items must be replayed with corresponding outputs. Responses requests bound output to 1,024 tokens and set `store=false`. OpenAI Chat Completions uses `tool_calls` and `tool_call_id`; GPT-6 Luna supports that endpoint only with `reasoning_effort=none`, and requests cap completion at 1,024 tokens. OpenAI recommends Responses for new integrations ([model guidance](https://developers.openai.com/api/docs/guides/deployment-checklist)). Anthropic uses `POST https://api.anthropic.com/v1/messages`, with `x-api-key` and `anthropic-version: 2026-10-21` headers ([versioning](https://platform.claude.com/docs/en/api/versioning)). Move system content to the top-level `system` field; use assistant `tool_use` blocks and user `tool_result` blocks keyed by `tool_use_id`, and replay the preceding assistant blocks intact. Keep provider errors bounded and recognizable, enforce the configured request timeout, and do not follow redirects with credentials. Cloudflare Workers AI and local Ollama use OpenAI-compatible chat completions. `httpx` is sufficient for these HTTP transports; no model SDK is required. Malformed/truncated outputs, unknown providers and missing credentials fail closed. See [interfaces](../interfaces.md) and the provider implementation for exact limits.

The application continues to own sender identity, source version, authorization, tool budgets and result validation. Model/provider selection does not change those boundaries. The standalone [MCP server](../interfaces.md#mcp-server) uses the locked `mcp==1.23.3` SDK and exposes only the four bounded application tools over local stdio; an MCP client selects its own model, so MCP calls do not pass through this model-provider factory. The MCP server selects the active source bundle on each individual call and returns `bundle_version` with successful results; it does not pin that version across a multi-call exchange as the Django customer turn does. An MCP host should compare returned versions before combining results.

## Cost and access notes

Prices below are USD per million input/output tokens, standard text rates for ordinary context sizes, not an estimate of total interaction cost.

| Provider/model | Input / output | Account caveat |
| --- | --- | --- |
| Cloudflare `@cf/google/gemma-4-26b-a4b-it` | $0.10 / $0.30 | 10,000 free Neurons/day; on Workers Free, requests fail after the daily allocation. Workers Paid starts at $5/month and charges usage above included neurons. |
| Cloudflare `@cf/zai-org/glm-4.7-flash` | $0.0605 / $0.40 | Listed among models available on Workers Free as of 2026-07-28 and included in the reviewed free-eligible allowlist; customer-workflow qualification remains open. Subject to plan/quota changes. |
| OpenAI `gpt-6-luna` | $0.10 / $0.50 | Paid API usage; ChatGPT subscription is not an API usage allowance. Long-context and processing options may cost more. |
| Anthropic `claude-haiku-5-5` | $0.10 / $0.50 up to 100k prompt tokens; $0.50 / $2.50 above | Paid API usage. Sonnet 5.5 is a higher-cost alternative at $2 / $10. |
| Ollama local model | No hosted inference token price | Local hardware, power, storage and operator time still have cost. Model tags with tool capability and sufficient quality vary. |
| OpenRouter | Route-specific | Route price and free availability can change; inspect the selected route before use. |

Official prices and plan limits: [Workers AI model/pricing](https://developers.cloudflare.com/ai/models/%40cf/google/gemma-4-26b-a4b-it/), [Workers AI pricing and free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Cloudflare free-plan model eligibility](https://developers.cloudflare.com/changelog/post/2026-07-28-models-require-workers-paid/), [OpenAI GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [Anthropic Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview), and [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

## MCP server boundary

`uv run --env-file .env python manage.py mcp_server` exposes exactly four existing application tools over stdio. MCP tool service and model inference remain independent: the MCP client supplies the model. `EMPORIO_MCP_SENDER`, when configured by the server operator, is the trusted sender for restricted order tools. Sender/customer identity and provider/model choice are never client tool arguments. Without trusted sender context, restricted calls receive a generic denial. A local stdio server does not provide remote endpoint authentication.

## Qualification and fallback policy

Mocked transport tests establish serialization and key isolation only. The Cloudflare probe establishes one successful short interaction only. The historical Ollama request and OpenRouter 429 results retain their original narrow scope. No provider has completed qualification of a Portuguese catalog/policy customer workflow with independently evaluated answers. The cost table is not a capability ranking and low rates do not imply stronger or equivalent answers.

Do not add implicit fallback. If an operator later requests it, independently qualify route entitlement, tool and JSON behavior, latency, Portuguese task quality and privacy handling. Preserve sender/source binding, counters, retry allowance and deadlines; do not switch after a tool execution, on authentication/billing/malformed-output errors, or after uncertain transmission. See [validation](../validation.md) for outstanding acceptance gaps.
