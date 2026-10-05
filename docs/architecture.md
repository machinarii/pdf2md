[← README](../README.md)

# Architecture and limitations

`pdf2md_all.py` is the standalone converter. It contains the PDF pipeline and an
inlined copy of `structured.py`, which implements EPUB and DOCX readers.
`tools/sync_structured.py` synchronizes the latter using identifier-aware edits;
CI verifies that the two copies agree.

## PDF pipeline

1. **Extract.** Read text spans with fonts, sizes, weights, and bounding boxes.
   Normalize page rotation and infer page-local column reading order.
2. **Repair when requested.** Optional local Tesseract OCR handles selected damaged
   lines and empty image pages and separate image regions, including PDF rotations. Confidence and text-preservation gates accept or
   reject candidates; decisions are recorded.
3. **Identify and profile.** Infer book, paper, deck, or document from metadata,
   geometry, typography, and structural markers. Learn body styles, repeated
   running heads, and heading styles from the current document.
4. **Classify.** Assign roles such as heading, body, caption, code, table, and
   footnote. Apply document-type and front/back-matter rules.
5. **Preserve tables.** Match detected tables against native cell geometry, retain
   known spans, and flatten supported grouped headers into explicit labels. Join
   numbered continuations only when headers and bounds agree. Optional Ollama
   candidates remain separate unless `--table-render model` is selected.
6. **Construct and render.** Build heading and paragraph/list relationships,
   reflow text, and emit Markdown with metadata and an optional contents list.
7. **Export when requested.** `--artifacts` saves page coverage, table crops and
   cell evidence alongside the existing tree and repair logs. `--chunks` counts
   tokens with an optional tokenizer and preserves block/table context for ingestion.

Model table extraction has a per-document attempt cap, a per-call timeout, and
revision-aware caching. Schema, truncation, numeric-token, and shape checks are
not factual verification. Failed candidates leave native output intact. Figure
interpretation uses its separate `--figure-vlm` path and remains unverified context.

The document tree records structural relationships, not a semantic knowledge
graph. Source records preserve original text locations through some merges and
transformations. They do not map every Markdown byte to the original PDF.

## Structured formats

EPUB readers follow spine order and use HTML/CSS evidence for structure. DOCX
readers use document elements and styles. DOC, ODT, and RTF are converted through
LibreOffice. For structured reader changes, edit `structured.py` and run:

```bash
python3 tools/sync_structured.py
python3 tools/sync_structured.py --check
```

## Practical limits

- Unusual columns, sidebars, tables, and wrapped headings can produce incorrect
  structure or reading order. A successful exit does not establish completeness.
- Sparse numeric tables, arbitrary header depth, and continuations without repeated
  headers remain difficult. Table vision operates only on already detected tables.
  Nested tables are
  flattened; their containment cannot be represented as nested Markdown tables.
- Equations pass through as approximate text rather than reconstructed LaTeX.
- Heading checks accept Unicode letters, and Chinese/Japanese line joining avoids artificial spaces. Name and regime heuristics still primarily target English/Latin text.
- Footnote labels may be page-qualified rather than preserve printed numbering.
- Untrustworthy title metadata can fall back to typography or the source filename.
- Undecodable font encodings can produce plausible-looking nonsense. Warnings
  detect some patterns but do not solve arbitrary substitution encodings.
- DOCX tracked changes, comments, and text boxes are not fully represented.
- Classification may mistake landscape books for decks, or legitimate content
  for running furniture. Review important output against the source.

See the [usage guide](usage.md) for OCR restrictions and provenance fields,
[comparison report](../benchmarks/comparison-2026-09-19.md) for measured coverage,
and [contribution guide](../CONTRIBUTING.md) for regression testing.

The [real-document ingestion improvement plan](research/2026-10-03-document-ingestion.md)
prioritizes page coverage checks, table continuity, and structure-preserving chunk
export. Initial coverage, table-preservation, and chunk-export support is described in the
[usage guide](usage.md#table-preservation-and-page-coverage); the broader plan is
not a completeness or accuracy guarantee.
