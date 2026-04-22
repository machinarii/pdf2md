import { ERROR_CODES, LOG_COMPONENTS } from '../constants';
import type { BookStructureService } from '../services/BookStructureService';
import type { ConfigService } from '../services/ConfigService';
import type { LoggerService } from '../services/LoggerService';
import { TextCleanerService } from '../services/TextCleanerService';
import type {
    FileFormatResult,
    FileInfo,
    PipelineState,
    ProgressCallback,
} from '../types';
import { AppError } from '../utils/AppError';
import { getArtifactsDir } from '../utils/ArtifactsDir';
import { FileUtils } from '../utils/FileUtils';
import { AbstractPhase } from './AbstractPhase';
import { FileFormatDetector } from './phase_1_Text_Extraction_And_Format_Processing/step_1_File_Format_Detection_And_Validation/FileFormatDetector';
import { TextExtractor } from './phase_1_Text_Extraction_And_Format_Processing/step_2_Text_Extraction/TextExtractor';

/**
 * Phase 1: extract text, then run deterministic cleanup.
 *
 *   1. File-format detection
 *   2. Text extraction (embedded + Tesseract OCR when needed)
 *   3. TextCleanerService — Unicode normalization, ligatures, page-number
 *      removal, hyphen rejoining, repeated header/footer dedup, paragraph
 *      rewrap, OCR-specific passes
 *
 * The cleaned text is written to `book-artifacts/<book>/phase1/step2-cleaned.*`
 * and picked up by `CleanBookCommand.finalizeOutput` to be written as
 * `<basename>.md` next to the source file.
 */
export class DataLoadingPhase extends AbstractPhase {
    private formatDetector: FileFormatDetector;
    private textExtractor: TextExtractor;
    private fileUtils: FileUtils;
    private textCleaner: TextCleanerService;

    constructor(
        logger: LoggerService,
        configService: ConfigService,
        bookStructureService: BookStructureService,
    ) {
        super(logger);
        this.formatDetector = new FileFormatDetector(logger);
        this.textExtractor = new TextExtractor(
            logger,
            configService,
            getArtifactsDir(),
            bookStructureService,
        );
        this.fileUtils = new FileUtils(logger);
        this.textCleaner = new TextCleanerService(logger);
    }

    public override getName(): string {
        return 'Data Loading & Format Detection';
    }

    public override getDescription(): string {
        return 'Detects file format, extracts text, and runs deterministic cleanup';
    }

