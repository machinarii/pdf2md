# Phase 1: Text Extraction & Format Processing

The only phase the CLI runs. Takes a raw input file (PDF / EPUB / TXT) and produces cleaned text. No LLM involved.

```
phase_1_Text_Extraction_And_Format_Processing/
├── step_1_File_Format_Detection_And_Validation/
└── step_2_Text_Extraction/
```

| Step | Component | Purpose |
|------|-----------|---------|
| 1 | `FileFormatDetector` | Magic-number + structural validation (PDF / EPUB / TXT) |
| 2 | `TextExtractor` | Extract text per book-manifest boundaries; runs Tesseract OCR for image PDFs |
| — | `TextCleanerService` (invoked from `DataLoadingPhase`) | Deterministic cleanup: Unicode, ligatures, page numbers, hyphen rejoining, repeated header/footer dedup, paragraph rewrap, OCR artifact fixes |

See `src/services/TextCleanerService.md` for the cleanup pass order and rationale.

## Data flow

```
input file
  → step 1: format detection
  → step 2: text extraction (embedded text + Tesseract OCR if needed)
      → writes book-artifacts/<book>/phase1/step2.txt (+ step2.ocr)
  → TextCleanerService.clean() on both text streams
      → writes step2-cleaned.txt (+ step2-cleaned.ocr)
  → CleanBookCommand.finalizeOutput() picks the best cleaned file
      → writes <source-basename>.md next to the source file
      → deletes book-artifacts/<book>/ unless --keep-artifacts
```

## Configuration

Book-specific manifest files live under `book-artifacts/<author>#<title>/book-manifest.yaml`. The manifest can optionally specify text boundaries that trim front/back matter before cleanup:

```yaml
author: "Author Name"
title: "Book Title"
text-before-first-chapter: "INTRODUCTION"
text-after-last-chapter: "APPENDIX"
# OR for paginated PDFs:
first-author-content-page: 5
last-author-content-page: 120
```

Pass `-s` / `--skip-start-marker` or run in a non-TTY shell to skip boundary prompting and process the whole file.

## Error handling

- Format detection failures throw `AppError(INVALID_FORMAT)`.
- Text extraction gracefully downgrades to whole-file when boundaries are missing.
- OCR runs on image PDFs automatically via Tesseract (`deu`/`eng` traineddata ships in the repo root).

## Testing

```bash
npm test -- --testPathPatterns=TextCleaner
```
