/**
 * Deterministic text cleaner. TypeScript port of txt-cleaner.py.
 *
 * Pass order is load-bearing:
 *   0.  Unicode normalization (ligatures, smart quotes, control chars, exotic whitespace)
 *   0b. ResearchGate / SlideShare / Academia.edu multi-line block stripping
 *   1.  Line-level removal (page numbers, TOC leaders, footnote markers, bullets,
 *        boilerplate, standalone URLs, OCR junk, spaced letters, repeated headers/footers)
 *   1b. Spaced-letter rejoining (ocr mode only)
 *   2.  Hyphenated line-break rejoining
 *   3.  Paragraph rewrapping
 *   4.  Blank-line collapsing
 *
 * Swapping 1b and 2 breaks spaced-letter content. Running pass 1 before pass 0
 * breaks pattern matching against smart-quote / ligature content.
 */

import { LOG_COMPONENTS } from '@/constants';
import type { LoggerService } from './LoggerService';

export type TextCleanerSource = 'pdf' | 'ocr';

export interface TextCleanerOptions {
    aggressive?: boolean;
    removeBoilerplate?: boolean;
    removeUrls?: boolean;
    removeToc?: boolean;
    extraPatterns?: string[];
    source?: TextCleanerSource;
}

export interface TextCleanerStats {
    source: TextCleanerSource;
    originalLines: number;
    finalLines: number;
    rgSectionsStripped: number;
    repeatedLinesDetected: number;
    repeatThreshold: number;
    fuzzyRepeatedLines: number;
    removed: {
        pageNumbers: number;
        tocLeaders: number;
        footnoteMarkers: number;
        orphanBullets: number;
        boilerplate: number;
        urls: number;
        ocrJunk: number;
        spacedLetters: number;
        repeated: number;
        fuzzyRepeated: number;
        custom: number;
    };
}

export interface TextCleanerResult {
    cleanedText: string;
    stats: TextCleanerStats;
}

// ---------------------------------------------------------------------------
// Pass 0: Unicode / character-level normalization
// ---------------------------------------------------------------------------

const LIGATURES: Record<string, string> = {
    '\uFB00': 'ff',
    '\uFB01': 'fi',
    '\uFB02': 'fl',
    '\uFB03': 'ffi',
    '\uFB04': 'ffl',
    '\uFB05': 'st',
    '\uFB06': 'st',
};

const SMART_CHARS: Record<string, string> = {
    '\u2018': "'",
    '\u2019': "'",
    '\u201A': "'",
    '\u201C': '"',
    '\u201D': '"',
    '\u201E': '"',
    '\u2013': '-',
    '\u2014': '--',
    '\u2015': '--',
    '\u2026': '...',
    '\u00A0': ' ',
    '\u200B': '',
    '\u200C': '',
    '\u200D': '',
    '\uFEFF': '',
};

const UNICODE_WHITESPACE = /[\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]/g;
// biome-ignore lint/suspicious/noControlCharactersInRegex: stripping control chars is the whole point
const CONTROL_CHARS = /[\x00-\x08\x0b\x0e-\x1f\x7f]/g;

function normalizeUnicode(text: string): string {
    let out = text.replace(/\f/g, '\n');
    out = out.replace(CONTROL_CHARS, '');
    for (const [lig, replacement] of Object.entries(LIGATURES)) {
        out = out.split(lig).join(replacement);
    }
    for (const [ch, replacement] of Object.entries(SMART_CHARS)) {
        out = out.split(ch).join(replacement);
    }
    out = out.replace(UNICODE_WHITESPACE, ' ');
    return out;
}

// ---------------------------------------------------------------------------
// Page-number patterns
// ---------------------------------------------------------------------------

const PAGE_NUMBER_PATTERNS = [
    /^\s*[-\u2013\u2014]\s+\d{1,4}\s+[-\u2013\u2014]\s*$/,
    /^\s*page\s+\d{1,4}\s+of\s+\d{1,4}\s*$/i,
    /^\s*\|\s*\d{1,4}\s*\|\s*$/,
    /^\s*\|\s*[ivxlcdm]+\s*\|\s*$/i,
];
const BARE_NUMBER = /^\s*\d{1,4}\s*$/;
const BARE_PAGE_KEYWORD = /^\s*page\s+\d{1,4}\s*$/i;
const BARE_P_DOT = /^\s*p\.?\s*\d{1,4}\s*$/i;
const STANDALONE_SEPARATOR = /^\s*[|\u2502\u2503]\s*$/;

