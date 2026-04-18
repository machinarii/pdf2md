/**
 * Format handlers for extracting text from different file formats
 */

// Re-export types for convenience
export type {
    FileInfo,
    QualityIssue,
    TextExtractionResult,
    TextMetadata,
    TextQuality,
} from '@/types';
export { EPUBHandler } from './EPUBHandler';
export { PDFHandler } from './PDFHandler';
export { TextHandler } from './TextHandler';
