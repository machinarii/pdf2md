"""Generate the original-text README demo; requires only PyMuPDF.

Run from the repository root. Outputs are saved in ignored artifacts/.
"""
from pathlib import Path
import pymupdf


def main():
    output = Path('artifacts/readme-demo')
    output.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((48, 48), 'A Small Guide to Clear Documents', fontname='hebo', fontsize=20)
    page.insert_text((48, 73), 'An original two-column demonstration for pdf2md', fontsize=10)
    columns = [
        (48, '1 Introduction', [
            'A useful archive preserves the structure',
            'of a document as well as its words. Short',
            'lines on a printed page should become',
            'one readable paragraph in Markdown.',
            '',
            'Research papers often place two columns',
            'on the same page. Reading order matters:',
            'finish the left column before continuing',
            'with the text at the top of the right.',
            '',
            'A heading should remain a heading.',
            'Its size and weight provide evidence',
            'that separates it from ordinary prose.',
            'The original page remains the reference.',
        ]),
        (324, '2 Preservation', [
            'Clear text is easier to search and review.',
            'Keep the source file so each conversion',
            'can be checked against the printed page.',
            'Record the tool version with the output.',
            '',
            'Automatic conversion still needs review.',
            'Complex tables and damaged characters',
            'can require a closer look at the source.',
            'A readable result is a useful first step.',
            '',
            'This small example illustrates headings',
            'and paragraph reflow on a simple layout.',
            'It is a demonstration, not a benchmark',
            'of every document or extraction method.',
        ]),
    ]
    for x, heading, lines in columns:
        page.insert_text((x, 120), heading, fontname='hebo', fontsize=16)
        for index, line in enumerate(lines):
            if line:
                page.insert_text((x, 148 + index * 16), line, fontsize=11)
    doc.set_metadata({'title': 'A Small Guide to Clear Documents', 'author': 'pdf2md contributors'})
    doc.save(output / 'source.pdf')
    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(output / 'source.png')
    doc.close()


if __name__ == '__main__':
    main()