function isPageNumber(line: string, prevLine: string, nextLine: string): boolean {
    for (const p of PAGE_NUMBER_PATTERNS) {
        if (p.test(line)) return true;
    }
    const isolated = prevLine.trim() === '' && nextLine.trim() === '';
    if (!isolated) return false;
    return (
        BARE_NUMBER.test(line) || BARE_PAGE_KEYWORD.test(line) || BARE_P_DOT.test(line)
    );
}

// ---------------------------------------------------------------------------
// TOC leader / footnote marker / bullet patterns
// ---------------------------------------------------------------------------

const TOC_LEADER_PATTERNS = [
    /^.{2,60}\s*[.\u00B7\u2026]{3,}\s*\d{1,4}\s*$/,
    /^.{2,60}\s*_{3,}\s*\d{1,4}\s*$/,
    /^.{2,60}\s*-{3,}\s*\d{1,4}\s*$/,
];
const FOOTNOTE_PATTERNS = [
    /^\s*\[\d{1,3}\]\s*$/,
    /^\s*\d{1,3}\.\s*$/,
    /^\s*[*\u2020\u2021\u00A7\u00B6]\s*$/,
];
const ORPHAN_BULLET_PATTERNS = [
    /^\s*[\u2022\u25AA\u25B8\u25B9\u25BB\u25BA\u25B6\u2023\u27A4\u279C\u25C6\u25C7\u25CB\u25CF\u25C9\u25A0\u25A1\u25B7]\s*$/,
    /^\s*[-\u2013\u2014]\s*$/,
];
const URL_LINE = /^\s*(https?:\/\/\S+|www\.\S+|\S+@\S+\.\S+)\s*$/i;

// ---------------------------------------------------------------------------
// OCR junk / spaced-letter detection
// ---------------------------------------------------------------------------

function isOcrJunk(
    line: string,
    ocrMode: boolean,
    threshold = 0.35,
    minLength = 4,
): boolean {
    const stripped = line.trim();
    if (stripped.length <= minLength) return false;
    const effectiveThreshold = ocrMode ? 0.25 : threshold;
    const minWordRuns = ocrMode ? 3 : 2;
    const wordRuns = stripped.match(/[A-Za-z]{3,}/g);
    if (wordRuns && wordRuns.length >= minWordRuns) return false;
    if (/\d/.test(stripped)) return false;
    let alphaOrSpace = 0;
    for (const c of stripped) {
        if (c === ' ' || /[A-Za-z\u00C0-\u024F]/.test(c)) alphaOrSpace++;
    }
    return alphaOrSpace / stripped.length < effectiveThreshold;
}

const SPACED_LETTERS = /^(?:[a-zA-Z]\s+){3,}[a-zA-Z]?\s*$/;
function isSpacedLetters(line: string): boolean {
    const stripped = line.trim();
    if (stripped.length < 7) return false;
    return SPACED_LETTERS.test(stripped);
}

// ---------------------------------------------------------------------------
// Boilerplate patterns
// ---------------------------------------------------------------------------

const BOILERPLATE_PATTERNS = [
    /^\s*confidential\s*$/i,
    /^\s*draft\s*$/i,
    /^\s*do not distribute\s*$/i,
    /^\s*do not copy\s*$/i,
    /^\s*not for distribution\s*$/i,
    /^\s*internal use only\s*$/i,
    /^\s*for internal use\s*$/i,
    /^\s*proprietary\s*(and|&)\s*confidential\s*$/i,
    /^\s*all rights reserved\.?\s*$/i,
    /^\s*\u00A9.*\d{4}.*$/,
    /^\s*copyright\s+.*\d{4}.*$/i,
    /^\s*printed in\s+.+$/i,
    /^\s*ISBN[\s:=-]*[\d-]+\s*$/i,
    /^\s*alle rechte vorbehalten\.?\s*$/i,
];
const COPYRIGHT_PATTERN = /(?:^|\s)\u00A9\s*\d{4}\b/;

