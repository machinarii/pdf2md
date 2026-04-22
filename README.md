# Book Cleaner CLI

Node.js/TypeScript CLI that turns PDF / EPUB / TXT into a clean Markdown file with a single deterministic cleanup pass. No LLM required.

## What it does

For each input file:

1. Detects the file format (PDF / EPUB / TXT) and validates it.
2. Extracts text — embedded PDF text, EPUB chapters, or runs Tesseract OCR for image PDFs.
3. Runs `TextCleanerService` — deterministic cleanup ported from `txt-cleaner.py`: Unicode / ligature / smart-quote normalization, page-number and TOC-leader removal, repeated header/footer dedup, hyphen-break rejoining, paragraph rewrap, OCR artifact fixes.
4. Writes the cleaned result next to the source file as `<basename>.md`.
5. Deletes the intermediate `book-artifacts/<book>/` directory (keep with `--keep-artifacts`).

The pipeline is fully local and offline. No API calls. No model required.

## Install

```bash
git clone <repo>
cd book-cleaner-cli-ollama
npm install
npm run build
npm link            # puts `clean-book` on your PATH
```

If `npm link` hits permission errors on Homebrew Node, set a user-writable prefix first:

```bash
mkdir -p ~/.npm-global
npm config set prefix "$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$PATH"   # add to ~/.zshrc to persist
```

## Usage

```bash
clean-book some-report.pdf                 # writes some-report.md next to source
clean-book -s any.pdf                      # skip boundary prompt (process whole file)
clean-book --keep-artifacts any.pdf        # preserve book-artifacts/<book>/
clean-book -v -l debug any.pdf             # verbose + debug logs
```

Run `clean-book --help` for the full option list.

### Filename convention (optional)

If you name files `<author>#<title>[#<book-index>].<ext>`, the CLI fills the metadata automatically; otherwise it falls back to `author=Unknown`, `title=<basename>`.

### Text boundaries

On an interactive terminal, the CLI prompts for "text before first chapter" / "text after last chapter" so it can trim front/back matter before cleanup. Skip the prompt with `-s` to process the whole file. Non-interactive shells skip automatically.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | `debug` / `info` / `warn` / `error` / `fatal` |
| `CONFIG_DIR` | Override the `book-artifacts/` location (absolute path) |
| `OUTPUT_DIR` | Default output dir for the `-o` flag |

No API keys, no model, no network.

## Development

```bash
npm run dev -- some.pdf       # swc-node, no build step
npm run build                  # swc → dist/
npm run lint                   # biome
npm test                       # jest
npm run typecheck              # tsc --noEmit
```

### Project structure

```
src/
├── cli/               # Commander.js entrypoint
├── pipeline/          # DataLoadingPhase + PipelineManager
│   └── phase_1_Text_Extraction_And_Format_Processing/
│       ├── step_1_File_Format_Detection_And_Validation/
│       └── step_2_Text_Extraction/
├── services/          # OCRService, TextCleanerService, ConfigService, …
├── utils/             # ArtifactsDir, FileUtils, TextUtils, AppError, ChalkUtils
├── types/             # Shared TypeScript types
└── constants.ts
tests/                 # Jest unit tests
book-artifacts/        # Manifests + per-book intermediate output
.github/workflows/     # CI
```

Key service docs:

- [`src/services/TextCleanerService.md`](src/services/TextCleanerService.md) — the cleanup passes and their order
- [`src/pipeline/phase_1_Text_Extraction_And_Format_Processing/README.md`](src/pipeline/phase_1_Text_Extraction_And_Format_Processing/README.md) — pipeline flow

## License

MIT — see `LICENSE`.
