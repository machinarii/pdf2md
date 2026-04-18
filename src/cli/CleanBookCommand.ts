import path from 'node:path';
import { Command } from 'commander';
import {
    APP_DESCRIPTION,
    APP_VERSION,
    CLI_ALIASES,
    CLI_OPTIONS,
    DEFAULT_LOG_LEVEL,
    DEFAULT_OUTPUT_DIR,
    ERROR_CODES,
    LOG_COMPONENTS,
    LOG_LEVELS,
    PIPELINE_PHASES,
    VALID_BOOK_TYPES,
} from '@/constants';
import { AIEnhancementsPhase } from '@/pipeline/AIEnhancementsPhase';
import { DataLoadingPhase } from '@/pipeline/DataLoadingPhase';
import { EvaluationPhase } from '@/pipeline/EvaluationPhase';
import { PipelineManager } from '@/pipeline/PipelineManager';
import { TextNormalizationPhase } from '@/pipeline/TextNormalizationPhase';
import { BookStructureService } from '@/services/BookStructureService';
import { ConfigService } from '@/services/ConfigService';
import {
    createDefaultLoggerService,
    type LoggerService,
} from '@/services/LoggerService';
import type {
    BookManifestInfo,
    CLIOptions,
    FilenameMetadata,
    LogLevel,
    PipelineState,
    ProgressInfo,
} from '@/types';
import { AppError, isAppError } from '@/utils/AppError';
import { cyan, getChalkInstance, gray, info, success, warn } from '@/utils/ChalkUtils';
import { FileUtils } from '@/utils/FileUtils';

// import ora, { type Ora } from "ora"; // Removed to fix interactive prompt issues

// Commander.js option types (following .cursorrules #5 - no any keyword)
interface CommanderOptions {
    outputDir: string;
    bookType: string;
    verbose: boolean;
    debug: boolean;
    logLevel: string;
    skipStartMarker: boolean;
    inferText?: string;
}

/**
 * Main CLI command for cleaning books
 */
export class CleanBookCommand {
    private logger: LoggerService;
    private configService: ConfigService;
    private bookStructureService: BookStructureService;
    private fileUtils: FileUtils;
    private pipelineManager: PipelineManager;
    // private spinner: Ora | null = null; // Removed to fix interactive prompt issues

    constructor() {
        this.logger = createDefaultLoggerService();
        this.configService = new ConfigService(this.logger);
        this.bookStructureService = new BookStructureService(this.logger);
        this.fileUtils = new FileUtils(this.logger);
        this.pipelineManager = new PipelineManager(this.logger);

        // Register pipeline phases
        this.registerPipelinePhases();
    }

    /**
     * Register all pipeline phases
     */
    private registerPipelinePhases(): void {
        const dataLoadingPhase = new DataLoadingPhase(
            this.logger,
            this.configService,
            this.bookStructureService,
        );
        const textNormalizationPhase = new TextNormalizationPhase(this.logger);
        const evaluationPhase = new EvaluationPhase(this.logger);
        const aiEnhancementsPhase = new AIEnhancementsPhase(this.logger);

        this.pipelineManager.registerPhase(
            PIPELINE_PHASES.DATA_LOADING,
            dataLoadingPhase,
        );
        this.pipelineManager.registerPhase(
            PIPELINE_PHASES.TEXT_NORMALIZATION,
            textNormalizationPhase,
        );
        this.pipelineManager.registerPhase(PIPELINE_PHASES.EVALUATION, evaluationPhase);
        this.pipelineManager.registerPhase(
            PIPELINE_PHASES.AI_ENHANCEMENTS,
            aiEnhancementsPhase,
        );
    }