const ACADEMIC_BOILERPLATE_PATTERNS = [
    /^\s*Available\s+online\s+\d/i,
    /^\s*Received\s+.*Accept/i,
    /^\s*Contents\s+lists?\s+available\s+at\s+/i,
    /^\s*journal\s+homepage\s*:/i,
    /^\s*ScienceDirect\s*$/i,
    /^\s*JSTOR\s*$/i,
    /^\s*Springer\s*$/i,
    /^\d{4}\s+Elsevier/i,
    /^\s*Elsevier\s+(Ltd|B\.V\.|Inc|BV)\s*$/i,
    /^\s*doi\s*:/i,
    /^\s*https?:\/\/doi\.org\/\S+\s*$/i,
    /^\s*https?:\/\/dx\.doi\.org\/\S+\s*$/i,
];

const RESEARCHGATE_BOILERPLATE_PATTERNS = [
    /See discussions, stats, and author profiles/i,
    /^\s*\d+\s+(PUBLICATIONS|READS|CITATIONS)\b/i,
    /^\s*(PUBLICATIONS|READS|CITATIONS)\s*$/i,
    /^\s*SEE PROFILE\s*$/i,
    /^\s*\w[\w\s]*View\s+project\s*[\w\s]*$/i,
    /\bView\s+publication\s+stats?\b/i,
    /All content following this page was uploaded/i,
    /The user has requested enhancement/i,
    /uploaded by\s+.*\s+on\s+.*20[0-9]\d/i,
    /^\s*\d+\s+authors?\s*:/i,
    /^\s*[\w\u00C0-\u024F]+(?:\s+[\w\u00C0-\u024F]+){0,4}\s+University\s*$/i,
    /Some of the authors of this publication are also working on these related projects/i,
    /^\s*SlideShare\s*$/i,
    /www\.slideshare\.net/i,
    /Academia\.edu/i,
    /^\s*[A-Za-z]+\s*\u00B7\s*\d{4}\s*$/i,
    /^\s*[A-Za-z]+\s+\u00B7\s+[A-Za-z]+\s+\d{4}\s*$/i,
    /^\s*\d+\s+PUBLICATIONS\s+\d/i,
    /^\s*https?:\/\/www\.researchgate\.net\/\S+\s*$/i,
];

function isToCLeader(line: string): boolean {
    return TOC_LEADER_PATTERNS.some((p) => p.test(line));
}
function isFootnoteMarker(line: string): boolean {
    return FOOTNOTE_PATTERNS.some((p) => p.test(line));
}
function isOrphanBullet(line: string): boolean {
    return ORPHAN_BULLET_PATTERNS.some((p) => p.test(line));
}
function isBoilerplate(line: string): boolean {
    if (BOILERPLATE_PATTERNS.some((p) => p.test(line))) return true;
    if (COPYRIGHT_PATTERN.test(line)) return true;
    if (ACADEMIC_BOILERPLATE_PATTERNS.some((p) => p.test(line))) return true;
    if (RESEARCHGATE_BOILERPLATE_PATTERNS.some((p) => p.test(line))) return true;
    return false;
}
function isStandaloneUrl(line: string): boolean {
    return URL_LINE.test(line);
}

// ---------------------------------------------------------------------------
// ResearchGate section stripping (multi-line blocks)
// ---------------------------------------------------------------------------

const RG_SECTION_SIGNATURE = /See discussions, stats, and author profiles/i;
const RG_SECTION_END_MARKERS = [
    /The user has requested enhancement/i,
    /All content following this page was uploaded/i,
];
const RG_SECTION_CONTINUATION = [
    /^\s*\d+\s+(PUBLICATIONS|READS|CITATIONS)\b/i,
    /^\s*(PUBLICATIONS|READS|CITATIONS)\s*$/i,
    /^\s*SEE PROFILE\s*$/i,
    /^\s*View\s+project\s*$/i,
    /^\s*\d+\s+authors?\s*:/i,
    /^\s*https?:\/\/www\.researchgate\.net\/\S+\s*$/i,
    /^\s*[\w\u00C0-\u024F]+(?:\s+[\w\u00C0-\u024F]+){0,4}\s+University\s*$/i,
    /\bView\s+publication\s+stats?\b/i,
];
const TRAILING_RG_PATTERNS = [/^\s*View\s+publication\s+stats?\s*$/i];

