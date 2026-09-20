# Visual-context diagnostic evaluation

Four figures from two research PDFs were visually reviewed: a hierarchical
architecture diagram, four training charts, a radar chart with a numeric table,
and a game-board image. These are diagnostic cases, not a representative accuracy
benchmark. Source PDFs and raw model responses remain in local test artifacts.

## Cropping fix

Previously, the two vector figures produced three small crops covering label
fragments. The revised detector uses drawing paths intersected with their active
PDF clips, associates drawings with captions below them, and merges nearby panels.
It now produces one complete crop for the hierarchy and one containing all four
charts. Both raster figures are still captured. All four crops were visually
checked. Separate tests cover clipped backgrounds, multi-panel grouping,
neighboring figures, decorative rules, page rotation, and truncated responses.

## GLM-5.3-Flash cloud

Tested `glm-5.3-flash:cloud` through the user-designated Ollama server with corrected
automatic crops and extracted captions. A local test wrapper supplied the server
address to the existing helper. Final settings: temperature 0, optional thinking
disabled, 1,600 output tokens. This cloud-model test sends crops and captions to
the model provider; the baseline local converter does not require a model.

| Case | Useful result | Remaining problems |
|---|---|---|
| Hierarchy | Recognizes both panels, E3/E2/E1 labels, and the main update loop | Some connections are inferred; guesses the meaning of output labels |
| Four charts | Recognizes all panels, both series, and the main qualitative trends | Some approximate spike positions and categorical claims are inaccurate |
| Radar/table | All 32 printed numeric cells reproduced correctly in a five-column Markdown table | Caption supplied by the converter is incomplete; additional prose exceeds the requested brevity |
| Board | Recovers the roughly 5-column, 8-row layout and four player labels | Misstates some pawn colors/counts and speculates about player-to-zone correspondence |

The backend included planning prose in the response despite disabled thinking.
A diagnostic `/api/chat` request also exhibited this behavior. This is not clean,
trusted RAG context without review. The current converter does not reliably
identify untagged planning text or verify model claims.

The original 600-token budget yielded an empty description for one figure and
incomplete descriptions for others. Increasing headroom produced nonempty
descriptions for all four. Responses explicitly stopped by the output limit now
fall back to the crop and extracted labels instead of publishing incomplete text.

## Earlier GLM-OCR comparison

On manually selected complete crops, the existing description prompt took
1.84–4.62 seconds per image (2.76 seconds mean, one run each). It recovered all
32 table values but produced malformed/duplicated tables, incorrect chart claims,
and an invented 4×4 board layout. Model-specific recognition prompts still caused
repetition and unsupported interpretation.

These runs used different crops, prompts, and output budgets from the final Flash
run; they do not establish a controlled model ranking or speed comparison.

## Limits

A subsequent pattern-focused prompt elicited useful table-backed comparisons,
but Flash incorrectly called Player 2 lowest in Wood Products Carbon (37); Player
3 is lower (33). Board counts in a full-image description were frequently wrong.
After adding explicit pip/marker-count instructions, a focused board request hit
the output limit and was rejected. These follow-ups reinforce that better prompts
do not replace quantitative validation or establish reliable automatic counting.

Whole-figure recovery is improved for these cases, not solved for all documents.
The detector currently relies on a nearby numbered English figure caption below
the drawing. Captionless figures, captions above drawings, unusual clipping or
layouts, and model hallucinations remain limitations. Correct table transcription
does not establish faithful chart interpretation or improved retrieval quality.
