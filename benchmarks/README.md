# Conversion quality benchmarks

Run `python3 tools/benchmark.py manifest.json --output artifacts/benchmark`.
The runner converts each input in a fresh process, saves Markdown and provenance,
checks annotated assertions and reports elapsed time and peak resident memory.
There is no network access or model judge. Inputs are never changed.

Example manifest (input paths are relative to this manifest):

```json
{"cases": [{"id": "paper", "input": "papers/example.pdf",
  "args": ["--doc-type", "paper", "--no-toc"],
  "checks": [
    {"type": "contains", "text": "An exact sentence from the source."},
    {"type": "absent", "text": "�"},
    {"type": "order", "texts": ["Left column ends here", "Right column begins here"]},
    {"type": "heading", "level": 2, "text": "Methods"},
    {"type": "count", "text": "Unique paragraph", "count": 1},
    {"type": "table_row", "cells": ["Model", "Accuracy"]}
  ]}]}
```

Choose annotations by inspecting source pages, not the generated Markdown.
Include ebooks, research papers, irregular reports, multiple languages, clean
text layers, mixed PDFs and scans. Keep separate cases for different languages.
Missing inputs are errors. Cases without checks are `unannotated`, not quality
passes. An optional `reference` text file enables multiset token precision and
recall (not CER/WER and not an order metric). Use `order` checks separately.
Use identical flags, inputs and environments when comparing runtime or memory.

Research: [OmniDocBench](https://arxiv.org/abs/2412.07626) motivates separate
content/structure checks; [olmOCR 2](https://arxiv.org/abs/2510.19817) motivates
verifiable assertions. This harness does not implement either official scoring
protocol and its scores must not be presented as their benchmark scores.

For a repeatable comparison with Microsoft's stock local PDF converter, install
`markitdown[pdf]` in the same environment and run:

```bash
python3 tools/compare_converters.py manifest.json --output artifacts/comparison --repeats 3
```

Only `--no-toc` is accepted in case arguments for comparisons. Both tools read
the same complete PDF; no cloud or OCR backend is enabled. Per-file median
conversion time and peak RSS are reported along with the same quality assertions.
Versions and converter/manifest hashes are recorded. Missing or corrupt files
remain visible as failures, and are not included in successful timing medians.
Heading checks ignore case; `level` is optional. Reading-order anchors also
ignore case. Text-presence checks are case-sensitive and normalize whitespace
only. Prefer unique anchors to avoid matching a table-of-contents entry instead
of the body. A global absence check does not replace a transcription reference.

## Interpreting results

[The September 19, 2026 development comparison](comparison-2026-09-19.md)
records the measured sample results and their limitations. Assertions evaluate
only what is annotated: a passing `contains` check does not prove paragraph
boundaries, and a passing `heading` check does not prove the entire hierarchy.
No comprehensive Markdown formatting score is currently implemented.

For formatting review, annotate source-backed examples of paragraphs, heading
hierarchy, lists, tables, code, footnotes and running furniture. Inspect rendered
Markdown as well as raw text, and report each category separately. Keep examples
used to fix defects separate from a held-out evaluation set.

The comparison alternates engine order across fresh-process trials. Timing
includes converter imports, conversion and output writing, but excludes common
interpreter/harness startup. It disables audit writing and OCR. Peak RSS measures
the worker process, not child processes. Report platform, versions, cache state,
trial count and sampling rules with any performance claim. Conversion errors are
not quality passes; unannotated files are not evidence of extraction accuracy.

Private PDFs, generated Markdown, and source paths belong in ignored local
`artifacts/`, not in committed benchmark fixtures.