function stripRgSections(text: string): { text: string; sectionsRemoved: number } {
    const lines = text.split('\n');
    const skip = new Set<number>();
    let sectionsRemoved = 0;

    let i = 0;
    while (i < lines.length) {
        const currentLine = lines[i];
        if (currentLine !== undefined && RG_SECTION_SIGNATURE.test(currentLine)) {
            const start = i;
            let end = i;
            let foundEnd = false;

            for (let j = i; j < Math.min(i + 50, lines.length); j++) {
                const lineJ = lines[j];
                if (lineJ === undefined) continue;
                if (RG_SECTION_END_MARKERS.some((p) => p.test(lineJ))) {
                    end = j + 1;
                    while (end < lines.length) {
                        const lineEnd = lines[end];
                        if (lineEnd === undefined) break;
                        if (RG_SECTION_CONTINUATION.some((p) => p.test(lineEnd))) {
                            end++;
                        } else if (lineEnd.trim() === '') {
                            end++;
                        } else {
                            break;
                        }
                    }
                    while (end < lines.length && lines[end]?.trim() === '') end++;
                    foundEnd = true;
                    break;
                }
            }

            if (!foundEnd) {
                for (let j = i; j < Math.min(i + 30, lines.length); j++) {
                    if (
                        lines[j]?.trim() === '' &&
                        j + 1 < lines.length &&
                        lines[j + 1]?.trim() === ''
                    ) {
                        end = j;
                        foundEnd = true;
                        break;
                    }
                }
                if (!foundEnd) end = Math.min(i + 30, lines.length);
            }

            for (let k = start; k < Math.min(end, lines.length); k++) skip.add(k);
            sectionsRemoved++;
            i = end;
            continue;
        }
        i++;
    }

    for (let k = Math.max(0, lines.length - 10); k < lines.length; k++) {
        const line = lines[k];
        if (line !== undefined && TRAILING_RG_PATTERNS.some((p) => p.test(line))) {
            skip.add(k);
        }
    }

    const kept: string[] = [];
    for (let k = 0; k < lines.length; k++) {
        if (!skip.has(k)) kept.push(lines[k] ?? '');
    }
    return { text: kept.join('\n'), sectionsRemoved };
}

// ---------------------------------------------------------------------------
// Repeated line detection
// ---------------------------------------------------------------------------

function findRepeatedLines(lines: string[], threshold: number): Set<string> {
    const counts = new Map<string, number>();
    for (const l of lines) {
        const s = l.trim();
        counts.set(s, (counts.get(s) ?? 0) + 1);
    }
    const repeated = new Set<string>();
    for (const [text, count] of counts) {
        if (count < threshold) continue;
        if (text.length < 25) continue;
        if (/^\d+$/.test(text)) continue;
        if (/^[\d.,/\-+×*=|: ]+$/.test(text)) continue;
        if (!text.includes(' ')) continue;
        repeated.add(text);
    }
    return repeated;
}

function similarityRatio(a: string, b: string): number {
    if (a.length === 0 && b.length === 0) return 1;
    if (a.length === 0 || b.length === 0) return 0;
    const maxLen = Math.max(a.length, b.length);
    if (Math.abs(a.length - b.length) / maxLen > 0.25) return 0;
    // Simple token-matching ratio. Not SequenceMatcher but good enough for
    // near-duplicate header detection with a 0.85 threshold.
    const bigramsA = new Map<string, number>();
    for (let i = 0; i < a.length - 1; i++) {
        const bg = a.slice(i, i + 2);
        bigramsA.set(bg, (bigramsA.get(bg) ?? 0) + 1);
    }
    let matches = 0;
    let bLen = 0;
    for (let i = 0; i < b.length - 1; i++) {
        bLen++;
        const bg = b.slice(i, i + 2);
        const remaining = bigramsA.get(bg);
        if (remaining && remaining > 0) {
            bigramsA.set(bg, remaining - 1);
            matches++;
        }
    }
    const totalBigrams = a.length - 1 + bLen;
    return totalBigrams === 0 ? 0 : (2 * matches) / totalBigrams;
}

