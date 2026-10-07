# AnyDoc follow-up — October 7, 2026

Reviewed [AnyDoc](https://github.com/firecrawl/anydoc) at source commit
`261fc257d17c3eab0f673be31c408fd9fdc2171a`. The implementation work inspired by
that review adds shared canonical cell positions, structured equation translation,
strict PDF coverage, bounded structured parsing, and a small Python API.

## Direct Office smoke test

Installed the published `firecrawl-anydoc==0.2.4` package in an isolated environment.
The package version is distinct from the source commit reviewed above. Both tools
converted the same hand-authored DOCX and EPUB fixtures, each containing a grouped
Revenue header, years 2024/2025, an EMEA row with values 120/145, and the fraction a/b.
No OCR or model calls were used.

| Check | AnyDoc 0.2.4 | Updated pdf2md |
|---|---|---|
| Data values and labels | Preserved | Preserved |
| Fraction | LaTeX `\frac{a}{b}` | LaTeX `\frac{a}{b}` |
| Grouped headers | Two rows; covered cells blank | Explicit `Revenue — 2024` / `Revenue — 2025` |

Both outputs retain the source information on these cases. pdf2md's flattened
headers make each data column self-describing without interpreting a separate
header row. That is a formatting distinction on two synthetic fixtures, not an
accuracy ranking, broad compatibility finding, or measured RAG improvement.

The fixtures and raw outputs are retained locally in ignored
`artifacts/structured-review/`. Regression tests independently cover horizontal and
vertical merges, row headers, unsupported math, XML/archive budgets, strict coverage,
and byte-input format detection. The Brookings PDF pages 30–32 were also rerun to
check that the existing table evidence still exports successfully.

## Decision

Keep AnyDoc as a candidate for future Office-format expansion. Do not add it as a
runtime dependency based on this small test. Its PowerPoint/Excel support, bindings,
and browser packaging remain advantages beyond this change. A representative
Office corpus, especially complex spreadsheets, presentations, and legacy formats,
is needed before selecting a backend. Its published benchmark excludes PDFs and
cannot establish better book or research-paper extraction than pdf2md.

See [usage](../docs/usage.md#structured-tables-and-equations) and the
[Python API](../docs/python-api.md) for implemented behavior and limits.
