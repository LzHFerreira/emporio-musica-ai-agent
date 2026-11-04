# ADR-0005: Retrieval refactoring

- Status: Proposed; not implemented. Requires owner approval before code changes.
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

## Decision (proposed)

1. **Policy: give the model the whole manual.** Replace passage ranking with a `read_store_manual` tool that returns the full extracted text with page markers. The model reads it and decides whether the manual answers the question; when it does not (for example pickup), it says so and offers a human. This removes topic vocabulary, expansions, the abstention rule and most of the staff passage-review workflow.
2. **Extraction: pypdfium2 with a coverage gate.** Extraction already moved to pypdfium2 (implemented 2026-11-03; pdfplumber was evaluated and interleaved running headers into tables on this PDF, while pypdfium2 matched Ghostscript word-for-word). Publication fails closed unless:
   - each page's extracted text covers at least 99% of the PDF's own text-layer characters;
   - no page is empty or image-only (scanned content the extractor cannot read);
   - a golden test on the supplied manual finds every section heading, every hours-table row and key values (7 days, 10 business days, 5% PIX discount, warranty exclusions). The golden test now exists: 8 pages, all nine section headings and key values.
   The existing PDF hash pinning stays, so the model receives exactly the text that passed the gate.
3. **Catalog: keep structured, deterministic search.** Prices, stock, PIX, promotions and installments are arithmetic and exact filters that small models get wrong, and the output guard depends on exact tool prices. Apply the shared Portuguese stop-word list to catalog query tokens.
4. **Determinism stays where it matters.** Tool outputs remain deterministic (same manual text, same catalog rows); only the model's reading varies, as it already does with ranked passages. Prices, stock, orders and the output guard remain deterministic.

## Alternatives considered

- **BM25:** fixes term weighting (`de`) but not inflections, synonyms (`abrem no domingo` → hours) or abstention, which still needs a score threshold.
- **Embeddings (for example Cloudflare `@cf/baai/bge-m3`) with a vector store such as FAISS:** handle paraphrases, but add a network call per question, a calibrated threshold and mocked tests. FAISS adds a native dependency for 26 vectors, where a numpy dot product would do. Unnecessary when the whole manual fits in context.
- **pdfplumber:** interleaved running headers into table rows on this PDF; pypdfium2 matched Ghostscript word-for-word.
- **PyMuPDF:** best extraction quality, but AGPL. **pypdf:** lighter, weaker on tables. **Sending the PDF to a vision model:** ties the design to multimodal models and loses the coverage gate.

## Consequences

About 5k extra input tokens per model request, which consumes free-tier quota faster. The output guard can only confirm that a policy number appears in the manual, not in the right section; that binding was already weak. Fewer files to maintain, which also answers the review's scope concern.

## Acceptance

Run `evaluate_model` before and after the change, with the four probes above added as cases, and adopt the change only if results hold or improve. The existing regression tests either still pass or are retired together with passage ranking, with the reason recorded.
