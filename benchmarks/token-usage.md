# Token estimate for the existing PDF sample

Eight readable PDFs, 635 pages; one empty input excluded. Counts measured locally with tiktoken 0.14.0 using o200k_base and cross-checked with cl100k_base. No document was sent to a model API.

Raw text: PyMuPDF page.get_text("text"), concatenated in page order. Unclean Markdown: saved MarkItDown 0.1.7 output. Clean Markdown: saved pdf2md 0.2.0 output, with --no-toc. Entire output files counted, including metadata and markup. No additional cleanup or summarization applied.

## Measured text counts (o200k_base)

| Sample | Pages | Raw PDF text | MarkItDown | pdf2md | Saving vs MarkItDown |
|---|---:|---:|---:|---:|---:|
| sample-1 | 19 | 8,373 | 8,169 | 7,819 | 4.28% |
| sample-2 | 15 | 17,007 | 32,689 | 16,154 | 50.58% |
| sample-4 | 10 | 9,626 | 9,698 | 9,361 | 3.47% |
| sample-5 | 10 | 12,240 | 13,908 | 11,034 | 20.66% |
| sample-6 | 6 | 4,306 | 5,557 | 3,716 | 33.13% |
| sample-7 | 208 | 92,673 | 83,055 | 84,564 | -1.82% |
| sample-8 | 10 | 13,711 | 13,866 | 12,528 | 9.65% |
| sample-9 | 357 | 357,122 | 409,853 | 314,680 | 23.22% |
| Total | 635 | 515,058 | 576,795 | 459,856 | 20.27% |

Aggregate saving: 55,202 tokens (10.72%) versus raw text and 116,939 tokens (20.27%) versus MarkItDown. cl100k_base gives 522,904 / 585,077 / 466,170 tokens respectively, with 10.85% / 20.32% savings.

## Full PDF inputs

[OpenAI file-input documentation](https://developers.openai.com/api/docs/guides/file-inputs) describes PDF processing as extracted text plus page images for vision-capable models. Local raw-text counts are only a proxy for provider extraction; exact full-PDF usage needs the selected model, image detail, and actual API accounting.

Illustrative sensitivity calculation only: full PDF tokens = 515,058 + 635 × assumed image tokens per page. At an assumed 500 tokens/page, that is 832,558 tokens and 44.8% fewer for clean Markdown. At 1,000 tokens/page, that is 1,150,058 and 60.0% fewer. These assumptions are not measured costs or a provider-specific range. Image interpretation is also lost unless relevant figures are separately supplied.

## Interpretation and limitations

- Aggregate sums are corpus totals, not a suggestion to send all documents in one request.
- Model tokenizers, provider extraction, prompts, tool calls, generated responses, and caching change real usage and billing.
- Fewer tokens do not prove better fidelity: omissions and structural differences also affect counts. Prior spot checks are not a full content-preservation audit.
- This development sample informed converter improvements and is dominated by a 357-page book; it is not a representative held-out benchmark.
- Selective chapter retrieval can further reduce loaded context, but that is a separate workflow benefit. For illustration, 5,000 retrieved tokens versus the book's 314,680 clean tokens is 98.4% less document context, excluding indexing/skill-generation costs and other agent context. This is not a measured retrieval result.

## Reproducing the counting method

Install optional analysis dependencies `tiktoken==0.14.0` and `pymupdf==1.28.2` in a separate environment. Generate MarkItDown 0.1.7 and pdf2md 0.2.0 outputs for the same input, using `--no-toc` for pdf2md. Count complete output files without stripping metadata or markup:

```python
from pathlib import Path
import pymupdf
import tiktoken

enc = tiktoken.get_encoding("o200k_base")
with pymupdf.open("input.pdf") as doc:
    raw = "".join(page.get_text("text") for page in doc)
for label, text in (
    ("raw", raw),
    ("markitdown", Path("markitdown.md").read_text(encoding="utf-8")),
    ("pdf2md", Path("pdf2md.md").read_text(encoding="utf-8")),
):
    print(label, len(enc.encode(text, disallowed_special=())))
```

Repeat with `cl100k_base` to assess tokenizer sensitivity. Sum each representation's counts across files, then compute `100 * (1 - clean_tokens / baseline_tokens)`. The sample's source documents and full outputs remain private; these instructions reproduce the method on your own files, not the exact private dataset.
