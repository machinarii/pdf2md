import { cleanText } from '@/services/TextCleanerService';

describe('TextCleanerService — Unicode normalization', () => {
    it('replaces common ligatures and smart quotes', () => {
        const input = 'of\uFB01ce — She said \u201Chello\u201D\u2014yes.';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toContain('office');
        expect(cleanedText).toContain('"hello"');
        expect(cleanedText).toContain('--');
    });

    it('strips zero-width and BOM characters', () => {
        const input = 'a\u200Bb\uFEFFc';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toBe('abc');
    });

    it('normalizes non-breaking and exotic whitespace to plain space', () => {
        const input = 'word1\u00A0word2\u2009word3';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toBe('word1 word2 word3');
    });

    it('converts form-feed to newline', () => {
        const input = 'page1\fpage2';
        const { cleanedText } = cleanText(input, { aggressive: false });
        expect(cleanedText).toContain('page1');
        expect(cleanedText).toContain('page2');
    });
});

describe('TextCleanerService — page numbers', () => {
    it('removes bare numbers isolated between blank lines', () => {
        const input = 'Paragraph one.\n\n12\n\nParagraph two continues here.';
        const { cleanedText, stats } = cleanText(input);
        expect(stats.removed.pageNumbers).toBe(1);
        expect(cleanedText).not.toMatch(/^12$/m);
    });

    it('preserves inline numbers inside paragraphs (PageRank protection)', () => {
        const input = 'We set Page 1 of the matrix to the first row.';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toContain('Page 1');
    });

    it('removes "- 12 -" dash-wrapped page numbers', () => {
        const input = 'text\n- 12 -\nmore text';
        const { stats } = cleanText(input);
        expect(stats.removed.pageNumbers).toBe(1);
    });
});

describe('TextCleanerService — TOC leaders and footnote markers', () => {
    it('removes dot-leader TOC entries', () => {
        const input =
            'Book\n\nChapter 1 .......... 5\nChapter 2 .......... 42\n\nBody.';
        const { stats } = cleanText(input);
        expect(stats.removed.tocLeaders).toBe(2);
    });

    it('removes standalone footnote markers', () => {
        const input = 'Text.\n\n[1]\n\nMore text.';
        const { stats } = cleanText(input);
        expect(stats.removed.footnoteMarkers).toBe(1);
    });
});

describe('TextCleanerService — hyphen rejoining and rewrap', () => {
    it('rejoins hyphenated words across lines', () => {
        const input = 'The quick brown fox jumps over the lazy docu-\nment again.';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toContain('document');
        expect(cleanedText).not.toContain('docu-');
    });

    it('rewraps hard-wrapped mid-sentence lines', () => {
        const input = 'This is a long sentence that was\nhard-wrapped mid-sentence.';
        const { cleanedText } = cleanText(input);
        expect(cleanedText.split('\n').filter((l) => l.trim()).length).toBe(1);
    });

    it('keeps paragraph breaks intact', () => {
        const input = 'First paragraph.\n\nSecond paragraph continues here.';
        const { cleanedText } = cleanText(input);
        expect(cleanedText).toMatch(/First paragraph\.\n\nSecond paragraph/);
    });
});

describe('TextCleanerService — repeated headers/footers', () => {
    it('removes lines repeated beyond the threshold', () => {
        const header = 'Acme Corporation | Annual Report 2024';
        const body = Array.from(
            { length: 80 },
            (_, i) =>
                `${header}\nPage content paragraph number ${i + 1} goes here to pad body length.`,
        ).join('\n\n');
        const { stats } = cleanText(body);
        expect(stats.removed.repeated).toBeGreaterThan(0);
    });
});

describe('TextCleanerService — boilerplate', () => {
    it('removes copyright and ISBN lines', () => {
        const input =
            'Body text.\n\n\u00A9 2024 Acme Corp\nAll rights reserved.\nISBN: 978-3-16-148410-0\n\nEpilogue.';
        const { stats } = cleanText(input);
        expect(stats.removed.boilerplate).toBeGreaterThanOrEqual(3);
    });
});

describe('TextCleanerService — OCR mode spaced letters', () => {
    it('rejoins spaced-letter OCR artifacts', () => {
        const input = 'Body.\n\nw i t h a r e c a p a b l e\n\nEnd.';
        const { cleanedText } = cleanText(input, { source: 'ocr' });
        expect(cleanedText).not.toMatch(/w i t h/);
    });
});