function findFuzzyRepeatedLines(
    lines: string[],
    threshold: number,
    similarity = 0.85,
): Set<number> {
    const remove = new Set<number>();
    const buckets = new Map<number, Array<{ idx: number; text: string }>>();
    for (let i = 0; i < lines.length; i++) {
        const s = lines[i]?.trim() ?? '';
        if (s.length < 5) continue;
        const bucket = Math.floor(s.length / 5);
        if (!buckets.has(bucket)) buckets.set(bucket, []);
        buckets.get(bucket)?.push({ idx: i, text: s });
    }
    for (const bucketLines of buckets.values()) {
        if (bucketLines.length < threshold) continue;
        const used = new Set<number>();
        for (let a = 0; a < bucketLines.length; a++) {
            if (used.has(a)) continue;
            const entryA = bucketLines[a];
            if (!entryA) continue;
            const group: number[] = [entryA.idx];
            for (let b = a + 1; b < bucketLines.length; b++) {
                if (used.has(b)) continue;
                const entryB = bucketLines[b];
                if (!entryB) continue;
                if (similarityRatio(entryA.text, entryB.text) >= similarity) {
                    group.push(entryB.idx);
                    used.add(b);
                }
            }
            if (group.length >= threshold) {
                for (const idx of group) remove.add(idx);
                used.add(a);
            }
        }
    }
    return remove;
}

// ---------------------------------------------------------------------------
// Hyphen / spaced-letter / rewrap / collapse passes
// ---------------------------------------------------------------------------

const HYPHEN_BREAK = /(\w+)-\s*$/;

function fixHyphenBreaks(lines: string[]): string[] {
    const result: string[] = [];
    let i = 0;
    while (i < lines.length) {
        const line = lines[i] ?? '';
        const m = HYPHEN_BREAK.exec(line);
        if (m && i + 1 < lines.length) {
            const nextLine = (lines[i + 1] ?? '').replace(/^\s+/, '');
            if (nextLine && /[a-z\u00E0-\u024F]/.test(nextLine[0] ?? '')) {
                result.push(line.slice(0, m.index) + m[1] + nextLine);
                i += 2;
                continue;
            }
        }
        result.push(line);
        i++;
    }
    return result;
}

function fixSpacedLetters(lines: string[]): string[] {
    return lines.map((line) => {
        const stripped = line.trim();
        if (!isSpacedLetters(stripped)) return line;
        const raw = stripped.replace(/\s+/g, '');
        const matches =
            raw.match(/[aeiouy]*[bcdfghjklmnpqrstvwxyz]+[aeiouy]*|./gi) ?? [];
        const rejoined = matches.filter((w) => w.length >= 2).join(' ');
        return rejoined.length > 0 ? rejoined : raw;
    });
}

const SENTENCE_TERMINATORS = new Set([
    '.',
    '!',
    '?',
    ':',
    ';',
    '"',
    "'",
    ')',
    ']',
    '}',
    '\u201D',
    '\u2019',
]);

function looksLikeMidsentenceBreak(line: string, nextLine: string): boolean {
    if (!line.trim() || !nextLine.trim()) return false;
    const lastChar = line.trimEnd().slice(-1);
    const firstChar = nextLine.trimStart().slice(0, 1);
    if (
        !SENTENCE_TERMINATORS.has(lastChar) &&
        firstChar &&
        firstChar === firstChar.toLowerCase() &&
        firstChar !== firstChar.toUpperCase()
    ) {
        return true;
    }
    if (lastChar === ',') return true;
    return false;
}

function rewrapParagraphs(lines: string[], aggressive: boolean): string[] {
    const result: string[] = [];
    let buffer = '';
    for (const line of lines) {
        const stripped = line.trim();
        if (!stripped) {
            if (buffer) {
                result.push(buffer);
                buffer = '';
            }
            result.push('');
            continue;
        }
        if (buffer) {
            const firstChar = stripped[0] ?? '';
            const aggressiveJoin =
                aggressive && firstChar !== '' && firstChar !== firstChar.toUpperCase();
            if (looksLikeMidsentenceBreak(buffer, stripped) || aggressiveJoin) {
                buffer = `${buffer.trimEnd()} ${stripped}`;
                continue;
            }
            result.push(buffer);
            buffer = stripped;
        } else {
            buffer = stripped;
        }
    }
    if (buffer) result.push(buffer);
    return result;
}

function collapseBlankLines(lines: string[], maxConsecutive = 2): string[] {
    const result: string[] = [];
    let blankCount = 0;
    for (const line of lines) {
        if (line.trim() === '') {
            blankCount++;
            if (blankCount <= maxConsecutive) result.push('');
        } else {
            blankCount = 0;
            result.push(line);
        }
    }
    return result;
}

// ---------------------------------------------------------------------------
// Main pipeline
// ---------------------------------------------------------------------------

