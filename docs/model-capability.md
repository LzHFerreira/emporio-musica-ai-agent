# Provider and model capability probes

These probes measure availability/protocol outcomes only. They do not qualify generated-answer quality or live Meta compatibility. The original OpenRouter probe preceded application implementation.

## OpenRouter (2026-11-02)

Target: `POST https://openrouter.ai/api/v1/chat/completions`, explicit `google/gemma-4-26b-a4b-it:free`, no paid or alternate route. The corrected synthetic Portuguese probe specified a fictional catalog fact and store hours, two unchanged tool definitions and a terminal-JSON prompt. Its offline harness checks passed, but the live request returned HTTP 429 in 0.60 s before inference; zero tool calls and no answer. An authenticated key diagnostic reported free tier and 50/50 daily requests remaining at 17:59:07 UTC; it does not explain the rate limit. The initial sandbox request had no retained status, and an earlier harness bug discarded one response category. No capability conclusion follows.

## Authorized application request (2026-11-03)

A single direct `run_turn`/`OpenRouterClient` request sent a synthetic Portuguese catalog/budget question, application prompt and four tool definitions to the same explicit free model. No customer/order data or retrieved tool result was sent. HTTP 429 arrived after 0.551 s; no completion or tool call. The fixed fallback returned, without retry or model switch. This did not traverse webhook, worker or Meta; local mock-transport integration was tested separately. Request scope/hash is in [priority evaluation](priority-evaluation.json).

## Local Ollama (2026-11-03)

Windows Ollama 0.40.14 with `qwen3:4b` was reachable from NAT-mode WSL through gateway `172.24.160.1` at review time. A synthetic greeting returned terminal JSON in 28.42 s. A full policy turn did not reach mock send acceptance before the 55-second work cutoff (55.73 s). These outcomes establish adapter reachability and one response shape, not tool-loop or task qualification. Setup and model digest are recorded in [ADR-0004](adr/0004-free-model-and-provider-fallbacks.md).

On 2026-11-04, `qwen3.5:9b` (Q4_K_M) on a Ryzen 5 8600G with integrated graphics took 10–70 s per request. With `OLLAMA_TIMEOUT_SECONDS=180` and `TURN_DEADLINE_SECONDS=900`, it completed the [five recorded conversations](interactions.md): 9 of 10 turns gave grounded answers and one gave the fixed failure reply. This is development evidence on one host, not an independent quality evaluation.

## Cloudflare Gemma application path (2026-11-03)

A bounded app probe sent two POST requests to the configured Gemma route; both returned HTTP 200. Gemma requested the Takamine GD20 catalog result and a public-policy lookup, then invoked the private `respond_to_customer` function. The worker nevertheless persisted its fixed failure reply, which the local Meta mock accepted; elapsed time was 20.515 s. The retained diagnostic excludes the reply arguments and raw response, so it cannot establish whether terminal parsing or evidence validation ran. This is evidence of model/tool protocol activity, not a successful customer answer or a completed workflow qualification.

## Separate Groq fixture experiment

[model-evaluation.jsonl](model-evaluation.jsonl) preserves an incomplete external experiment: three case records of sixteen planned cases, with valid terminal JSON. It supplied prepared evidence, did not exercise application retrieval/source routing, and includes historical orchestration attempts in its metadata. Groq has no application adapter; this record does not qualify the configured OpenRouter/Ollama customer workflow or establish a completed answer-quality evaluation.

Recheck availability and score complete application conversations before any current-provider capability claim; see [validation](validation.md).
