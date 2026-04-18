export {
    type BookTextMarkerType,
    checkForBookTextEndMarker,
    checkForBookTextMarker,
    checkForBookTextStartMarker,
} from './checkForBookTextMarkers';
export { detectFootnoteStartFromOcr } from './detectFootnotesFromOcr';
export {
    detectAndProcessHeaders,
    extractOrdinalValue,
    matchHeaderPattern,
} from './detectHeadersFromOcr';
export { GetTextAndStructureFromOcr } from './GetTextAndStructureFromOcr';
export type { OCROptions, OCRResult } from './OCRService';
export { OCRService } from './OCRService';
