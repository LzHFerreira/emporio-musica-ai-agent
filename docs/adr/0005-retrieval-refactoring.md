# ADR-0005: Retrieval refactoring

- Status: Accepted (2026-11-04).
- Date: 2026-11-03.

## Context

Retrieval passes its 11-case regression set ([retrieval evaluation](../retrieval-evaluation.json)), but probes outside that set show recall and abstention gaps. The snapshot has 26 public policy passages from an eight-page manual (about 17.6k characters, roughly 5k tokens) and 65 catalog products.

| Probe | Current result | Cause |
|---|---|---|
| Catalog `violão de nylon`, max R$ 1.000, PIX, in stock | 4 products; Yamaha C40 (R$ 569,91) and Giannini GN-15 (R$ 654,55) missing | The catalog path keeps the stop word `de`, so every product must contain it as a whole word (`emporio/catalog/query.py`). `violao nylon` returns both. |
| `Vocês abrem no domingo?` | `not_found` | `abrem`/`domingo` map to no topic; the hours table is not reached (`emporio/policy_intents.py`). |
| `Aceitam cartão parcelado?` | `not_found` | `parcelar` is expanded, `parcelado` is not. |
| `Posso retirar meu pedido na loja?` | `not_found` now; an external review observed adjacent §§5.2–5.3 returned as `found` | The manual has no pickup policy. Abstention depends on an overlap rule, not on whether a passage answers the question. |

Live replies omitted the two missing guitars, so the catalog gap reaches customers. The policy vocabulary, expansions and staff passage map are hand-maintained and were tuned against questions inspected during development. At this size, deterministic passage ranking adds maintenance without a matching benefit: the model already interprets whatever passages it receives.

## Decision (accepted)

1. **Policy: give the model the whole manual.** The `read_store_manual` tool returns the full extracted text with page markers and is the primary policy source; ranked `lookup_public_policy` stays available (see item 5). The model reads it and decides whether the manual answers the question; when it does not (for example pickup), it says so and offers a human. Because ranked lookup is kept, its topic vocabulary, expansions, abstention rule and staff passage-review workflow also stay.
2. **Extraction: pypdfium2 with a coverage gate.** Extraction already moved to pypdfium2 (implemented 2026-11-03; pdfplumber was evaluated and interleaved running headers into tables on this PDF, while pypdfium2 matched Ghostscript word-for-word). Publication fails closed unless:
   - each page's extracted text covers at least 99% of the PDF's own text-layer characters;
   - no page is empty or image-only (scanned content the extractor cannot read);
   - a golden test on the supplied manual finds every section heading, every hours-table row and key values (7 days, 10 business days, 5% PIX discount, warranty exclusions). The golden test now exists: 8 pages, all nine section headings and key values.
   The existing PDF hash pinning stays, so the model receives exactly the text that passed the gate.
3. **Catalog: keep structured, deterministic search.** Prices, stock, PIX, promotions and installments are arithmetic and exact filters that small models get wrong, and the output guard depends on exact tool prices. Apply the shared Portuguese stop-word list to catalog query tokens.
4. **Determinism stays where it matters.** Tool outputs remain deterministic (same manual text, same catalog rows); only the model's reading varies, as it already does with ranked passages. Prices, stock, orders and the output guard remain deterministic.
5. **Retrieval decision and evidence (2026-11-04).** Keep the full manual (`read_store_manual`) as the primary policy source and keep ranked `lookup_public_policy`. A hybrid (ranked, falling back to the full manual on `not_found` or weak matches) is deferred until token cost matters. This supersedes item 1's removal of the abstention rule.
   - Measurement: retrieval only, deterministic, 11 development cases plus 4 condition-critical probes. Full manual: 15/15 required conditions, about 15,200 characters (about 4–5k tokens) per call, about 0.8 ms. Ranked lookup: 14/15, about 750–1,700 characters, about 1.5–2 ms, about 13x smaller. Ranked lookup missed manual §4.2 ("30 (trinta) dias" defect exchange) for "Meu violão veio com defeito, e agora?" with both `topic=warranty` and `topic=null`.
   - Failures in the Context table no longer reproduce: "Vocês abrem no domingo?", "Aceitam cartão parcelado?", and the pickup adjacent-section false positive.
   - Catalog retrieval changes since this ADR: hyphenless model codes; filler and price/payment words ignored in budgeted searches; description-only matches dropped when name, category or spec matches exist.
   - Limits: retrieval only; answer correctness with a live model is unmeasured; spec values are not accent-folded.
   - Public-review controls stay unchanged. This decision does not authorize removing them.

## Alternatives considered

- **BM25:** fixes term weighting (`de`) but not inflections, synonyms (`abrem no domingo` → hours) or abstention, which still needs a score threshold.
- **Embeddings (for example Cloudflare `@cf/baai/bge-m3`) with a vector store such as FAISS:** handle paraphrases, but add a network call per question, a calibrated threshold and mocked tests. FAISS adds a native dependency for 26 vectors, where a numpy dot product would do. Unnecessary when the whole manual fits in context.
- **pdfplumber:** interleaved running headers into table rows on this PDF; pypdfium2 matched Ghostscript word-for-word.
- **PyMuPDF:** best extraction quality, but AGPL. **pypdf:** lighter, weaker on tables. **Sending the PDF to a vision model:** ties the design to multimodal models and loses the coverage gate.

## Consequences

About 5k extra input tokens per model request, which consumes free-tier quota faster. The output guard can only confirm that a policy number appears in the manual, not in the right section; that binding was already weak. Fewer files to maintain, which also answers the review's scope concern.

## Acceptance

Run `evaluate_model` before and after the change, with the four probes above added as cases, and adopt the change only if results hold or improve. The existing regression tests either still pass or are retired together with passage ranking, with the reason recorded.