    /**
     * Create and configure the CLI command
     */
    public createCommand(): Command {
        return new Command()
            .name('clean-book')
            .description(APP_DESCRIPTION)
            .version(APP_VERSION)
            .argument('<input-file>', 'Input file path (PDF, EPUB, or TXT)')
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.OUTPUT_DIR]}, --${CLI_OPTIONS.OUTPUT_DIR} <dir>`,
                'Output directory for processed files',
                DEFAULT_OUTPUT_DIR,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.BOOK_TYPE]}, --${CLI_OPTIONS.BOOK_TYPE} <type>`,
                `Book type (optional): ${VALID_BOOK_TYPES.join(', ')}. When omitted, all publisher text-removal patterns are applied (union of every type).`,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.VERBOSE]}, --${CLI_OPTIONS.VERBOSE}`,
                'Enable verbose logging',
                false,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.DEBUG]}, --${CLI_OPTIONS.DEBUG}`,
                'Enable debug logging',
                false,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.LOG_LEVEL]}, --${CLI_OPTIONS.LOG_LEVEL} <level>`,
                'Set log level (debug, info, warn, error, fatal)',
                DEFAULT_LOG_LEVEL,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.SKIP_START_MARKER]}, --${CLI_OPTIONS.SKIP_START_MARKER}`,
                'Skip the start marker (e.g., "START OF THIS BOOK")',
                false,
            )
            .option(
                `-${CLI_ALIASES[CLI_OPTIONS.INFER_TEXT]}, --${CLI_OPTIONS.INFER_TEXT} <filename>`,
                'Path to text file for structure inference',
            )
            .addHelpText(
                'after',
                `
Filename convention:
  Input files should follow <author>#<title>[#<book-index>].<ext>
  Examples:
    Rudolf_Steiner#Goethes_Naturwissenschaftliche_Schriften#GA_1.pdf
    Jane_Doe#Sample_Book.epub

Pipeline:
  1. File-format detection and validation
  2. Text extraction (embedded text + Tesseract OCR for image PDFs)
  3. Deterministic cleanup via TextCleanerService
     (Unicode normalization, ligatures, page numbers, hyphen rejoining,
      repeated header/footer removal, paragraph rewrap)
  4. Book-structure inference via a local Ollama model
  5. Structure normalization / footnote handling / OCR QC

Environment variables:
  OLLAMA_BASE_URL   Ollama endpoint (default http://localhost:11434/v1)
  OLLAMA_MODEL      Model tag       (default qwen3:32b)
  OLLAMA_NUM_CTX    Context tokens  (default 32768)
  LOG_LEVEL         debug | info | warn | error | fatal
  OUTPUT_DIR        Default output directory
  CONFIG_DIR        Configuration directory

Prerequisites:
  - Node version matching .nvmrc
  - Ollama running locally (https://ollama.com)
  - Model pulled, e.g. \`ollama pull qwen3:32b\`

Examples:
  clean-book some-report.pdf                         # no -b → apply all patterns
  clean-book -b google-play-ebook Jane_Doe#Book.epub # google-play preset
  clean-book -v -l debug Author#Title.pdf
  OLLAMA_MODEL=llama3.1:8b clean-book book.pdf

More:
  README.md                         pipeline + dev setup
  src/services/TextCleanerService.md  deterministic cleanup passes
  src/services/OllamaService.md       LLM client + retry behavior
`,
            )
            .action(async (inputFile: string, options: CommanderOptions) => {
                await this.execute(inputFile, options);
            });
    }

    /**
     * Execute the clean book command
     */
    private async execute(inputFile: string, options: CommanderOptions): Promise<void> {
        const cliLogger = this.logger.getCLILogger(LOG_COMPONENTS.CLI_COMMAND);

        try {
            // Parse and validate options
            const cliOptions = await this.parseOptions(inputFile, options);

            // Update logger configuration
            this.updateLoggerConfig(cliOptions);

            // Validate input file
            await this.validateInputFile(cliOptions.inputFile);

            // Parse filename metadata
            const metadata = this.parseFilenameMetadata(cliOptions);

            // Load or create book manifest
            let bookManifest: BookManifestInfo;
            try {
                console.log('🔍 Attempting to load existing manifest...');
                bookManifest =
                    await this.bookStructureService.loadBookManifest(metadata);
                console.log('✅ Existing manifest loaded successfully');

                // Check if text boundaries are missing and prompt for them
                if (
                    !bookManifest.textBeforeFirstChapter ||
                    !bookManifest.textAfterLastChapter
                ) {
                    console.log('📝 Text boundaries missing, prompting for them...');
                    const { textBeforeFirstChapter, textAfterLastChapter } =
                        await this.promptForTextBoundaries();
                    console.log('✅ Text boundaries received:', {
                        textBeforeFirstChapter,
                        textAfterLastChapter,
                    });

                    // Update the manifest with the boundaries
                    console.log('💾 Updating manifest with boundaries...');
                    await this.bookStructureService.updateBookManifest(metadata, {
                        textBeforeFirstChapter,
                        textAfterLastChapter,
                    });
                    console.log('✅ Manifest updated');

                    // Reload the manifest to get the updated version
                    console.log('🔄 Reloading manifest...');
                    bookManifest =
                        await this.bookStructureService.loadBookManifest(metadata);
                    console.log('✅ Manifest reloaded');
                }
            } catch (error) {
                console.log(
                    '❌ Error loading manifest:',
                    error instanceof Error ? error.message : String(error),
                );

                // If manifest doesn't exist, create one and prompt for boundaries
                if (error instanceof AppError && error.code === 'CONFIG_INVALID') {
                    console.log('📝 Creating new manifest...');
                    cliLogger.info('Book manifest not found, creating new one...');

                    // Create new book structure
                    console.log('🏗️ Creating book structure...');
                    bookManifest = await this.bookStructureService.createBookStructure(
                        metadata,
                        cliOptions.inputFile,
                    );
                    console.log('✅ Book structure created');

                    // Prompt for text boundaries
                    console.log('📝 Prompting for text boundaries...');
                    const { textBeforeFirstChapter, textAfterLastChapter } =
                        await this.promptForTextBoundaries();
                    console.log('✅ Text boundaries received:', {
                        textBeforeFirstChapter,
                        textAfterLastChapter,
                    });

                    // Update the manifest with the boundaries
                    console.log('💾 Updating manifest with boundaries...');
                    await this.bookStructureService.updateBookManifest(metadata, {
                        textBeforeFirstChapter,
                        textAfterLastChapter,
                    });
                    console.log('✅ Manifest updated');

                    // Reload the manifest to get the updated version
                    console.log('🔄 Reloading manifest...');
                    bookManifest =
                        await this.bookStructureService.loadBookManifest(metadata);
                    console.log('✅ Manifest reloaded');

                    cliLogger.info(
                        'Book manifest created successfully with text boundaries',
                    );
                } else {
                    console.log('❌ Unexpected error, rethrowing...');
                    throw error;
                }
            }

            // Load configuration
            const bookConfig = await this.configService.loadBookConfig(
                metadata,
                cliOptions.inputFile,
            );

            // Create pipeline configuration
            const pipelineConfig = this.configService.createPipelineConfig(
                bookConfig,
                cliOptions,
            );

            // Setup progress reporting
            this.setupProgressReporting(cliOptions);

            // Execute pipeline
            cliLogger.info(
                {
                    inputFile: cliOptions.inputFile,
                    outputDir: cliOptions.outputDir,
                    author: metadata.author,
                    title: metadata.title,
                },
                'Starting book cleaning process',
            );

            const result = await this.pipelineManager.execute(pipelineConfig, metadata);

            // Report success
            await success('✓ Book cleaning completed successfully!');
            await info(`Output directory: ${pipelineConfig.outputDir}`);
            await info(
                `Processing time: ${this.formatDuration(result.startTime, result.endTime)}`,
            );

            if (cliOptions.verbose) {
                await this.printProcessingStatistics(result);
            }
        } catch (error) {
            await this.handleError(error);
            process.exit(1);
        } finally {
            // Cleanup
            await this.cleanup();
        }
    }

    /**
     * Parse and validate CLI options
     */
    private async parseOptions(
        inputFile: string,
        options: CommanderOptions,
    ): Promise<CLIOptions> {
        // Book type is optional. When provided, validate; when absent, pass an
        // empty string so downstream code runs the union of every type's
        // text-removal patterns.
        if (options.bookType && !VALID_BOOK_TYPES.includes(options.bookType)) {
            console.error(`\n❌ Error: Invalid book type "${options.bookType}"\n`);
            console.error('Available book types:');
            for (const type of VALID_BOOK_TYPES) {
                console.error(`  - ${type}`);
            }
            console.error('\nOmit -b entirely to apply all text-removal patterns.\n');
            process.exit(1);
        }

        // Note: infer-text file validation will be done during processing
        // to allow the step to be omitted if the file doesn't exist

        const cliOptions: CLIOptions = {
            inputFile: path.resolve(inputFile),
            outputDir: options.outputDir
                ? path.resolve(options.outputDir)
                : path.resolve(DEFAULT_OUTPUT_DIR),
            bookType: options.bookType ?? '',
            verbose: options.verbose || options.debug,
            debug: options.debug,
            logLevel: options.logLevel as LogLevel,
            skipStartMarker: options.skipStartMarker,
            inferText: options.inferText,
        };

        return cliOptions;
    }

    /**
     * Update logger configuration based on CLI options
     */
    private updateLoggerConfig(options: CLIOptions): void {
        let logLevel = DEFAULT_LOG_LEVEL;

        if (options.debug) {
            logLevel = LOG_LEVELS.DEBUG;
        } else if (options.verbose) {
            logLevel = LOG_LEVELS.INFO;
        } else if (
            options.logLevel &&
            Object.values(LOG_LEVELS).includes(options.logLevel as LogLevel)
        ) {
            logLevel = options.logLevel as LogLevel;
        }

        this.logger.updateConfig({
            level: logLevel as LogLevel,
            pretty: true,
            timestamp: true,
            tags: {
                pipeline: logLevel as LogLevel,
                file_processing: logLevel as LogLevel,
                text_extraction: logLevel as LogLevel,
                ocr: logLevel as LogLevel,
                config: logLevel as LogLevel,
                cli: logLevel as LogLevel,
                error: LOG_LEVELS.ERROR,
            },
        });
    }

    /**
     * Validate input file
     */
    private async validateInputFile(inputFile: string): Promise<void> {
        const exists = await this.fileUtils.fileExists(inputFile);
        if (!exists) {
            throw new AppError(
                ERROR_CODES.FILE_NOT_FOUND,
                LOG_COMPONENTS.CLI_COMMAND,
                'validateInputFile',
                `Input file not found: ${inputFile}`,
                { inputFile },
            );
        }

        const isValidFormat = this.fileUtils.validateFileFormat(inputFile);
        if (!isValidFormat) {
            throw new AppError(
                ERROR_CODES.INVALID_FORMAT,
                LOG_COMPONENTS.CLI_COMMAND,
                'validateInputFile',
                `Unsupported file format: ${path.extname(inputFile)}`,
                { inputFile, extension: path.extname(inputFile) },
            );
        }
    }

    /**
     * Parse filename metadata
     */
    private parseFilenameMetadata(options: CLIOptions): FilenameMetadata {
        return this.fileUtils.parseFilename(options.inputFile);
    }

    /**
     * Prompt for text boundaries
     */
    private async promptForTextBoundaries(): Promise<{
        textBeforeFirstChapter: string;
        textAfterLastChapter: string;
    }> {
        const chalk = await getChalkInstance();

        console.log(chalk.yellow('\n📖 Text Boundary Configuration Required'));
        console.log(
            chalk.cyan(
                'The book cleaner needs to know where the actual book content starts and ends.',
            ),
        );
        console.log(
            chalk.cyan(
                'This helps remove publisher content, prefaces, appendices, etc.\n',
            ),
        );

        console.log(chalk.green('🔍 How to find these boundaries:'));
        console.log(
            chalk.white(
                '1. Open your PDF and look for the first chapter or main content',
            ),
        );
        console.log(
            chalk.white('2. Find the text that appears right BEFORE the first chapter'),
        );
        console.log(
            chalk.white('3. Find the text that appears right AFTER the last chapter'),
        );
        console.log(chalk.white('4. Copy these exact phrases (case-sensitive)\n'));

        console.log(chalk.yellow('💡 Examples:'));
        console.log(
            chalk.white('• "START OF THIS BOOK" or "BEGINNING OF AUTHOR CONTENT"'),
        );
        console.log(chalk.white('• "CHAPTER 1" or "I. INTRODUCTION"'));
        console.log(
            chalk.white('• "END OF THIS BOOK" or "APPENDIX" or "BIBLIOGRAPHY"'),
        );
        console.log(chalk.white('• "PUBLISHER NOTES" or "ABOUT THE AUTHOR"\n'));

        const textBeforeFirstChapter = await this.promptForText(
            chalk.green('Enter the text that appears BEFORE the first chapter:'),
            chalk.gray('(e.g., "START OF THIS BOOK" or "CHAPTER 1")'),
        );

        const textAfterLastChapter = await this.promptForText(
            chalk.green('Enter the text that appears AFTER the last chapter:'),
            chalk.gray('(e.g., "END OF THIS BOOK" or "APPENDIX")'),
        );

        console.log(chalk.green('\n✅ Text boundaries configured successfully!'));
        console.log(chalk.white(`• Before: "${textBeforeFirstChapter}"`));
        console.log(chalk.white(`• After: "${textAfterLastChapter}"`));
        console.log(
            chalk.cyan(
                'The book cleaner will now extract content between these boundaries.\n',
            ),
        );

        return { textBeforeFirstChapter, textAfterLastChapter };
    }

    /**
     * Helper to prompt for text input
     */
    private async promptForText(message: string, hint?: string): Promise<string> {
        const readline = require('node:readline');
        const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout,
        });

        const question = (query: string) => {
            return new Promise<string>((resolve) => {
                rl.question(query, (ans: string) => {
                    resolve(ans);
                });
            });
        };

        const fullMessage = hint ? `${message}\n${hint}\n> ` : `${message}\n> `;
        const answer = await question(fullMessage);
        rl.close();
        return answer.trim();
    }

    /**
     * Setup progress reporting
     */
    private setupProgressReporting(options: CLIOptions): void {
        if (options.verbose || options.debug) {
            // Use detailed logging for verbose mode
            this.pipelineManager.setProgressCallback((progress: ProgressInfo) => {
                const cliLogger = this.logger.getCLILogger(LOG_COMPONENTS.CLI_COMMAND);
                cliLogger.info(
                    {
                        phase: progress.phase,
                        step: progress.step,
                        percentage: progress.percentage,
                    },
                    `${progress.phase}: ${progress.message} (${progress.percentage}%)`,
                );
            });
        } else {
            // Use simple console output instead of spinner
            console.log('Initializing...');

            this.pipelineManager.setProgressCallback((progress: ProgressInfo) => {
                console.log(
                    `${progress.phase}: ${progress.message} (${progress.percentage}%)`,
                );
            });
        }
    }

    /**
     * Handle errors
     */
    private async handleError(error: unknown): Promise<void> {
        console.log('✖ Processing failed');

        const cliLogger = this.logger.getCLILogger(LOG_COMPONENTS.CLI_COMMAND);

        if (isAppError(error)) {
            const chalk = await getChalkInstance();
            console.error(chalk.red('✗ Error:'), error.message);

            if (error.context) {
                await gray(`Context: ${JSON.stringify(error.context, null, 2)}`);
            }

            cliLogger.error(
                {
                    error: error.getDetails(),
                },
                'Application error occurred',
            );

            if (error.cause) {
                await gray(`Caused by: ${error.cause.message}`);
            }
        } else {
            const errorMessage = error instanceof Error ? error.message : String(error);
            const chalk = await getChalkInstance();
            console.error(chalk.red('✗ Error:'), errorMessage);

            cliLogger.error(
                {
                    error: errorMessage,
                },
                'Unexpected error occurred',
            );
        }

        await warn('\nTip: Run with --verbose for more details');
        process.exit(1);
    }

    /**
     * Format duration
     */
    private formatDuration(startTime: Date, endTime?: Date): string {
        if (!endTime) {
            return 'N/A';
        }

        const duration = endTime.getTime() - startTime.getTime();
        const seconds = Math.floor(duration / 1000);
        const minutes = Math.floor(seconds / 60);

        if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        }
        return `${seconds}s`;
    }

    /**
     * Print processing statistics
     */
    private async printProcessingStatistics(result: PipelineState): Promise<void> {
        await cyan('\n📊 Processing Statistics:');
        await info(`Phases completed: ${result.results.length}`);
        await info(
            `Total processing time: ${this.formatDuration(result.startTime, result.endTime)}`,
        );

        for (const phaseResult of result.results) {
            const duration = phaseResult.duration ? `${phaseResult.duration}ms` : 'N/A';
            const status = phaseResult.status === 'completed' ? '✓' : '✗';
            await info(`  ${status} ${phaseResult.name}: ${duration}`);
        }
    }

    /**
     * Cleanup resources
     */
    private async cleanup(): Promise<void> {
        try {
            // Cleanup pipeline and logger
            await this.pipelineManager.cleanup();
            this.logger.flush();
        } catch (_error) {
            // Ignore cleanup errors
        }
    }
}