export function cleanText(
    text: string,
    options: TextCleanerOptions = {},
): TextCleanerResult {
    const {
        aggressive = false,
        removeBoilerplate = true,
        removeUrls = true,
        removeToc = true,
        extraPatterns = [],
        source = 'pdf',
    } = options;
    const ocrMode = source === 'ocr';

    let working = normalizeUnicode(text);
    const { text: rgStripped, sectionsRemoved } = stripRgSections(working);
    working = rgStripped;

    const lines = working.split('\n');
    const originalLines = lines.length;

    const customPatterns: RegExp[] = [];
    for (const pat of extraPatterns) {
        try {
            customPatterns.push(new RegExp(pat, 'i'));
        } catch {
            // Silently skip invalid regex — same behavior as Python version's warning.
        }
    }

    const baseThreshold = aggressive
        ? Math.max(2, Math.floor(1 + Math.sqrt(lines.length / 30)))
        : Math.max(3, Math.floor(2 + Math.sqrt(lines.length / 25)));

    const repeated = findRepeatedLines(lines, baseThreshold);
    const fuzzyIndices = aggressive
        ? findFuzzyRepeatedLines(lines, baseThreshold)
        : new Set<number>();

    const removed = {
        pageNumbers: 0,
        tocLeaders: 0,
        footnoteMarkers: 0,
        orphanBullets: 0,
        boilerplate: 0,
        urls: 0,
        ocrJunk: 0,
        spacedLetters: 0,
        repeated: 0,
        fuzzyRepeated: 0,
        custom: 0,
    };

    const cleaned: string[] = [];
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i] ?? '';
        const stripped = line.trim();
        const prev = i > 0 ? (lines[i - 1] ?? '') : '';
        const next = i + 1 < lines.length ? (lines[i + 1] ?? '') : '';

        if (isPageNumber(line, prev, next)) {
            removed.pageNumbers++;
            continue;
        }
        if (removeToc && isToCLeader(line)) {
            removed.tocLeaders++;
            continue;
        }
        if (isFootnoteMarker(line)) {
            removed.footnoteMarkers++;
            continue;
        }
        if (isOrphanBullet(line)) {
            removed.orphanBullets++;
            continue;
        }
        if (STANDALONE_SEPARATOR.test(line)) {
            removed.orphanBullets++;
            continue;
        }
        if (removeBoilerplate && isBoilerplate(line)) {
            removed.boilerplate++;
            continue;
        }
        if (removeUrls && isStandaloneUrl(line)) {
            removed.urls++;
            continue;
        }
        if (isOcrJunk(line, ocrMode)) {
            removed.ocrJunk++;
            continue;
        }
        if (isSpacedLetters(line)) {
            removed.spacedLetters++;
            continue;
        }
        if (repeated.has(stripped)) {
            removed.repeated++;
            continue;
        }
        if (fuzzyIndices.has(i)) {
            removed.fuzzyRepeated++;
            continue;
        }
        if (customPatterns.some((p) => p.test(line))) {
            removed.custom++;
            continue;
        }

        cleaned.push(line);
    }

    let result = ocrMode ? fixSpacedLetters(cleaned) : cleaned;
    result = fixHyphenBreaks(result);
    result = rewrapParagraphs(result, aggressive);
    result = collapseBlankLines(result);

    while (result.length > 0 && result[0]?.trim() === '') result.shift();
    while (result.length > 0 && result[result.length - 1]?.trim() === '') result.pop();

    return {
        cleanedText: result.join('\n'),
        stats: {
            source,
            originalLines,
            finalLines: result.length,
            rgSectionsStripped: sectionsRemoved,
            repeatedLinesDetected: repeated.size,
            repeatThreshold: baseThreshold,
            fuzzyRepeatedLines: fuzzyIndices.size,
            removed,
        },
    };
}

export class TextCleanerService {
    constructor(private readonly logger: LoggerService) {}

    public clean(text: string, options: TextCleanerOptions = {}): TextCleanerResult {
        const result = cleanText(text, options);
        this.logger.info(
            LOG_COMPONENTS.PIPELINE_MANAGER,
            'Deterministic text cleanup complete',
            {
                source: result.stats.source,
                originalLines: result.stats.originalLines,
                finalLines: result.stats.finalLines,
                removed: result.stats.removed,
                rgSectionsStripped: result.stats.rgSectionsStripped,
                repeatedLinesDetected: result.stats.repeatedLinesDetected,
                fuzzyRepeatedLines: result.stats.fuzzyRepeatedLines,
            },
        );
        return result;
    }
}
