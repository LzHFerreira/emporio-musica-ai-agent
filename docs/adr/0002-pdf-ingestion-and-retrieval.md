# ADR-0002: PDF ingestion and policy retrieval

- Status: Implemented locally: bounded extraction, staff review/publication, pinned lookup and fixed-set retrieval regression evaluation. Live answer quality is unverified.
- Date: 2026-11-02.

## Decision

Extract PDF pages in-process with pypdfium2; require staff to approve public passages and supported rule metadata before publication. Bind approval to the PDF hash and draft revision. Keep deterministic Portuguese topic/lexical retrieval while the regression set passes; it does not establish general paraphrase coverage.

The local trial used Ghostscript 10.08.0 on the supplied eight-page manual: eight nonempty UTF-8 page files, 17,645 characters; inspected accents, headings, table rows and order were preserved. Ghostscript `txtwrite` emits Unicode ([Ghostscript device docs](https://ghostscript.readthedocs.io/en/latest/Devices.html)). On 2026-11-03 extraction moved to pypdfium2 to remove the system dependency (Ghostscript installs as `gswin64c` on Windows), with identical normalized text and passages on the supplied manual. `pypdf` ([text extraction docs](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)) could not be trialed because PyPI DNS resolution failed. OCR is not supported; extraction failures or empty pages require staff action.

Ingestion limits are 10 MiB, 20 pages, 128 KiB extracted text; parsing has no separate timeout. Reviewers see page text and submit complete source-grounded passages (max 400 code points) with page/section, topic and audience. The initial passage map applies only to the exact supplied-PDF hash; new PDFs require review. Internal or unclassified text is excluded. Supported price metadata is published with the PDF and snapshot; unsupported rule semantics are rejected.

Lookup filters to public passages in the pinned snapshot, normalizes Portuguese accents/case, uses reviewed vocabulary and stable locators, and returns at most three complete passages. `not_found` is distinct from source errors. Model-facing schemas cannot select a snapshot. Publication and rollback activate PDF, manifest and pricing rows together. Full contracts are in [interfaces](../interfaces.md) and [ADR-0003](0003-protected-source-maintenance.md).

## Alternatives and evidence

Reviewed lexical retrieval is small and deterministic, but misses unrecognized paraphrases and needs alias maintenance. FTS5, embeddings/hybrid retrieval and query expansion remain candidates only if independent evaluation demonstrates benefit. LlamaIndex is an ingestion framework, not a retrieval strategy ([pipeline docs](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/)); SQLite FTS5 is an optional lexical index ([docs](https://www.sqlite.org/fts5.html)).

The [11-case regression set](../retrieval-evaluation.json) reports precision, recall and required-condition coverage of 1.0, with zero irrelevant or non-public results. Its paraphrases were inspected during implementation and are not held-out evidence. It cannot establish unseen-query performance. See [validation](../validation.md).
