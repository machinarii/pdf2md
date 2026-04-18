import { ERROR_CODES, ERROR_MESSAGES, LOG_COMPONENTS } from '@/constants';
import { AppError } from '@/utils/AppError';
import type { ConfigService } from '../ConfigService';
import type { LoggerService } from '../LoggerService';

/**
 * Header type configuration structure
 */
interface HeaderTypeConfig {
    level1: {
        formats: string[];
        examples: string[];
    };
}

/**
 * Book type configuration structure
 */
interface BookTypeConfig {
    description?: string;
    'header-type': HeaderTypeConfig;
    'text-removal-patterns': string[];
}

/**
 * Book types configuration file structure
 */
interface BookTypesConfig {
    [key: string]: BookTypeConfig;
}

/**
 * Service for managing book types and their configurations
 */
export class BookTypesService {
    private readonly logger: LoggerService;
    private readonly configService: ConfigService;
    private bookTypesCache: BookTypesConfig | null = null;

    constructor(logger: LoggerService, configService: ConfigService) {
        this.logger = logger;
        this.configService = configService;
    }

    /**
     * Load book types configuration from book-types.yaml
     */
    public async loadBookTypes(): Promise<BookTypesConfig> {
        if (this.bookTypesCache) {
            return this.bookTypesCache;
        }

        try {
            const rawBookTypes = await this.configService.loadBookTypesConfig();

            if (!rawBookTypes) {
                throw new AppError(
                    ERROR_CODES.CONFIG_INVALID,
                    LOG_COMPONENTS.CONFIG_SERVICE,
                    'loadBookTypes',
                    'Book types configuration file not found or empty',
                    {},
                );
            }

            const bookTypes = rawBookTypes as BookTypesConfig;

            // Validate the structure
            this.validateBookTypesConfig(bookTypes);

            this.bookTypesCache = bookTypes;

            return bookTypes;
        } catch (error) {
            if (error instanceof AppError) {
                throw error;
            }

            throw new AppError(
                ERROR_CODES.CONFIG_INVALID,
                LOG_COMPONENTS.CONFIG_SERVICE,
                'loadBookTypes',
                ERROR_MESSAGES[ERROR_CODES.CONFIG_INVALID].replace(
                    '{details}',
                    'Failed to load book types configuration',
                ),
                {},
                error instanceof Error ? error : new Error(String(error)),
            );
        }
    }

    /**
     * Get text-removal-patterns.
     *
     * - When `bookType` is a known type, returns that type's patterns.
     * - When `bookType` is empty or unknown, returns the **union** of every
     *   type's patterns (deduplicated) so a single pass strips boilerplate
     *   from any publisher. The `default` entry — which is typically empty
     *   and acts as a schema placeholder — is excluded.
     */
    public async getTextRemovalPatterns(bookType?: string): Promise<string[]> {
        const bookTypes = await this.loadBookTypes();

        if (bookType && bookTypes[bookType]) {
            return bookTypes[bookType]['text-removal-patterns'] || [];
        }

        const configLogger = this.logger.getConfigLogger(LOG_COMPONENTS.CONFIG_SERVICE);
        if (bookType) {
            configLogger.warn(
                { bookType, availableTypes: Object.keys(bookTypes) },
                'Unknown book type, applying union of all text-removal patterns',
            );
        } else {
            configLogger.info(
                { availableTypes: Object.keys(bookTypes) },
                'No book type specified, applying union of all text-removal patterns',
            );
        }

        const seen = new Set<string>();
        for (const [typeName, typeConfig] of Object.entries(bookTypes)) {
            if (typeName === 'default') continue;
            for (const pattern of typeConfig['text-removal-patterns'] || []) {
                seen.add(pattern);
            }
        }
        return Array.from(seen);
    }

    /**
     * Get header type configuration for a specific book type. Returns null
     * when no book type is specified (no publisher-specific heading rules to
     * apply — callers should fall back to generic heading detection).
     */
    public async getHeaderTypeConfig(
        bookType?: string,
    ): Promise<HeaderTypeConfig | null> {
        if (!bookType) return null;
        const bookTypes = await this.loadBookTypes();
        const typeConfig = bookTypes[bookType];
        if (!typeConfig) {
            const defaultConfig = bookTypes.default;
            return defaultConfig?.['header-type'] || null;
        }
        return typeConfig['header-type'] || null;
    }

    /**
     * Get available book types
     */
    public async getAvailableBookTypes(): Promise<string[]> {
        const bookTypes = await this.loadBookTypes();
        return Object.keys(bookTypes);
    }

    /**
     * Get book type configuration by name
     */
    public async getBookTypeConfig(bookType: string): Promise<BookTypeConfig | null> {
        const bookTypes = await this.loadBookTypes();
        return bookTypes[bookType] || null;
    }

    /**
     * Clear the cache (useful for testing or when config changes)
     */
    public clearCache(): void {
        this.bookTypesCache = null;
    }

    /**
     * Validate book types configuration structure
     */
    private validateBookTypesConfig(bookTypes: BookTypesConfig): void {
        const configLogger = this.logger.getConfigLogger(LOG_COMPONENTS.CONFIG_SERVICE);

        for (const [typeName, typeConfig] of Object.entries(bookTypes)) {
            // Check if required fields are present
            if (
                !typeConfig['text-removal-patterns'] ||
                !Array.isArray(typeConfig['text-removal-patterns'])
            ) {
                configLogger.warn(
                    { typeName },
                    'Book type missing or invalid text-removal-patterns array',
                );
            }

            if (
                !typeConfig['header-type'] ||
                typeof typeConfig['header-type'] !== 'object'
            ) {
                configLogger.warn(
                    { typeName },
                    'Book type missing or invalid header-type configuration',
                );
            }
        }
    }

    /**
     * Check if book types configuration file exists
     */
    public async exists(): Promise<boolean> {
        try {
            const bookTypes = await this.configService.loadBookTypesConfig();
            return bookTypes !== null;
        } catch {
            return false;
        }
    }
}

export type { BookTypeConfig, BookTypesConfig, HeaderTypeConfig };
