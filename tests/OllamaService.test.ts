import type { LoggerService } from '@/services/LoggerService';
import { OllamaService } from '@/services/OllamaService';

function makeLogger(): LoggerService {
    const pinoStub = {
        debug: jest.fn(),
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
    };
    return {
        getConfigLogger: () => pinoStub,
        getPipelineLogger: () => pinoStub,
        debug: jest.fn(),
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
        fatal: jest.fn(),
    } as unknown as LoggerService;
}

describe('OllamaService — config loading', () => {
    const origEnv = { ...process.env };
    afterEach(() => {
        process.env = { ...origEnv };
    });

    it('uses defaults when env vars are unset', () => {
        process.env.OLLAMA_BASE_URL = undefined;
        process.env.OLLAMA_MODEL = undefined;
        process.env.OLLAMA_NUM_CTX = undefined;
        delete process.env.OLLAMA_BASE_URL;
        delete process.env.OLLAMA_MODEL;
        delete process.env.OLLAMA_NUM_CTX;
        const service = new OllamaService(makeLogger());
        const cfg = service.getConfig();
        expect(cfg.baseUrl).toBe('http://localhost:11434/v1');
        expect(cfg.model).toBe('qwen3:32b');
        expect(cfg.numCtx).toBe(32768);
    });

    it('honors env overrides and strips trailing slash', () => {
        process.env.OLLAMA_BASE_URL = 'http://remote:11434/v1/';
        process.env.OLLAMA_MODEL = 'mistral:latest';
        process.env.OLLAMA_NUM_CTX = '8192';
        const service = new OllamaService(makeLogger());
        const cfg = service.getConfig();
        expect(cfg.baseUrl).toBe('http://remote:11434/v1');
        expect(cfg.model).toBe('mistral:latest');
        expect(cfg.numCtx).toBe(8192);
    });

    it('rejects non-numeric OLLAMA_NUM_CTX', () => {
        process.env.OLLAMA_NUM_CTX = 'not-a-number';
        expect(() => new OllamaService(makeLogger())).toThrow(/OLLAMA_NUM_CTX/);
    });
});

describe('OllamaService — HTTP requests', () => {
    const origEnv = { ...process.env };
    let originalFetch: typeof fetch;

    beforeEach(() => {
        process.env.OLLAMA_BASE_URL = 'http://test-host:11434/v1';
        process.env.OLLAMA_MODEL = 'qwen3:32b';
        process.env.OLLAMA_NUM_CTX = '4096';
        originalFetch = global.fetch;
    });

    afterEach(() => {
        global.fetch = originalFetch;
        process.env = { ...origEnv };
    });

    it('sends an OpenAI-shaped body including num_ctx', async () => {
        const fetchMock = jest.fn(async () => ({
            ok: true,
            status: 200,
            json: async () => ({
                id: 'x',
                model: 'qwen3:32b',
                choices: [{ message: { content: 'hi' }, finish_reason: 'stop' }],
            }),
            text: async () => '',
        }));
        global.fetch = fetchMock as unknown as typeof fetch;

        const service = new OllamaService(makeLogger());
        const res = await service.sendChatRequest({
            messages: [{ role: 'user', content: 'hello' }],
            jsonMode: true,
        });

        expect(res.content).toBe('hi');
        expect(fetchMock).toHaveBeenCalledTimes(1);
        const call = fetchMock.mock.calls[0];
        if (!call) throw new Error('fetch was not called');
        expect(call[0]).toBe('http://test-host:11434/v1/chat/completions');
        const init = call[1] as { body: string };
        const body = JSON.parse(init.body);
        expect(body.model).toBe('qwen3:32b');
        expect(body.options.num_ctx).toBe(4096);
        expect(body.response_format).toEqual({ type: 'json_object' });
        expect(body.stream).toBe(false);
    });

    it('retries once on ECONNREFUSED then throws on repeat', async () => {
        const err = Object.assign(new Error('fetch failed'), {
            cause: Object.assign(new Error('connect ECONNREFUSED'), {
                code: 'ECONNREFUSED',
            }),
        });
        const fetchMock = jest.fn(async () => {
            throw err;
        });
        global.fetch = fetchMock as unknown as typeof fetch;

        const service = new OllamaService(makeLogger());
        await expect(
            service.sendChatRequest({ messages: [{ role: 'user', content: 'x' }] }),
        ).rejects.toThrow(/Ollama/);
        expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it('throws AppError on non-OK HTTP', async () => {
        global.fetch = (async () => ({
            ok: false,
            status: 500,
            text: async () => 'boom',
            json: async () => ({}),
        })) as unknown as typeof fetch;

        const service = new OllamaService(makeLogger());
        await expect(
            service.sendChatRequest({ messages: [{ role: 'user', content: 'x' }] }),
        ).rejects.toThrow(/500/);
    });
});

const e2e = process.env.OLLAMA_E2E === '1' ? describe : describe.skip;
e2e('OllamaService — live Ollama e2e', () => {
    it('reaches a real Ollama instance', async () => {
        const service = new OllamaService(makeLogger());
        const res = await service.sendChatRequest({
            messages: [{ role: 'user', content: 'Respond with the single word: ping' }],
            maxTokens: 8,
            temperature: 0,
        });
        expect(typeof res.content).toBe('string');
        expect(res.content.length).toBeGreaterThan(0);
    }, 30_000);
});
