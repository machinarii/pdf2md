# book-cleaner-cli → Ollama migration plan

> **Status: Completed.** All phases executed. DeepSeek removed, Ollama wired in,
> deps modernized (Node 24, Biome 2, Jest 30, pino 10, …), `TextCleanerService`
> ported from `txt-cleaner.py` and wired into the pipeline between extraction
> and structure inference. `npm run build` / `lint` / `test` / `audit` all clean.
> See the top-level `README.md` and `src/pipeline/phase_1_.../README.md` for the
> resulting architecture. This document is retained as a historical record.


**Context:** Fork of archived [cypherpunk-academy/book-cleaner-cli](https://github.com/cypherpunk-academy/book-cleaner-cli). Repo currently hardcodes DeepSeek Chat and was last touched September 2025 (~7 months of dep drift). Goals:

1. **Rip out DeepSeek entirely, replace with Ollama.** No provider abstraction.
2. **Modernize all dependencies** to current versions, including Node itself.
3. **Add deterministic pre-LLM text cleaning** using the existing `txt-cleaner.py` as a reference implementation — do cheap, predictable cleanup before spending LLM tokens.

Personal fork — simplicity wins.

**Target stack:** Node 22 LTS (or current LTS at time of work), TypeScript latest, Ollama at `http://localhost:11434` (or Tailscale IP from Lume VM), primary model `qwen3:32b` with `num_ctx` ≥ 32K.

**Existing asset to port/reference:** `txt-cleaner.py` — a ~940-line deterministic text cleaner with source-mode switching (`pdf` / `ocr` / `slides` / `academic`), Unicode normalization, repeated header/footer detection, hyphen-break rejoining, paragraph rewrapping, and ResearchGate/academic boilerplate stripping. Battle-tested, no LLM calls.

---

## What we already know

From a grep of the repo:

- `src/services/DeepSeekService.ts` — the service. To be deleted.
- `src/services/ConfigService.ts:229-254` — reads DeepSeek env vars. To be rewritten.
- `src/services/BookStructureService/StructureInferrer.ts:105` — `// TODO: Implement actual DeepSeek Chat API call in Phase 3`. **Verify in Phase 0 whether the HTTP call is real or stubbed.**
- `src/types/index.ts:450` — `AIProvider = 'deepseek' | 'openai' | 'anthropic'`. Narrow to `'ollama'` or delete.
- `src/constants.ts:247,253-255,430-432` — provider strings, model names, env var names.
- Toolchain present: TypeScript, SWC (`.swcrc`), Biome (`biome.json`), Jest (`jest.config.js`), Pino (per README).
- Pipeline structure: Phase 1 (Data Loading) → Phase 2 (Text Normalization & AI Cleaning) → Phase 3 (Evaluation) → Phase 4 (AI Enhancements, future).

Ollama's `/v1` endpoint is OpenAI-compatible. Raw `fetch` is sufficient; no SDK needed.

---

## Goal

End state:

- Zero references to DeepSeek.
- `OllamaService` handles all LLM calls.
- Deterministic cleanup runs *before* the LLM on every chunk — fewer tokens, cleaner input, better output.
- All dependencies current, Node on current LTS, build + lint + test green.

**Non-goals:**

- No multi-provider abstraction.
- No OCR engine changes (Tesseract stays).
- No streaming if not present.
- No framework swaps (staying with Jest, Biome, SWC, Pino — just bumping versions).

---

## Phase 0 — Discovery

Read-only. No code changes.

### 0.1 LLM call path

1. Read `src/services/DeepSeekService.ts` end-to-end. Verify:
   - Real HTTP call or synthesized response at ~line 129?
   - Request body shape — OpenAI-compatible or DeepSeek-specific?
   - Error / exit path.
2. Read `src/services/BookStructureService/StructureInferrer.ts` lines 100–250. Confirm `sendStructureInferenceRequest` invocation + expected response shape (text vs JSON).
3. Grep for other LLM call sites:
   ```
   grep -rni "chat.completions\|sendStructureInference\|DeepSeek\|AI_PROVIDER\|deepseek-chat" src/
   ```
4. Read one `configs/*.config` if present.

### 0.2 Existing text normalization code

Before deciding whether to port `txt-cleaner.py` or shell out to it, audit what's already there:

1. Find the existing normalization code. Likely candidates:
   ```
   grep -rni "normalize\|cleanup\|ligature\|hyphen\|rewrap\|spaced" src/ --include="*.ts"
   find src/pipeline -type d
   ```
   Based on the README, Phase 2 has "heading normalization" and "safe text replacements" — look for those files.
2. For each normalization function found, compare feature set against `txt-cleaner.py`:

   | Capability                                       | txt-cleaner.py | book-cleaner-cli |
   |--------------------------------------------------|----------------|------------------|
   | Unicode / ligature normalization                 | ✓              | ?                |
   | Smart quote / dash normalization                 | ✓              | ?                |
   | Context-aware page number removal                | ✓              | ?                |
   | TOC leader line removal                          | ✓              | ?                |
   | Hyphenated line-break rejoining                  | ✓              | ?                |
   | Spaced-letter OCR artifact fix                   | ✓              | ?                |
   | Repeated header/footer detection (adaptive)      | ✓              | ?                |
   | Fuzzy header/footer matching                     | ✓              | ?                |
   | Paragraph rewrapping                             | ✓              | ?                |
   | ResearchGate / academic boilerplate stripping    | ✓              | ?                |
   | OCR junk detection (low alpha ratio)             | ✓              | ?                |
   | Source-mode switching (pdf/ocr/slides/academic)  | ✓              | ?                |

   Fill in the "?" column. Anything marked as missing or weak is a candidate for Phase 3 port.

### 0.3 Dependency audit

1. Dump current state:
   ```
   cat package.json
   node --version
   cat .nvmrc 2>/dev/null || echo "no .nvmrc"
   ```
2. Run `npx npm-check-updates` (no `-u`). Capture output.
3. Check Node LTS status at [nodejs.org](https://nodejs.org/en/about/previous-releases) — identify current Active LTS.
4. Flag any abandoned deps + suggested replacement.
5. Run `npm audit`, capture.

### 0.4 Output of Phase 0

Before any code changes, post back:

- Real HTTP call or stub?
- One LLM call site or several?
- Raw fetch or SDK?
- Response format (text vs JSON)?
- Existing normalization feature coverage (table above filled in).
- `package.json`, Node version, `ncu` output, `npm audit` output.
- Any abandoned deps + replacement candidate.

---

## Phase 1 — Replace DeepSeek with Ollama

Do this *before* dep updates and preprocessing work — shrinks the codebase first, avoids updating deps of code about to be deleted.

### 1.1 New env vars

Replace `DEEPSEEK_*` entries in `src/constants.ts` `ENV_VARS` with:

```ts
OLLAMA_BASE_URL: 'OLLAMA_BASE_URL',  // e.g. http://localhost:11434/v1
OLLAMA_MODEL:    'OLLAMA_MODEL',     // e.g. qwen3:32b
OLLAMA_NUM_CTX:  'OLLAMA_NUM_CTX',   // e.g. 32768
```

No API key env var. Remove `DEEPSEEK_API_KEY`, `DEEPSEEK_REST_API_KEY`, `DEEPSEEK_REST_API_URI`, the whole `AI_PROVIDERS.DEEPSEEK` block.

### 1.2 Create `OllamaService`

New file: `src/services/OllamaService.ts`. Mirrors `DeepSeekService`'s public methods so callers change minimally. Internals:

- Raw `fetch` against `${OLLAMA_BASE_URL}/chat/completions`.
- Config loaded from env; throws at construction if `OLLAMA_BASE_URL` or `OLLAMA_MODEL` missing.
- Always includes `options: { num_ctx: Number(OLLAMA_NUM_CTX ?? 32768) }`.
- One retry on `ECONNREFUSED` before exiting.

Request body:

```ts
{
  model: this.config.model,
  messages: request.messages,
  temperature: request.temperature ?? 0.2,
  max_tokens: request.maxTokens,
  response_format: request.jsonMode ? { type: 'json_object' } : undefined,
  options: { num_ctx: this.config.numCtx },
  stream: false,
}
```

Response: OpenAI shape, pull `choices[0].message.content`.

### 1.3 Delete `DeepSeekService`

Delete the file. Update imports in `StructureInferrer.ts` + any other call sites.

### 1.4 Rewrite `ConfigService.ts`

Lines 229–254 → Ollama-only config. Drop `provider` field.

### 1.5 Types and constants cleanup

- `src/types/index.ts:450` — `AIProvider = 'ollama'` or delete type.
- `src/constants.ts` — remove all DeepSeek entries.

---

## Phase 2 — Dependency modernization

Clean codebase now. Update deps.

### 2.1 Node runtime

- Update `engines.node` in `package.json` to current LTS.
- Create / update `.nvmrc`.

### 2.2 Dev dependencies — bulk update

Safe to bump; failures surface in build/lint/test:

- `typescript` — latest. Review `tsconfig.json` for new strict flags (e.g. `noUncheckedIndexedAccess`, `verbatimModuleSyntax`); only adopt if cleanup is bounded.
- `@types/node` — match runtime.
- `@swc/core`, `@swc/cli` — latest; verify `.swcrc`.
- `@biomejs/biome` — latest; run `npx biome migrate` if needed; re-run `biome check --apply`.
- `jest`, `@types/jest`, `@swc/jest` — latest; read migration guide for major bumps.

### 2.3 Runtime dependencies — per-package evaluation

One major version at a time:

- `pino` — transport config changed around v8 → v9; verify.
- CLI framework (`commander` or `yargs`) — breaking changes possible.
- YAML parser (`js-yaml`) — stable.
- PDF parser — if `pdf-parse`, consider `pdfjs-dist` or `unpdf` (pdf-parse is effectively unmaintained).
- EPUB parser — consider replacements if current is stale.
- Tesseract wrapper — `tesseract.js` has had breaking changes; verify OCR output unchanged.
- `dotenv` — consider Node 20+ built-in `--env-file` flag as replacement.

### 2.4 Security

- `npm audit` after updates. Evaluate remaining high/critical per-case.
- Add `.npmrc` with `audit-level=high`.

### 2.5 Lockfile hygiene

- Delete and regenerate `package-lock.json`.

### 2.6 Verification gate

- `npm install` clean.
- `npm run build` clean.
- `npm run lint` clean (Biome fixes in a separate cosmetic commit).
- `npm test` passes.

Bisect by rolling back one dep at a time if anything breaks.

---

## Phase 3 — Deterministic preprocessing (port from txt-cleaner.py)

**The highest-leverage change.** Every chunk that flows into the LLM should first pass through deterministic cleanup. Reasons:

- Saves tokens (don't pay qwen3 to strip page numbers).
- Improves LLM output quality (cleaner input → cleaner output).
- Faster and more predictable than letting the LLM handle it.
- Easier to debug: deterministic stages produce reproducible diffs.

### 3.1 Decide: port vs shell out

**Option A (recommended):** Port `txt-cleaner.py` to TypeScript as `src/services/TextCleanerService.ts`. Unified stack, no Python runtime dependency, integrates cleanly into the phase system.

**Option B (pragmatic shortcut):** Keep `txt-cleaner.py` in the repo, shell out via `child_process.spawn`. Faster to integrate, but adds a Python runtime dep and makes packaging/distribution harder.

Default to Option A unless Phase 0 turns up a reason to defer (e.g. the existing normalization code already covers most of it).

### 3.2 Port scope — in priority order

Port only what Phase 0 flagged as missing or weak. Likely priority:

1. **Unicode normalization** (Pass 0 in txt-cleaner.py)
   - Ligature map (`ﬁ` → `fi`, etc.)
   - Smart quote / dash normalization
   - Zero-width / exotic whitespace handling
   - Form-feed → newline
2. **Hyphenated line-break rejoining** — essential for OCR'd books. Single-page effort to port.
3. **Paragraph rewrapping** — merges hard-wrapped lines back into prose. Handles mid-sentence breaks via last-char / first-char heuristics.
4. **Repeated header/footer detection** — adaptive threshold `2 + sqrt(lines / 25)`. Critical for books where the same running header appears on every page.
5. **Page number removal with context awareness** — isolated bare numbers (blank-before-and-after) are page numbers; inline numbers are data. Do not strip "Page 1" inside a PageRank example.
6. **Spaced-letter OCR fix** — `w i t h a r e` → `with are`. Common slide/poster OCR artifact.
7. **TOC leader removal** — `Chapter 1 .......... 5`.
8. **OCR junk detection** — low alpha ratio, but protected against math / tables / references.
9. **Fuzzy header/footer matching** (aggressive mode only) — `SequenceMatcher` equivalent in TS. Use `fast-levenshtein` or similar.
10. **Source-mode switching** — book-cleaner-cli already knows PDF vs EPUB vs TXT input; add an `--ocr-mode` flag when the PDF was OCR'd (detectable via Tesseract comparison that's already in Phase 1).

### 3.3 Integration point

Insert the cleaner between text extraction (end of book-cleaner-cli's Phase 1) and LLM cleanup (Phase 2's AI step). Data flow:

```
extract text (PDF/EPUB/TXT)
  → (NEW) deterministic cleanup [source-mode aware]
  → existing heading normalization
  → structure inference via Ollama
  → AI text cleanup via Ollama
  → spell check
```

Structure inference benefits from cleaner input too — don't skip it.

### 3.4 Pass ordering is load-bearing

From `txt-cleaner.py`, the order is:

1. Unicode normalization (fix characters first)
2. RG / academic pre-pass (multi-line block stripping)
3. Line-by-line removal (page numbers, bullets, boilerplate, OCR junk)
4. Spaced-letter fix (must run before hyphen fix)
5. Hyphen-break rejoining
6. Paragraph rewrap
7. Collapse excessive blank lines

Preserve this order on port. Swapping 4 and 5 breaks spaced-letter content. Running line-level removal before Unicode normalization breaks pattern matching against smart-quote content.

### 3.5 Stats reporting

The Python script reports per-pattern removal counts. Port this too — it's invaluable for debugging why a book looks wrong after cleaning. Surface via Pino logger at `debug` level minimum, `info` at top-line counts.

### 3.6 Tests

- Unit tests for each pass, using small fixtures (10–20 line snippets).
- Golden-file tests: input → expected output for a short sample from `sample-book.txt`.
- Edge cases that must not regress: "Page 1" inside code/math context, tables with trailing hyphens, URLs that look like boilerplate.

---

## Phase 4 — Prompt / context adjustments for local models

Two likely friction points vs DeepSeek's hosted API:

1. **JSON output reliability.** If structure inference expects JSON (confirm Phase 0), wrap parsing in retry-on-parse-failure (1–2 retries). Pass `response_format: { type: 'json_object' }`.
2. **Chunk size vs context.** DeepSeek has 64K. `qwen3:32b` defaults to 32K (less as loaded). If chunker was tuned for 64K, halve chunks or bump `num_ctx` via Modelfile.

With deterministic cleanup in place (Phase 3), chunks are smaller and cleaner, which helps here. Tune against the post-preprocessing input, not raw extracted text.

**Deliverable:** single-chapter test run. Sensible → move on.

---

## Phase 5 — Validation

End-to-end on a real book.

Checklist:

- [ ] `npm run build`, `npm run lint`, `npm test` all clean.
- [ ] Delete / rewrite DeepSeek-specific tests.
- [ ] New unit tests: `OllamaService` + `TextCleanerService` passes.
- [ ] `OllamaService` e2e test (gated by `process.env.OLLAMA_E2E === '1'`).
- [ ] Manual run: `clean-book -v sample-book.txt` completes.
- [ ] Output quality spot-check.
- [ ] Compare token usage: before preprocessing vs after. Expect 20–40% reduction on OCR'd input.
- [ ] `grep -rni "deepseek" .` returns zero hits outside `node_modules` / git history.
- [ ] `npm audit` clean or consciously accepted.
- [ ] Node runtime matches `.nvmrc` matches `engines.node`.

---

## Phase 6 — README and docs

- Top-level `README.md` env block:
  ```
  OLLAMA_BASE_URL=http://localhost:11434/v1
  OLLAMA_MODEL=qwen3:32b
  OLLAMA_NUM_CTX=32768
  ```
- Remove all DeepSeek mentions from README + service READMEs.
- Add "Prerequisites": Ollama installed, model pulled, service running, Node version matching `.nvmrc`.
- Document the new preprocessing stage in the pipeline diagram if one exists.
- Credit `txt-cleaner.py` in the preprocessing module header comment if ported.

---

## Risks / open questions

1. **Stub risk.** If `DeepSeekService` never hit the network upstream, full pipeline has never run end-to-end. Budget extra Phase 5 time.
2. **Chunk size coupling.** Grep for hardcoded chunk sizes in Phase 0.
3. **German OCR target.** `deu.traineddata` + Rudolf Steiner example → German. Spot-check qwen3:32b on German. Also: `txt-cleaner.py` patterns are English-biased (boilerplate phrases, ligature table). German-specific boilerplate (`Alle Rechte vorbehalten`, etc.) may need adding.
4. **Resilience.** One retry on `ECONNREFUSED` minimum.
5. **Concurrency.** Local Ollama serializes. Hardcoded semaphore at 2 if needed.
6. **Dep update strictness cascade.** Don't expand scope chasing TS / Biome rule upgrades; note and defer.
7. **Preprocessing vs structure inference.** Aggressive cleanup could strip signal the structure inference needs (e.g. footnote markers may help detect footnote sections). Validate that chapter / structure detection still works post-preprocessing in Phase 5; tune cleanup aggressiveness per-pipeline-stage if needed.
8. **Port fidelity.** Regex behavior between Python and JS differs subtly (lookbehind support, Unicode property escapes, multiline flag semantics). Test each ported pass against matched fixtures before declaring done.

---

## Acceptance criteria

- `OLLAMA_BASE_URL=http://localhost:11434/v1 OLLAMA_MODEL=qwen3:32b clean-book sample-book.txt` runs to completion.
- `grep -rni "deepseek" src/` returns zero hits.
- `grep -rni "deepseek" README.md docs/ src/**/README.md` returns zero hits.
- No hardcoded model strings / URLs / context sizes outside `constants.ts` and `OllamaService.ts`.
- All deps on latest stable major (or pinned with comment explaining why).
- Node on current LTS; `.nvmrc` + `engines.node` agree.
- `npm audit` no high/critical.
- `npm test` passes, including new `TextCleanerService` unit + golden-file tests.
- Preprocessing reduces chunk token count by ≥20% on a sample OCR'd input.
- README reflects Ollama + preprocessing.

---

## Commit strategy

1. `chore: document current DeepSeek call path and dep state` (Phase 0 findings)
2. `feat: add OLLAMA_* env var constants`
3. `feat: introduce OllamaService`
4. `refactor: StructureInferrer uses OllamaService`
5. `refactor: ConfigService uses Ollama config`
6. `chore: remove DeepSeekService and related types/constants`
7. `chore: bump Node engine to <LTS> + update .nvmrc`
8. `chore: bump dev dependencies (TS, Biome, Jest, SWC)`
9. `style: apply Biome auto-fixes from updated rules`
10. `chore: bump runtime dependencies`
11. `chore: replace <abandoned-dep> with <replacement>` (one per replacement)
12. `feat: TextCleanerService scaffold with Unicode normalization`
13. `feat: TextCleanerService hyphen-break rejoining`
14. `feat: TextCleanerService paragraph rewrap`
15. `feat: TextCleanerService repeated header/footer detection`
16. `feat: TextCleanerService page number / TOC / bullet removal`
17. `feat: TextCleanerService OCR-specific passes (spaced letters, junk)`
18. `feat: integrate TextCleanerService into pipeline Phase 1 → 2 boundary`
19. `fix: retry on ECONNREFUSED, semaphore on concurrent LLM calls`
20. `docs: README + service READMEs updated for Ollama + preprocessing`
21. `test: OllamaService unit + e2e (gated); TextCleanerService golden-file tests`

Preprocessing gets one commit per pass for reviewability. Skip or combine if a pass is trivial.

---

## What to report back after Phase 0

Before touching any code:

- `DeepSeekService.ts` contents lines 100–200.
- Grep results for other LLM call sites.
- `StructureInferrer` expected response format.
- Any hardcoded chunk sizes / context assumptions.
- Full `package.json`.
- Current Node + `.nvmrc`.
- `npx npm-check-updates` output.
- `npm audit` output.
- Any abandoned dep + replacement candidate.
- **Filled-in normalization feature table** (from section 0.2) — which `txt-cleaner.py` capabilities are already covered vs missing.

Then proceed to Phase 1.
