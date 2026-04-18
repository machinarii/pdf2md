# Phase 1: Text Extraction & Format Processing

## Overview

Phase 1 turns a raw input file (PDF/EPUB/TXT) into clean text plus a corrected book-structure manifest. It is orchestrated by `DataLoadingPhase.ts` and runs before the LLM-heavy phases.

## Steps

```
phase_1_Text_Extraction_And_Format_Processing/
├── DataLoadingPhase.ts                           (in src/pipeline/, orchestrator)
├── PhaseExecutionSummary.ts
├── step_1_File_Format_Detection_And_Validation/
├── step_2_Text_Extraction/
├── step_3_Book_Structure_Inference/
├── step_3_Text_Auto_Correction_OLD/              (deprecated, kept for reference)
├── step_4_Structure_Normalization/
├── step_5_Convert_Footnotes_To_Endnotes/
└── step_6_OCR_Text_Quality_Enhancement/
```

| Step | Component | Purpose |
|------|-----------|---------|
| 1 | `FileFormatDetector` | Magic-number + structural validation of PDF/EPUB/TXT |
| 2 | `TextExtractor` | Extract text per book-structure boundaries; runs Tesseract OCR for image PDFs |
| — | **`TextCleanerService`** (post-step-2) | Deterministic pre-LLM cleanup: Unicode, ligatures, page numbers, hyphen rejoining, repeated header/footer removal, paragraph rewrap |
| 3 | `BookStructureAnalyzer` + `StructureInferrer` | Chunk cleaned text, send to Ollama, merge corrections into the book manifest |
| 4 | `step_4_Structure_Normalization` | Normalize heading/section structure |
| 5 | `step_5_Convert_Footnotes_To_Endnotes` | Footnote → endnote conversion |
| 6 | `step_6_OCR_Text_Quality_Enhancement` | OCR-specific character/word corrections |

The `_OLD` Text Auto Correction directory is superseded by the combination of `TextCleanerService` (deterministic) and Ollama-based inference (LLM). It remains in the tree only for reference.

## Data flow

```
input file
  → step 1: format detection
  → step 2: text extraction (embedded text + OCR if needed)
     → writes book-artifacts/<book>/phase1/step2.txt (+ step2.ocr)
  → TextCleanerService.clean() on both txt and ocr
     → writes step2-cleaned.txt (+ step2-cleaned.ocr)
  → step 3: book structure inference via Ollama (chunked)
     → updates book-manifest.yaml
  → steps 4–6: structure normalization, footnote conversion, OCR QC
```

See `../../services/TextCleanerService.ts` for the deterministic cleanup passes (pass order is load-bearing) and `../../services/OllamaService.ts` for the LLM client.

## Configuration

Phase 1 uses book-specific manifest files:

```yaml
# book-artifacts/<author>#<title>/book-manifest.yaml
author: "Author Name"
title: "Book Title"
first-author-content-page: 5
last-author-content-page: 120
# or for non-paginated files:
text-before-first-chapter: "INTRODUCTION"
text-after-last-chapter: "APPENDIX"
```

LLM-related env vars (see top-level README for full list):

- `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`)
- `OLLAMA_MODEL` (default `qwen3:32b`)
- `OLLAMA_NUM_CTX` (default `32768`)

## Error handling

- Format detection: unsupported formats fail fast with `AppError`.
- Text extraction: missing boundaries downgrade to whole-file extraction with a warning.
- Ollama reachability: `OllamaService` retries once on `ECONNREFUSED`; `StructureInferrer` retries once on invalid JSON. After retries, returns an empty inference result so the pipeline can continue.

## Testing

```bash
npm test                                   # all tests
npm test -- --testPathPatterns=TextCleaner # deterministic cleaner passes
npm test -- --testPathPatterns=Ollama      # OllamaService (mocked)
OLLAMA_E2E=1 npm test -- --testPathPatterns=Ollama  # live Ollama
```

## Status

Steps 1 and 2 are production-ready. Steps 3 (book structure inference) and the `TextCleanerService` integration are wired in. Steps 4–6 still have placeholder implementations — see each step's README for status.