    public override async execute(
        state: PipelineState,
        progressCallback?: ProgressCallback,
    ): Promise<unknown> {
        const pipelineLogger = this.logger.getPipelineLogger(
            LOG_COMPONENTS.PIPELINE_MANAGER,
        );

        try {
            pipelineLogger.info(
                { pipelineId: state.id, inputFile: state.inputFile },
                'Starting data loading phase',
            );

            progressCallback?.({
                phase: this.getName(),
                step: 'step-1-format-detection',
                current: 0,
                total: 100,
                percentage: 0,
                message: 'Step 1: Detecting file format...',
            });

            const fs = await import('node:fs/promises');
            const path = await import('node:path');
            const stats = await fs.stat(state.inputFile);

            const fileInfo: FileInfo = {
                path: state.inputFile,
                name: path.basename(state.inputFile),
                size: stats.size,
                format: path
                    .extname(state.inputFile)
                    .toLowerCase()
                    .slice(1) as FileInfo['format'],
                mimeType: 'application/octet-stream',
                lastModified: stats.mtime,
            };

            const formatResult = await this.formatDetector.detectFormat(fileInfo);

            progressCallback?.({
                phase: this.getName(),
                step: 'step-1-format-detection',
                current: 40,
                total: 100,
                percentage: 40,
                message: 'Step 1: File format detected',
            });

            pipelineLogger.info(
                { pipelineId: state.id, format: formatResult.format },
                'Starting Step 2: Text extraction',
            );

            progressCallback?.({
                phase: this.getName(),
                step: 'step-2-text-extraction',
                current: 50,
                total: 100,
                percentage: 50,
                message: 'Step 2: Extracting text...',
            });

            const metadata = this.fileUtils.parseFilename(state.inputFile);
            const fileType = this.determineFileType(formatResult);

            const textExtractionResult = await this.textExtractor.extractText(
                fileInfo,
                {
                    hasTextBoundaries: true,
                    boundaries: {},
                    fileType,
                    skipStartMarker: state.skipStartMarker,
                },
                metadata,
                state.bookType,
            );

            progressCallback?.({
                phase: this.getName(),
                step: 'step-2-text-extraction',
                current: 75,
                total: 100,
                percentage: 75,
                message: 'Step 2: Text extraction complete',
            });

            progressCallback?.({
                phase: this.getName(),
                step: 'step-3-text-cleanup',
                current: 80,
                total: 100,
                percentage: 80,
                message: 'Step 3: Deterministic text cleanup...',
            });

            const configKey = this.getConfigKey(metadata);
            const bookArtifactsDir = getArtifactsDir();
            const phase1Dir = `${bookArtifactsDir}/${configKey}/phase1`;
            const step2TxtPath = `${phase1Dir}/step2.txt`;
            const step2OcrPath = `${phase1Dir}/step2.ocr`;

            let txtContent = '';
            let ocrContent = '';

            try {
                txtContent = await fs.readFile(step2TxtPath, 'utf-8');
            } catch {
                pipelineLogger.debug(
                    { pipelineId: state.id, path: step2TxtPath },
                    'No step2.txt file found',
                );
            }
            try {
                ocrContent = await fs.readFile(step2OcrPath, 'utf-8');
            } catch {
                pipelineLogger.debug(
                    { pipelineId: state.id, path: step2OcrPath },
                    'No step2.ocr file found (normal for non-OCR texts)',
                );
            }

            if (txtContent) {
                const { cleanedText, stats: cleanStats } = this.textCleaner.clean(
                    txtContent,
                    { source: 'pdf' },
                );
                await fs.writeFile(
                    `${phase1Dir}/step2-cleaned.txt`,
                    cleanedText,
                    'utf-8',
                );
                pipelineLogger.info(
                    { pipelineId: state.id, stats: cleanStats },
                    'Deterministic cleanup of extracted text complete',
                );
            }
            if (ocrContent) {
                const { cleanedText, stats: cleanStats } = this.textCleaner.clean(
                    ocrContent,
                    { source: 'ocr' },
                );
                await fs.writeFile(
                    `${phase1Dir}/step2-cleaned.ocr`,
                    cleanedText,
                    'utf-8',
                );
                pipelineLogger.info(
                    { pipelineId: state.id, stats: cleanStats },
                    'Deterministic cleanup of OCR text complete',
                );
            }

            progressCallback?.({
                phase: this.getName(),
                step: 'step-3-text-cleanup',
                current: 100,
                total: 100,
                percentage: 100,
                message: 'Step 3: Cleanup complete',
            });

            pipelineLogger.info(
                {
                    pipelineId: state.id,
                    format: formatResult.format,
                    confidence: formatResult.confidence,
                    extractedTextLength: textExtractionResult.extractedText.length,
                    ocrTextLength: textExtractionResult.ocrText?.length || 0,
                },
                'Data loading phase completed successfully',
            );

            return {
                phase: 'data_loading',
                success: true,
                data: { formatResult, textExtractionResult, metadata },
                timestamp: new Date(),
            };
        } catch (error) {
            pipelineLogger.error(
                {
                    pipelineId: state.id,
                    error: error instanceof Error ? error.message : String(error),
                },
                'Data loading phase failed',
            );

            throw new AppError(
                ERROR_CODES.PIPELINE_FAILED,
                LOG_COMPONENTS.PIPELINE_MANAGER,
                'DataLoadingPhase.execute',
                'Failed to load and process file',
                { inputFile: state.inputFile },
                error instanceof Error ? error : new Error(String(error)),
            );
        }
    }

    private determineFileType(formatResult: FileFormatResult): string {
        if (formatResult.format === 'pdf') {
            switch (formatResult.metadata?.contentType) {
                case 'text_based':
                    return 'pdf-text';
                case 'image_based':
                    return 'pdf-ocr';
                default:
                    return 'pdf-text-ocr';
            }
        }
        if (formatResult.format === 'epub') return 'epub';
        return 'text';
    }

    private getConfigKey(metadata: {
        author: string;
        title: string;
        bookIndex?: string;
    }): string {
        const { author, title, bookIndex } = metadata;
        return `${author}#${title}${bookIndex ? `#${bookIndex}` : ''}`;
    }
}
