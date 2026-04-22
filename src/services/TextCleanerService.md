# TextCleanerService

The entire text-cleaning stage. Deterministic, regex-based, fully offline. TypeScript port of `txt-cleaner.py`.

## Why it exists

Raw PDF / OCR text is littered with artifacts a regex can strip reliably: page numbers, ligatures, smart quotes, running headers, hyphenated line-breaks, ResearchGate front-matter, OCR junk. A rule-based pass produces reproducible diffs you can inspect via `--keep-artifacts`.

## Pass order (load-bearing)

```
0.   Unicode normalization    (ligatures, smart quotes, control chars, exotic whitespace)
0b.  ResearchGate / SlideShare / Academia.edu multi-line block stripping
1.   Line-level removal       (page numbers, TOC leaders, footnote markers, bullets,
                               boilerplate, standalone URLs, OCR junk,
                               spaced-letter OCR artifacts, repeated headers/footers)
1b.  Spaced-letter rejoining  (ocr mode only — "w i t h" → "with")
2.   Hyphenated line-break rejoining
3.   Paragraph rewrapping     (merge hard-wrapped lines)
4.   Blank-line collapsing
```

Swapping 1b and 2 breaks spaced-letter content. Running pass 1 before pass 0 breaks pattern matching against smart-quote / ligature content. Do not reorder.

## Source modes

- `pdf` (default) — standard cleaning for PyMuPDF / pdf-parse extracted text.
- `ocr` — more aggressive OCR junk detection, spaced-letter rejoin enabled.

The `slides` and `academic` modes from the Python reference script are not ported; this codebase targets books.

## Pipeline integration

Wired into `DataLoadingPhase.ts` after text extraction:

```
step_2_Text_Extraction
  → writes book-artifacts/<book>/phase1/step2.txt  (and step2.ocr if OCR was run)
  → TextCleanerService.clean(txt, { source: 'pdf' })
  → TextCleanerService.clean(ocr, { source: 'ocr' })
  → writes step2-cleaned.txt  (and step2-cleaned.ocr)
  → CleanBookCommand.finalizeOutput() writes <source-basename>.md next to source
```

Stats land in the Pino log at `info` level — you see exactly what each pass stripped on every run.

## API

```ts
import { TextCleanerService, cleanText } from '@/services/TextCleanerService';

// Through the service (logs to Pino):
const service = new TextCleanerService(logger);
const { cleanedText, stats } = service.clean(rawText, { source: 'ocr' });

// Pure function (no logger, useful in tests):
const { cleanedText, stats } = cleanText(rawText, {
    source: 'pdf',
    aggressive: false,
    removeBoilerplate: true,
    removeUrls: true,
    removeToc: true,
    extraPatterns: ['^custom\\s+line$'],
});
```

The returned `stats` object contains per-pattern removal counts, repeated-line detection counts, and the adaptive repeat threshold that was used.

## Tests

```bash
npm test -- --testPathPatterns=TextCleanerService
```

15 unit tests cover each pass plus the integration cases that are easiest to regress (isolated page numbers vs inline, hyphen rejoin vs paragraph break, etc.). Add fixtures here before changing regex patterns.

## Known gaps vs the Python reference

- `slides` and `academic` source modes not ported.
- `find_fuzzy_repeated_lines` uses a bigram-overlap ratio instead of Python's `SequenceMatcher`. Close enough for header/footer dedup at the 0.85 threshold; may diverge on edge cases.
- Python patterns are English-biased (boilerplate phrases, ligature table). German-specific boilerplate (`Alle Rechte vorbehalten` etc.) — one pattern added; extend `BOILERPLATE_PATTERNS` as needed.
