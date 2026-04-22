# BookStructureService

Loads, caches, and updates the per-book `book-manifest.yaml` file that lives under `book-artifacts/<author>#<title>/`. The manifest holds:

- Author / title / book-index metadata
- Optional text boundaries (`text-before-first-chapter`, `text-after-last-chapter`, or page ranges)
- Book-type hint (used by `BookTypesService` to look up publisher-specific text-removal regex in `book-types.yaml`)

## Files in this directory

| File | Purpose |
|------|---------|
| `BookStructureService.ts` | Manifest CRUD, caching, file-info reconciliation |
| `BookTypesService.ts` | Loads `book-artifacts/book-types.yaml`, returns text-removal regex patterns |

## Typical usage

```ts
import { BookStructureService, BookTypesService } from '@/services/BookStructureService';

const svc = new BookStructureService(logger, artifactsDir);
const manifest = await svc.loadBookManifest(metadata);

const types = new BookTypesService(logger, configService);
const patterns = await types.getTextRemovalPatterns(); // union of all types' patterns
```

`getTextRemovalPatterns()` called without a book-type returns the **union** of every type's regex list from `book-types.yaml` — useful for ad-hoc PDFs where the publisher isn't known.

## Error handling

- Missing manifest → prompts the CLI layer to create one.
- Failed manifest loads throw `AppError(CONFIG_INVALID)`.
- Unknown book types fall back to the union-of-all patterns and log a warning.

No LLM / network / API calls. Everything is local YAML + regex.
