# OllamaService

Thin client for a local [Ollama](https://ollama.com) instance using its OpenAI-compatible `/v1/chat/completions` endpoint. No SDK — raw `fetch`.

## Configuration (env vars)

| Variable | Default | Notes |
|----------|---------|-------|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Trailing slash is stripped |
| `OLLAMA_MODEL` | `qwen3:32b` | Any model you've pulled into Ollama |
| `OLLAMA_NUM_CTX` | `32768` | Must be positive; rejected at construction time if not numeric |

No API key. Ollama is local.

## Behavior

- Every request body includes `options: { num_ctx }` so the local model loads with the configured context window.
- `jsonMode: true` adds `response_format: { type: 'json_object' }` — used by `sendStructureInferenceRequest`.
- On `ECONNREFUSED` / `fetch failed` / `ENOTFOUND`, retries the request **once** before throwing.
- Non-2xx HTTP responses throw `AppError(API_ERROR)` with the response body truncated to 500 chars.
- Timeout is 120s via `AbortController`.

## API

```ts
import { OllamaService } from '@/services/OllamaService';

const service = new OllamaService(logger);

// Generic chat
const res = await service.sendChatRequest({
    messages: [{ role: 'user', content: 'Hi' }],
    temperature: 0.2,
    maxTokens: 500,
    jsonMode: false,
});
// res.content, res.usage, res.finish_reason

// JSON-mode prompt for structure inference (used by StructureInferrer)
const text = await service.sendStructureInferenceRequest(prompt);

// Health check
const ok = await service.testConnection();
```

## Tests

```bash
# Mocked fetch (fast, always runs)
npm test -- --testPathPatterns=OllamaService

# Hits a real Ollama instance — requires ollama serve + model pulled
OLLAMA_E2E=1 OLLAMA_MODEL=qwen3:32b npm test -- --testPathPatterns=OllamaService
```

## Caller expectations

`StructureInferrer` layers JSON-parse retry (1 retry) on top of `sendStructureInferenceRequest`. Failures after retries return an empty inference result rather than propagating — the pipeline continues on.

Add another retry layer in the caller (not this service) if you need per-prompt resilience beyond reconnect retry.
