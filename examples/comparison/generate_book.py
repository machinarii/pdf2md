"""Generate an original three-page book excerpt for the output gallery."""
from pathlib import Path
import pymupdf


def main():
    output = Path('artifacts/readme-demo/book')
    output.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    chapters = ['Collecting', 'Checking', 'Sharing']
    paragraphs = [
        ['The archive connects readers with an inter-',
         'national community. Each record includes infor-',
         'mation about the source and its publication.',
         'The team records each decision through careful docu-',
         'mentation helps later readers verify the result.'],
        ['A self-supervised method can identify patterns.',
         'Readers can inspect the training data. This self-',
         'supervised example also shows why every printed',
         'hyphen should not be removed in the same way.'],
        ['Keep the original scan alongside the extracted text.',
         'A clean paragraph should preserve the meaning of',
         'the source while removing artificial line breaks.',
         'Readers can then search, quote, and review it.'],
        ['Page furniture belongs outside the body text.',
         'A repeated running header provides navigation on',
         'paper, but becomes distracting inside an archive.',
         'Page numbers should not interrupt a paragraph.'],
    ]
    for number, title in enumerate(chapters, 1):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 28), 'FIELD NOTES ON DOCUMENT ARCHIVES', fontsize=9)
        page.insert_text((72, 100), f'Chapter {number}: {title}', fontsize=18, fontname='hebo')
        y = 148
        for lines in paragraphs:
            for line in lines:
                page.insert_text((72, y), line, fontsize=11)
                y += 16
            y += 18
        page.insert_text((300, 770), str(number), fontsize=9)
    doc.set_metadata({'title': 'Field Notes on Document Archives', 'author': 'pdf2md contributors'})
    doc.save(output / 'source.pdf')
    doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(output / 'source.png')
    doc.close()


if __name__ == '__main__':
    main()
