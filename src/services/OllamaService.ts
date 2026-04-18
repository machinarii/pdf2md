import {
    ENV_VARS,
    ERROR_CODES,
    LOG_COMPONENTS,
    OLLAMA_DEFAULTS,
    RETRY_CONFIG,
} from '@/constants';
import { AppError } from '@/utils/AppError';
import type { LoggerService } from './LoggerService';

export interface OllamaChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

export interface OllamaChatRequest {
    messages: OllamaChatMessage[];
    temperature?: number;
    maxTokens?: number;
    jsonMode?: boolean;
}

export interface OllamaChatResponse {
    id: string;
    model: string;
    content: string;
    usage?: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    };
    finish_reason?: string;
}

export interface OllamaConfig {
    baseUrl: string;
    model: string;
    numCtx: number;
    maxRetries: number;
    timeout: number;
}

export class OllamaService {
    private readonly logger: LoggerService;
    private readonly config: OllamaConfig;

    constructor(logger: LoggerService) {
        this.logger = logger;
        this.config = this.loadConfig();
    }

    private loadConfig(): OllamaConfig {
        const baseUrl =
            process.env[ENV_VARS.OLLAMA_BASE_URL] ?? OLLAMA_DEFAULTS.BASE_URL;
        const model = process.env[ENV_VARS.OLLAMA_MODEL] ?? OLLAMA_DEFAULTS.MODEL;
        const numCtxRaw = process.env[ENV_VARS.OLLAMA_NUM_CTX];
        const numCtx = numCtxRaw ? Number(numCtxRaw) : OLLAMA_DEFAULTS.NUM_CTX;

        if (!Number.isFinite(numCtx) || numCtx <= 0) {
            throw new AppError(
                ERROR_CODES.CONFIG_INVALID,
                LOG_COMPONENTS.CONFIG_SERVICE,
                'loadConfig',
                `OLLAMA_NUM_CTX must be a positive number, got "${numCtxRaw}"`,
                {},
            );
        }

        return {
            baseUrl: baseUrl.replace(/\/+$/, ''),
            model,
            numCtx,
            maxRetries: RETRY_CONFIG.MAX_RETRIES,
            timeout: 120_000,
        };
    }

    public getConfig(): Readonly<OllamaConfig> {
        return this.config;
    }

    public async sendChatRequest(
        request: OllamaChatRequest,
    ): Promise<OllamaChatResponse> {
        const logger = this.logger.getConfigLogger(LOG_COMPONENTS.CONFIG_SERVICE);
        const url = `${this.config.baseUrl}/chat/completions`;

        const body = {
            model: this.config.model,
            messages: request.messages,
            temperature: request.temperature ?? 0.2,
            max_tokens: request.maxTokens,
            response_format: request.jsonMode ? { type: 'json_object' } : undefined,
            options: { num_ctx: this.config.numCtx },
            stream: false,
        };

        logger.debug(
            { url, model: this.config.model, messageCount: request.messages.length },
            'Sending Ollama chat request',
        );

        const attempt = async (): Promise<Response> => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), this.config.timeout);
            try {
                return await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    signal: controller.signal,
                });
            } finally {
                clearTimeout(timer);
            }
        };

        let response: Response;
        try {
            response = await attempt();
        } catch (err) {
            const cause = err instanceof Error ? err : new Error(String(err));
            const isConnRefused =
                /ECONNREFUSED|fetch failed|ENOTFOUND/i.test(cause.message) ||
                ('cause' in cause &&
                    /ECONNREFUSED/.test(String((cause as { cause?: unknown }).cause)));
            if (!isConnRefused) {
                throw new AppError(
                    ERROR_CODES.API_ERROR,
                    LOG_COMPONENTS.CONFIG_SERVICE,
                    'sendChatRequest',
                    `Ollama request failed: ${cause.message}`,
                    { url },
                    cause,
                );
            }
            logger.warn(
                { url, error: cause.message },
                'Ollama connection refused, retrying once',
            );
            try {
                response = await attempt();
            } catch (err2) {
                const cause2 = err2 instanceof Error ? err2 : new Error(String(err2));
                throw new AppError(
                    ERROR_CODES.API_ERROR,
                    LOG_COMPONENTS.CONFIG_SERVICE,
                    'sendChatRequest',
                    `Ollama not reachable at ${url}: ${cause2.message}`,
                    { url },
                    cause2,
                );
            }
        }

        if (!response.ok) {
            const text = await response.text().catch(() => '');
            throw new AppError(
                ERROR_CODES.API_ERROR,
                LOG_COMPONENTS.CONFIG_SERVICE,
                'sendChatRequest',
                `Ollama returned HTTP ${response.status}: ${text.slice(0, 500)}`,
                { url, status: response.status },
            );
        }

        const data = (await response.json()) as {
            id?: string;
            model?: string;
            choices?: Array<{
                message?: { content?: string };
                finish_reason?: string;
            }>;
            usage?: OllamaChatResponse['usage'];
        };

        const content = data.choices?.[0]?.message?.content;
        if (typeof content !== 'string' || content.length === 0) {
            throw new AppError(
                ERROR_CODES.API_ERROR,
                LOG_COMPONENTS.CONFIG_SERVICE,
                'sendChatRequest',
                'Empty response from Ollama',
                { url },
            );
        }

        return {
            id: data.id ?? 'ollama-response',
            model: data.model ?? this.config.model,
            content,
            usage: data.usage,
            finish_reason: data.choices?.[0]?.finish_reason,
        };
    }

    public async sendCustomChatRequest(
        messages: OllamaChatMessage[],
        options: { temperature?: number; maxTokens?: number; jsonMode?: boolean } = {},
    ): Promise<string> {
        const res = await this.sendChatRequest({
            messages,
            temperature: options.temperature,
            maxTokens: options.maxTokens,
            jsonMode: options.jsonMode,
        });
        return res.content;
    }

    public async sendStructureInferenceRequest(
        prompt: string,
        options: { temperature?: number; maxTokens?: number } = {},
    ): Promise<string> {
        const messages: OllamaChatMessage[] = [
            {
                role: 'system',
                content:
                    'You are an expert at analyzing book structures and correcting Table of Contents and paragraph entries. Always respond with valid JSON and nothing else.',
            },
            { role: 'user', content: prompt },
        ];
        return this.sendCustomChatRequest(messages, {
            temperature: options.temperature ?? 0.1,
            maxTokens: options.maxTokens ?? 2000,
            jsonMode: true,
        });
    }

    public async testConnection(): Promise<boolean> {
        try {
            await this.sendChatRequest({
                messages: [{ role: 'user', content: 'ping' }],
                maxTokens: 4,
                temperature: 0,
            });
            return true;
        } catch (error) {
            this.logger.error(
                LOG_COMPONENTS.CONFIG_SERVICE,
                'Ollama connection test failed',
                { error: error instanceof Error ? error.message : String(error) },
            );
            return false;
        }
    }
}
