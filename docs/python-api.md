[← README](../README.md)

# Python API

Use `pdf2md_api.py` from the repository checkout with the same Python environment
as the converter. This is an initial local API, not a published PyPI package.
It supports PDF, EPUB, and DOCX. Legacy Office conversion remains available through
the CLI.

```python
from pdf2md_api import ConversionError, convert_file, convert_bytes

result = convert_file("report.pdf", timeout=120, max_bytes=64 * 1024 * 1024)
print(result.markdown)
print(result.diagnostics)

# The PDF/EPUB/DOCX container signature takes precedence over a misleading name.
result = convert_bytes(document_bytes, filename="report.docx")
```

`ConversionResult` contains `markdown`, `diagnostics`, and detected `format`.
Conversion failures and timeouts raise `ConversionError`. Ordinary file opening
errors from `convert_file` retain their Python exception types. Defaults are a
128 MiB input budget and 300-second conversion timeout.

Each call uses a temporary directory and a subprocess. This isolates the legacy
renderer's module globals and supports concurrent callers, at the cost of process
startup. There is no claimed in-process speed improvement or Node/WASM binding.
Content detection belongs to this API; the CLI still dispatches by filename extension.

OCR and visual models are disabled. Embedded image extraction is disabled and
structured-document image labels remain as text; the result must not link to
assets that disappear when the temporary directory closes. This is a text-oriented
API. Use the CLI for persistent images, audits, selective OCR, strict coverage,
and model controls. Conversion does not build or query a RAG index.
