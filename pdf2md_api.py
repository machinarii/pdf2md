"""Small, isolated Python API for the standalone pdf2md converter.

Conversion runs in a subprocess because the legacy renderer uses module globals.
No OCR or model calls are enabled by this API.
"""
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import io

from structured import BoundedZip, ResourceLimitError


class ConversionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConversionResult:
    markdown: str
    diagnostics: str
    format: str


def detect_format(data: bytes, filename: str = '') -> str:
    """Recognize supported containers; legacy formats use a filename hint."""
    if data[:1024].lstrip().startswith(b'%PDF-'):
        return '.pdf'
    if data.lstrip().startswith(b'{\\rtf'):
        return '.rtf'
    if data.startswith(b'PK'):
        with BoundedZip(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if 'word/document.xml' in names:
                return '.docx'
            if 'META-INF/container.xml' in names:
                return '.epub'
            if 'mimetype' in names:
                info = archive.getinfo('mimetype')
                if info.file_size < 128 and archive.read(info) == b'application/vnd.oasis.opendocument.text':
                    return '.odt'
    hint = Path(filename).suffix.lower()
    if hint in ('.doc', '.odt', '.rtf', '.epub', '.docx', '.pdf'):
        return hint
    raise ConversionError('unrecognized document; supply a supported filename hint')


def convert_bytes(data: bytes, *, filename: str = '', timeout: float = 300,
                  max_bytes: int = 128 * 1024 * 1024) -> ConversionResult:
    """Convert bounded bytes to Markdown without network calls or persistent assets.

Embedded-image extraction is disabled: temporary files must not leave broken links.
Use the CLI when persistent images, audits, OCR, or model controls are needed.
"""
    if max_bytes < 1 or len(data) > max_bytes:
        raise ConversionError('input byte budget exceeded')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    try:
        kind = detect_format(data, filename)
        if kind not in (".pdf", ".epub", ".docx"):
            raise ConversionError("the API supports PDF, EPUB and DOCX; use the CLI for legacy Office formats")
        with tempfile.TemporaryDirectory(prefix='pdf2md-api-') as temp:
            source = Path(temp, (Path(filename).stem or 'document') + kind)
            source.write_bytes(data)
            output = Path(temp, 'output.md')
            run = subprocess.run([sys.executable, str(Path(__file__).with_name('pdf2md_all.py')),
                str(source), '-o', str(output), '--no-toc', '--no-visual-ai', '--no-images'],
                capture_output=True, text=True, timeout=timeout)
            if run.returncode:
                raise ConversionError(run.stderr.strip() or run.stdout.strip())
            return ConversionResult(output.read_text(encoding='utf-8'), run.stderr.strip(), kind[1:])
    except (OSError, zipfile.BadZipFile, ResourceLimitError, subprocess.TimeoutExpired) as error:
        raise ConversionError(str(error)) from error


def convert_file(path, *, timeout: float = 300, max_bytes: int = 128 * 1024 * 1024) -> ConversionResult:
    source = Path(path)
    if max_bytes < 1:
        raise ValueError('max_bytes must be positive')
    with source.open('rb') as stream:
        data = stream.read(max_bytes + 1)
    return convert_bytes(data, filename=source.name, timeout=timeout, max_bytes=max_bytes)
