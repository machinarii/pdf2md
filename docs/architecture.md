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
5. **Construct and render.** Build heading and paragraph/list relationships,
   reflow text, and emit Markdown with metadata and an optional contents list.

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
- Sparse numeric tables and multi-row headers remain difficult. Nested tables are
  flattened; their containment cannot be represented as nested Markdown tables.
- Equations pass through as approximate text rather than reconstructed LaTeX.
- Heading checks accept Unicode letters, and Chinese/Japanese line joining avoids artificial spaces. Name and regime heuristics still primarily target English/Latin text.
- Footnote labels may be page-qualified rather than preserve printed numbering.
- A coverless book can fall back to the filename even when PDF title metadata exists.
- Undecodable font encodings can produce plausible-looking nonsense. Warnings
  detect some patterns but do not solve arbitrary substitution encodings.
- DOCX tracked changes, comments, and text boxes are not fully represented.
- Classification may mistake landscape books for decks, or legitimate content
  for running furniture. Review important output against the source.

See the [usage guide](usage.md) for OCR restrictions and provenance fields,
[comparison report](../benchmarks/comparison-2026-09-19.md) for measured coverage,
and [contribution guide](../CONTRIBUTING.md) for regression testing.
