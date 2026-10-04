# Table preservation smoke test — October 4, 2026

This is a small implementation check, not a general model ranking or a retrieval
benchmark. The full regression suite also exercises synthetic merged headers,
HTML spans, continuation joins and negative cases, blank-page accounting,
chunk row preservation, model failures, and model-revision cache invalidation.

## Source and procedure

Used PDF pages 30–32 of the public
[Brookings automation report](https://www.brookings.edu/wp-content/uploads/2019/01/2019.01_BrookingsMetro_Automation-AI_Report_Muro-Maxim-Whiton-FINAL-version.pdf).
The table on page 30 contains four columns, one header row, and 14 data rows.
The source crop was visually inspected. Native conversion and artifact/chunk
exports were also exercised on three textbook pages with running headers.

The native table retained all 15 rows and recovered bounds for all 60 cells.
The table chunk carried its caption/context and page reference. The three report
pages produced no coverage review reasons; this does not prove full correctness.

## Live model calls

Both models used the configured Ollama endpoint and the new table-specific JSON
prompt with temperature zero, a 4,096-token output limit, and one attempt per run.
There were development retries while fixing response parsing; these are not
statistically controlled repeated trials.

| Model | Final observed result | Generation request time |
|---|---|---:|
| `glm-5.3-flash:cloud` | Valid 14-row candidate; all 56 data cells and four headers matched native extraction | 7.20 s |
| `qwen3-vl:30b` | No final JSON content; native output retained and failure recorded | 6.54 s |

Earlier responses exposed a compatibility problem: a model may prepend prose even
when JSON is requested. The parser now accepts a complete final table object and
excludes the preface from output. It still rejects truncation, invalid schemas,
and absent final content. No quality score is assigned to failed calls.

Cell agreement on this table is not evidence that either model will preserve
merged headers, handwritten values, or chart relationships on other documents.
Model-provided notes remain unverified interpretation/extraction requiring review.

## Native overhead

Three sequential development runs per version, using the same three report pages,
`--no-toc`, and `--artifacts`, with no model or chunk export:

| Version | Wall-clock seconds | Median |
|---|---|---:|
| Before this change (`6220558`) | 0.224, 0.225, 0.215 | 0.224 s |
| Development implementation | 0.271, 0.283, 0.277 | 0.277 s |

The additional audit and table work cost about 0.053 seconds on this sample.
This is approximately 24% overhead, not a speed improvement. Small warm runs on
one machine are insufficient to predict large-corpus performance. No indexing,
retrieval accuracy, memory, or end-to-end RAG speed gains were measured.

Private run artifacts are stored locally under `artifacts/ingestion-check/` and
are excluded from Git. See the [usage guide](../docs/usage.md#table-preservation-and-page-coverage)
for commands and limitations.
