# pdf2md / MarkItDown comparison — 2026-09-19

Implemented converter tested on a reproducible random sample of the local library. Eight readable documents contain 635 pages in total. A ninth sampled file is empty; both converters reject it. It remains in the manifest and reports.

These measurements precede integration of the separate library-sweep fixes from
commit `8acb5e0`. They describe the converter hash recorded below, not a new
performance measurement of the combined code. After integration, the same
quality manifest was rerun: all eight readable files passed their checks, and
the known empty input remained an error. The combined regression suite passed
82 tests. The three-trial performance comparison was not repeated.

## Aggregate results

| Metric | pdf2md | MarkItDown 0.1.7 |
|---|---:|---:|
| Source-grounded spot checks | 42/42 | 20/42 |
| Sum of per-file median conversion time | 5.41s | 38.31s |
| Median across per-file median peak RSS | 69.1 MiB | 124.7 MiB |
| Largest per-file median peak RSS | 138.6 MiB | 213.3 MiB |

On this sample, pdf2md is 7.08 times as fast based on the sum of per-file median conversion times.

## Per-file results

Each time and memory value is the median of three fresh-process trials. PDF pages are numbered from 1.

| Document | Pages | Checks: pdf2md / MarkItDown | Time: pdf2md / MarkItDown | Peak RSS: pdf2md / MarkItDown |
|---|---:|---:|---:|---:|
| SIMA-Play research paper | 19 | 6/6 / 3/6 | 0.238s / 4.623s | 75.1 / 173.7 MiB |
| Agentic Search research paper | 15 | 6/6 / 1/6 | 0.225s / 0.904s | 69.8 / 118.5 MiB |
| Semantic Scanpath research paper | 10 | 5/5 / 4/5 | 0.180s / 0.741s | 67.7 / 119.4 MiB |
| Email Refinding conference paper | 10 | 5/5 / 1/5 | 0.169s / 0.826s | 68.2 / 119.1 MiB |
| Mobile Phones in Medical Work | 6 | 5/5 / 3/5 | 0.121s / 0.418s | 67.2 / 112.4 MiB |
| 2017 Think Tank Index report | 208 | 5/5 / 5/5 | 0.645s / 6.276s | 91.1 / 130.0 MiB |
| Synchronous Social Q&A paper | 10 | 5/5 / 2/5 | 0.321s / 2.881s | 68.3 / 213.3 MiB |
| Blackwell Guide to Philosophy of Law | 357 | 5/5 / 1/5 | 3.514s / 21.637s | 138.6 / 143.8 MiB |

## Method and limits

- Source files were copied locally for both converters; originals were not modified.
- Seed 20260919: four entries from the initial uniformly sampled Documents/Downloads PDFs; two random library PDFs below 2 MB; two random library PDFs from 2–30 MB. Seed 20260920 adds one randomly selected non-conference, non-report PDF with at least 100 pages. See manifest population counts.
- Three trials per engine, alternating engine order. Same Python environment and PDFs. No cloud, OCR, plugins, or audit writing in the timed comparison. Common interpreter/harness startup is excluded; converter imports, conversion, and Markdown writing are included. Filesystem caches were warm from validation. Other host workloads were not controlled.
- MarkItDown uses its stock local API with plugins disabled; Azure, vision-model and OCR extensions are not compared.
- Checks were transcribed from rendered source pages before initial output inspection. Four annotation errors were subsequently corrected against the source and applied equally to both tools; the manifest records them.
- The sample exposed column-order, font-flag and symbol-repair defects that were fixed. This is a development validation set, not an independent held-out benchmark.
- The 42 checks cover selected passages, heading tags/levels, reading order and replacement characters. They are not full-document CER/WER scores and do not comprehensively assess formulas, tables, footnotes or multilingual scans. Passing them does not establish perfect conversion.
- Separate `release-audit` runs enable selective OCR and save tree/provenance artifacts. These are excluded from performance measurements. Font-encoded Symbol bullets are decoded directly; unverifiable standalone symbols are skipped rather than rewritten. Actual scan OCR is also covered by a generated mixed-PDF integration test.
- All 60 regression tests passed; static checks, byte compilation and single-file build consistency passed.
- These are research-inspired deterministic structure/verification methods plus optional Tesseract OCR. Trained DocLayNet/MinerU models, neural dewarping, cross-document training and official OmniDocBench scoring are not implemented.

## Reproduction and availability

The original inputs, source-page images, annotated manifest, detailed JSON
reports, and converted Markdown remain in ignored local artifacts. They are not
published with this repository. The aggregate results above are therefore a
reported development measurement, not a publicly reproducible benchmark dataset.

To run the same protocol on your own files, create a source-annotated manifest
using [the benchmark guide](README.md), install the optional comparison dependency,
and run:

```bash
pip install 'markitdown[pdf]==0.1.7'
python3 tools/compare_converters.py manifest.json --output artifacts/comparison --repeats 3
```

## Markdown formatting coverage

The selected heading and text checks provide partial evidence of Markdown
quality. They did not systematically assess paragraph spacing, nested lists,
table layout, code fences, footnote references/definitions, repeated headers,
or rendered readability across every output. No overall formatting score was
computed, and 42/42 must not be interpreted as perfect Markdown quality.

A broader evaluation should annotate these structures against source pages,
parse both outputs with the same Markdown dialect, and inspect rendered output
on an independent held-out sample. Automated syntax checks alone cannot establish
whether a paragraph or heading matches the source document. Formula transcription,
scanned physical books and multilingual documents also need separate evaluation.

Environment: Python 3.14.7; PyMuPDF 1.28.2; MarkItDown 0.1.7; pdfminer-six 20260107. Platform: `Linux-7.0.14-orbstack-00380-ga7e0a2dc9535-aarch64-with-glibc2.41`.

Converter SHA-256: `0a87968c9c201088c438a5db210a0d5bc8a6a1e2e1c0d6d3dea5f8e5a1f36d74`.
