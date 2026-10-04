# Real-document ingestion: improvement plan

Reviewed 2026-10-03 against pdf2md commit `95bca9d`. The original priorities below are a design plan. An initial implementation now
provides source-line coverage, detected-table evidence and conservative joins,
optional table-model alternatives, and optional Markdown chunks; see the
[usage guide](../usage.md#table-preservation-and-page-coverage). General table
detection, complete output provenance, calibrated warnings, and the held-out
evaluation program remain future work. No retrieval improvements have been measured.

## Reading and source archive

[Your RAG Pipeline Dies on Real Documents: Here's Why](https://hackernoon.com/your-rag-pipeline-dies-on-real-documents-heres-why),
Paolo Perrone, HackerNoon, October 3, 2026.

The article argues that plausible extraction can silently discard relationships
needed for retrieval. It discusses tables, reading order, scans, visual content,
and the limits of page-by-page model calls. Its practical recommendation is to
inspect difficult source documents and evaluate parsing before retrieval.

This is commentary with a LlamaParse promotion, not an independent comparative
study. Its quoted accuracy, pricing, and repeatability figures were not reproduced
here and should not become pdf2md claims. PDF structure is not uniformly absent:
optional tags exist, and native text plus geometry remain useful evidence.

An original HTML response and a timestamped SHA-256 manifest are archived locally
under `artifacts/article-archive/2026-10-03-rag-real-documents/`. External assets
are not bundled. The source snapshot is excluded from Git; this review is the
public project record.

## Baseline before implementation

This assessment comes from `pdf2md_all.py`, `structured.py`, the architecture
guide, corpus audit tooling, and our conversion and visual-context evaluations.

| Area | Current implementation | Remaining gap |
|---|---|---|
| Layout | Font/geometry profiling, column ordering, caption-bounded report regions | Ambiguous sidebars and unconventional layouts still need review |
| Tables | Native PDF table extraction and grid rendering; EPUB/DOCX table readers | No general cross-page table stitching or lossless merged-cell representation |
| OCR | Optional selective Tesseract repair with recorded acceptance decisions | No comprehensive per-page coverage accounting; handwriting and dewarping remain difficult |
| Visual content | Optional figure crops, image references, chosen-model descriptions and audit records | Chart claims can be wrong despite fluent descriptions; see the [model review](../../benchmarks/visual-context.md) |
| Provenance | Document tree, source locations, hashes, transformation and repair records | Not a complete ledger explaining every retained, suppressed, or unread region |
| RAG preparation | Markdown structure and optional document artifacts | No supported chunk export preserving table headers, captions, and source links |

## Prioritized work

### 1. Page coverage and review reasons — first

`tools/audit_markdown_quality.py` already flags malformed tables, missing image
links, suspicious glyphs, heading issues, and leftover page furniture. Batch tooling
already applies resource limits and audits outputs. Extend these checks rather
than creating a second cleanliness scorer; output-only checks cannot measure
whether source content was omitted.

Extend the existing audit with a record for every requested page: native text
count, image regions, OCR attempted/accepted/rejected, emitted nodes, suppressed
content, and explicit reasons to review. Distinguish a blank page from an image
page with no recovered text. Track source IDs across cleanup so a large deletion
is inspectable. Introduce an optional strict mode only after checking false alarms.

These are observable warning signals, not a probability that the text is correct.
No stronger model is needed to detect an empty result or a truncated response;
neither check establishes factual accuracy.

Acceptance: fixtures for blank, scanned, mixed, corrupted-font, and ordinary pages;
every page accounted for; failed OCR and unexplained omissions visible; legitimate
blank pages do not become extraction failures. Measure warning precision and recall
on human-reviewed pages before using warnings to block ingestion.

### 2. Table semantics across pages — next

Preserve cell coordinates, header relationships, row/column spans, caption,
units, and page references in a table sidecar. Render simple grids as Markdown;
offer HTML for spans and retain a source crop when structure is unresolved.
Join adjacent-page tables only when column geometry, header evidence, and a
continuation cue agree. Record the join evidence and keep uncertain tables apart.

Acceptance: exact header/value association checks, merged-cell fixtures, continued
tables with and without repeated headers, and negative cases of unrelated adjacent
tables. Keep Brookings as a regression case. Score structure and cell text separately.

### 3. Structure-preserving chunk export

Build an optional exporter from the document tree, carrying section paths, source
IDs, pages, captions, and image references. Keep paragraphs and ordinary tables
intact when possible. Split oversized tables by rows with repeated headers and
units; flag a single row exceeding the budget rather than silently truncating it.
Keep model-written visual interpretation distinguishable from extracted text.

Acceptance: no lost or duplicated data rows, resolvable source links, explicit
oversize handling, and table questions answerable from each exported row group.
Choose and record a tokenizer rather than estimating budgets from characters.

### 4. Bounded fallback for difficult regions

Use review reasons to nominate a region for optional OCR or a specialist parser,
including a future Unlimited-OCR adapter. Preserve the native candidate and the
replacement separately. Cache by crop hash, model/version, prompt, and settings;
limit retries and record latency and usage. Allow abstention when candidates
disagree. Crops need enough surrounding context to retain labels and units.

Acceptance: unavailable backends and truncated output preserve the original
evidence; cache invalidates on configuration changes; measure whether fallback
improves human-labeled cases enough to justify added latency and model calls.

### 5. Evaluation that catches convincing mistakes

Create a frozen, human-annotated difficult-document set covering the failures above,
plus footnotes, formulas, rotated scans, and dense charts. Separate development
fixtures from held-out evaluation. Compare the same pages, enabled features, and
hardware; report per-category results and repeated model runs.

Use text error, reading-order errors, table cell/header accuracy, omitted-content
rate, unsupported visual claims, wall time, peak memory, and inference usage.
[OmniDocBench](https://github.com/opendatalab/OmniDocBench) provides annotated layout,
text, tables, formulas, and reading order with evaluation code, including TEDS.
Pin its dataset and evaluator versions; its scores do not replace our chart-fact
checks or a downstream retrieval evaluation.

For retrieval, hold chunking, embeddings, and questions constant when comparing
parsers; evaluate the new chunk exporter separately. Measure source-supported
answer accuracy and provenance correctness, not merely token reduction.

## Implementation decision

Start with page coverage and table provenance, then cross-page recovery and chunk
export. These make failures visible and supply evidence for deciding when a model
is useful. Keep native extraction as the inexpensive default. Do not infer that
layout-first processing must rasterize every document, or that a parser vendor's
benchmark establishes better performance on this corpus.

Relevant implementation reference:
[PyMuPDF table API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables).
The converter already uses this API; the proposed work adds document-level
relationships and review evidence around page-level extraction.
