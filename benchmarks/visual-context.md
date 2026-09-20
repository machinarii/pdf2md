# Visual model findings

Evaluated September 19–20, 2026 on four figures from two research PDFs: a
hierarchical experience diagram, four training charts, a radar chart with an
8-by-4 numeric table, and a board with 31 occupied cells containing colored pins.
These are diagnostic cases, not a representative accuracy benchmark. Source PDFs,
images and raw responses remain in local artifacts; no private source paths are
published here.

## Which model to choose

**GLM-5.3-Flash gave the most useful overall explanations in this sample.**
**Qwen3.8:27b was the strongest tested local option** for complete descriptions
and table transcription. Both made factual errors. This is a qualitative review,
not an aggregate accuracy score or a claim about downstream RAG quality.

| Exact tested tag | Mean request time | Descriptions returned | Printed numeric cells transcribed correctly | Observed trade-off |
|---|---:|---:|---:|---|
| `glm-5.3-flash:cloud` | 9.39 s | 3/4 | 32/32 | Useful process and pattern descriptions; unsupported claims and planning text |
| `qwen3.8:27b` | 36.37 s | 4/4 | 32/32 | Complete tables and readable descriptions; incorrect comparisons and pin counts |
| `glm-ocr:latest` | 2.78 s | 3/4 | 32/32 | Fast transcription; repetition, prompt echo and little relationship explanation |
| `qwen3-vl:8b` | 17.73 s | 4/4 | 8/32 | Short descriptions; omitted values and reversed chart trends |
| `qwen3-vl:30b` | 13.11 s | 4/4 | 11/32 | Fast in this run; incomplete tables and misleading chart conclusions |
| `llama3.2-vision:latest` | Not measured | No inference | Not evaluated | Model loading failed with `unknown model architecture: 'mllama'` |

For the 8B and 30B models, all explicitly transcribed table values were correct;
the remaining cells were omitted. Completeness and correctness are distinct.
Returned descriptions are not accuracy passes. Llama failed on Ollama 0.33.0
and again on 0.34.2; this supplies no evidence about its output quality.

## Method and timing limits

Standard runs used identical crop hashes, extracted captions and production
prompt at commit `13712e6`: temperature 0, thinking disabled, a 1,600-token output
limit and one request per figure. Qwen runs reported above used Ollama 0.34.2.
GLM results were retained from earlier runs, not rerun on that version. Flash is
cloud-hosted; the other successful models were local. The earlier Qwen3.8 run
averaged 42.08 s; its updated-server rerun averaged 36.37 s, used above.

Times include loading, server and network effects. Different runtime versions,
cache state and local/cloud execution prevent a controlled throughput comparison.
The smaller parameter count did not guarantee lower latency in these single runs.
No repeated-trial confidence intervals, broad accuracy score or retrieval benchmark
were measured. Exact tags record the tested installations; availability elsewhere
must be checked with that user's Ollama server.

## Errors that matter for retrieval

- **Correct table, incorrect conclusion:** Qwen3.8 transcribed Ecosystem Carbon as
  Player 1 = 57 and Player 2 = 63, then incorrectly called Player 1 the leader.
  Flash missed Player 1's Wood Products Carbon lead despite transcribing 48.
- **Misread curves:** Flash called Backbone gradient norm consistently higher,
  overlooking its dip below HiExp near step 200. Qwen3.8 assigned that dip to the
  wrong series. Qwen3-VL 8B and 30B reversed major variance comparisons and drew
  misleading conclusions about training stability.
- **Unreliable counting:** Qwen3.8 assigned four pins to every occupied cell;
  only 11/31 counts matched manual review. Qwen3-VL 8B omitted counts. The 30B
  model's two explicitly located counts were both wrong: row 2/column 1 has three
  white pins, and row 3/column 2 has five red pins, rather than two each.
- **Invented relationships:** Models inferred game rules, assigned meanings to
  ambiguous output labels and sometimes reversed flowchart relationships.
- **Incomplete output:** Standard Flash board and GLM-OCR training-chart responses
  reached the output limit and were rejected. Flash sometimes included planning
  prose even with thinking disabled; the converter does not reliably strip it.

No tested model provided reliable automatic pin counting. A separate Flash board
retry with 4,000 tokens returned text but invented a sixth column and miscounted
two cells. It is excluded from the standard comparison.

## Higher resolution and close-ups

Qwen3-VL 8B and 30B each received three additional board views: a full 300-DPI PDF
rendering, an upper detail, and a lower detail. All six requests reached the same
1,600-token limit; no complete description was published. This does not establish
that higher resolution helps or hurts accuracy. The lower crop clipped the upper
edge of its first row, further limiting a fair counting assessment.

These supplementary runs are excluded from standard timing. Higher-DPI rendering
can preserve more detail in vector graphics, but cannot recover detail absent
from an embedded photograph. A future controlled test should use complete,
overlapping crops, retain raw response diagnostics, and test a larger output budget
separately from resolution changes.

## Can low accuracy confidence be detected?

**There is no calibrated accuracy-confidence score in pdf2md today.** Successful
generation, model self-confidence and agreement between models do not prove a
claim correct. A stronger model can be a useful reviewer, but its verdict is not
ground truth: it may repeat the same visual mistake or accept a fluent explanation.
A reviewer should see the source image and identify evidence for each challenged
claim; its reliability still needs human-checked evaluation. Deterministic checks
can catch internal contradictions without another model, but cannot prove that
extracted evidence itself matches the image.

`generated`, `status` and `review_required` describe generation and
review state, not a probability of accuracy. Failures and explicit truncation
already trigger image/label fallback.

Useful future checks would operate per claim or region:

| Check | What a failure could flag | Limit |
|---|---|---|
| Recompute rankings from extracted tables | Summary contradicts its own numeric evidence | Both table and summary can share an extraction error |
| Check expected rows, columns, labels and coverage | Missing content or impossible grid dimensions | Expected structure needs independent evidence |
| Compare complete overview and overlapping close-ups | Unstable counts, labels or series assignments | Consistent errors can survive every view |
| Compare OCR numbers with visual descriptions | Conflicting transcription | OCR itself can be wrong |
| Verify units, legend identity and arrow direction | Unsupported claims or reversed relationships | Needs source-grounded extraction or human review |
| Track truncation, repetition and prompt echo | Incomplete or poorly formed output | Clean prose may still be factually wrong |

Initially these should produce explicit review reasons such as `table-summary
conflict` or `unverified count`, not invented numerical confidence percentages.
Calibrated probabilities require a labeled, representative evaluation set with
held-out validation, tracked by model, prompt and document type. These additional
accuracy checks are proposals, not implemented features. Until then, preserve
source crops and treat all generated descriptions as requiring review.

## Crop recovery and remaining limits

The corrected detector intersects drawing paths with active PDF clips, associates
drawings with captions below them, and merges nearby panels. The hierarchy and
four-chart figure now each produce a complete crop instead of label fragments.
Tests cover clipped backgrounds, adjacent panels, neighboring figures, decorative
rules, rotation and truncated responses.

Captionless drawings, captions above figures, unusual layouts and full-page scans
remain limitations. Crop recovery and correct number transcription do not establish
faithful interpretation or improved RAG answers.
