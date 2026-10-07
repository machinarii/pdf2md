"""
structured.py — EPUB, DOCX, and (via LibreOffice) DOC / ODT / RTF input.

These formats carry real structure -- heading levels, list nesting, tables,
footnotes, metadata -- so nothing needs to be inferred from geometry. The
reader turns the native markup into typed Blocks, the outline tree still
validates heading numbering and TOC membership, and the renderer emits the
same YAML / title block / grouped contents / body layout as the PDF path.

  EPUB   container.xml -> OPF (metadata, manifest, spine) -> each XHTML
         spine item parsed to blocks; nav.xhtml (EPUB 3) or toc.ncx (EPUB 2)
         supplies contents truth and section titles for files with no heading
  DOCX   word/document.xml paragraphs and tables; styles.xml for heading
         levels (outlineLvl, or Heading N names); footnotes.xml; core props
  DOC / ODT / RTF   converted to DOCX with `soffice --headless`, then as DOCX

Only the standard library is used: zipfile, xml.etree, html.parser.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin
import xml.etree.ElementTree as ET


@dataclass
class Block:
    kind: str                      # heading|para|list_item|quote|code|table|caption|footnote|image|hr|title|meta
    text: str = ""
    level: int = 0                 # heading level / list nesting
    rows: list = field(default_factory=list)      # table rows (list of cell lists)
    note_id: str = ""              # footnote id
    src: str = ""                  # image path inside the container
    ordered: bool = False
    size: float = 0.0              # CSS font size (pt) when known
    bold: bool = False
    cells: list = field(default_factory=list)
    header_rows: int = 1


class ResourceLimitError(ValueError):
    """The source exceeds a bounded parser budget."""


MAX_ENTRY_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
MAX_XML_DEPTH = 256
MAX_XML_NODES = 500_000
MAX_TABLE_SLOTS = 1_000_000


class BoundedZip(zipfile.ZipFile):
    def __init__(self, path):
        super().__init__(path)
        self.bytes_read = 0
        entries = self.infolist()
        if (len(entries) > MAX_ARCHIVE_ENTRIES or
                any(e.file_size > MAX_ENTRY_BYTES for e in entries) or
                sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES):
            self.close()
            raise ResourceLimitError('archive decompression budget exceeded')

    def read(self, name, pwd=None):
        info = name if isinstance(name, zipfile.ZipInfo) else self.getinfo(name)
        if self.bytes_read + info.file_size > MAX_ARCHIVE_BYTES:
            raise ResourceLimitError('cumulative archive read budget exceeded')
        with self.open(info, pwd=pwd) as stream:
            data = stream.read(MAX_ENTRY_BYTES + 1)
        self.bytes_read += len(data)
        if len(data) > MAX_ENTRY_BYTES or self.bytes_read > MAX_ARCHIVE_BYTES:
            raise ResourceLimitError('archive read budget exceeded')
        return data


def bounded_xml(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    if len(data) > MAX_ENTRY_BYTES:
        raise ResourceLimitError('XML byte budget exceeded')
    if b'<!ENTITY' in data.replace(b'\x00', b'').upper() or b'<!DOCTYPE' in data.replace(b'\x00', b'').upper():
        raise ResourceLimitError('XML DTD and entity declarations are not supported')
    parser = ET.XMLPullParser(events=('start', 'end'))
    depth = count = 0
    root = None
    for offset in range(0, len(data), 65536):
        parser.feed(data[offset:offset+65536])
        for event, element in parser.read_events():
            if event == 'start':
                if root is None:
                    root = element
                depth += 1; count += 1
                if depth > MAX_XML_DEPTH or count > MAX_XML_NODES:
                    raise ResourceLimitError('XML depth/node budget exceeded')
            else:
                depth -= 1
    parser.close()
    if root is None:
        raise ET.ParseError('empty XML')
    return root


def canonical_table(cells):
    """One origin per logical cell; covered positions explicitly reference it."""
    slots = {}
    for source in cells:
        r, c = source['row'], source['column']
        rs, cs = source.get('rowspan') or 1, source.get('colspan') or 1
        if min(r, c) < 0 or min(rs, cs) < 1 or (r+rs)*(c+cs) > MAX_TABLE_SLOTS:
            raise ResourceLimitError('table expansion budget exceeded')
        if len(slots) + rs*cs > MAX_TABLE_SLOTS:
            raise ResourceLimitError('table slot budget exceeded')
        for rr in range(r, r+rs):
            for cc in range(c, c+cs):
                if (rr, cc) in slots:
                    raise ValueError('overlapping table spans')
                slots[rr, cc] = (dict(source, rowspan=rs, colspan=cs) if (rr, cc) == (r, c)
                                else {'row': rr, 'column': cc, 'covered_by': [r, c]})
    return [slots[k] for k in sorted(slots)]


def expanded_table(cells):
    slots = canonical_table(cells)
    if not slots:
        return []
    height = max(s['row'] for s in slots)+1
    width = max(s['column'] for s in slots)+1
    if height*width > MAX_TABLE_SLOTS:
        raise ResourceLimitError('table grid budget exceeded')
    origins = {(c['row'], c['column']): c.get('text', '') for c in cells}
    rows = [[''] * width for _ in range(height)]
    for slot in slots:
        origin = tuple(slot.get('covered_by', [slot['row'], slot['column']]))
        rows[slot['row']][slot['column']] = origins[origin]
    return rows


def structured_table_rows(block):
    rows = expanded_table(block.cells) if block.cells else block.rows
    depth = min(block.header_rows, len(rows))
    if depth > 1:
        header = [' — '.join(dict.fromkeys(rows[r][c] for r in range(depth) if rows[r][c]))
                  for c in range(len(rows[0]))]
        return [header] + rows[depth:]
    if depth == 0:
        return [[''] * max(map(len, rows), default=0)] + rows
    return rows


class UnsupportedMath(ValueError):
    pass


def math_latex(element):
    """Translate explicit MathML/OMML structure; never infer PDF equations."""
    tag = element.tag.rsplit('}', 1)[-1]
    if element.get('mathvariant') not in (None, 'normal', 'italic'):
        raise UnsupportedMath('unsupported math variant')
    children = list(element)
    def child(name):
        return next((x for x in children if x.tag.rsplit('}', 1)[-1] == name), None)
    def convert(node):
        return math_latex(node) if node is not None else ''
    def sequence():
        return ''.join(convert(x) for x in children)
    if tag in ('mi', 'mn', 'mo', 't'):
        text = element.text or ''
        symbols = {'α':r'\alpha ', 'β':r'\beta ', 'γ':r'\gamma ', 'θ':r'\theta ',
                   'π':r'\pi ', '∑':r'\sum ', '∫':r'\int ', '∞':r'\infty ',
                   '≤':r'\le ', '≥':r'\ge ', '≠':r'\ne ', '×':r'\times ', '−':'-'}
        return ''.join(symbols.get(c, '\\'+c if c in '{}%&#_$' else c) for c in text)
    if tag == 'mtext':
        return r'\text{' + (element.text or '').replace('\\', r'\backslash ').replace('{',r'\{').replace('}',r'\}') + '}'
    if tag in ('math','mrow','oMath','oMathPara','e','num','den','sup','sub','deg','r'):
        return sequence()
    if tag in ('rPr','ctrlPr','fPr','sSupPr','sSubPr','sSubSupPr','radPr'):
        return ''
    if tag in ('mfrac','f'):
        props = child('fPr')
        if props is not None and any(n.tag.rsplit('}',1)[-1] == 'type' and
                next(iter(n.attrib.values()), 'bar') != 'bar' for n in props):
            raise UnsupportedMath('unsupported fraction layout')
        a,b = (children if tag == 'mfrac' else [child('num'),child('den')])
        if a is None or b is None:
            raise UnsupportedMath('missing fraction operand')
        return r'\frac{' + convert(a) + '}{' + convert(b) + '}'
    if tag in ('msup','msub','msubsup'):
        needed = 3 if tag == 'msubsup' else 2
        if len(children) != needed:
            raise UnsupportedMath('invalid script arity')
        base = '{' + convert(children[0]) + '}'
        return base + (('_' if tag != 'msup' else '^') + '{' + convert(children[1]) + '}') + (
            '^{' + convert(children[2]) + '}' if needed == 3 else '')
    if tag in ('sSup','sSub','sSubSup'):
        return '{' + convert(child('e')) + '}' + (
            '_{' + convert(child('sub')) + '}' if tag != 'sSup' else '') + (
            '^{' + convert(child('sup')) + '}' if tag != 'sSub' else '')
    if tag == 'msqrt':
        return r'\sqrt{' + sequence() + '}'
    if tag in ('mroot','rad'):
        if tag == 'mroot':
            if len(children) != 2:
                raise UnsupportedMath('invalid root arity')
            base, degree = children
        else:
            base, degree = child('e'), child('deg')
        index = convert(degree)
        props = child('radPr')
        if props is not None and any(n.tag.rsplit('}',1)[-1] == 'degHide' and
                next(iter(n.attrib.values()), '1') in ('1', 'true', 'on') for n in props):
            index = ''
        return r'\sqrt' + ('['+index+']' if index else '') + '{' + convert(base) + '}'
    if tag == 'semantics':
        return convert(children[0]) if children else ''
    raise UnsupportedMath('unsupported math element: ' + tag)


def math_record(element):
    source = ET.tostring(element, encoding='unicode')
    try:
        latex = math_latex(element)
        if not latex.strip():
            raise UnsupportedMath('empty formula')
        return {'source_xml': source, 'latex': latex, 'status': 'converted'}
    except (UnsupportedMath, ValueError) as error:
        return {'source_xml': source, 'text': ' '.join(element.itertext()).strip(),
                'status': 'unsupported', 'reason': str(error)}


def math_text(record):
    return ('$' + record['latex'] + '$' if record['status'] == 'converted' else
            '[unconverted equation: ' + record.get('text', '') + ']')


GENERATOR_NAMES = re.compile(r"^(python-docx|libreoffice|openoffice|microsoft (office )?(word|user)|"
                             r"unknown( title| author)?|untitled|calibre|pandoc|author|user|admin|owner)$", re.I)


def css_style_map(css: str) -> dict[str, dict]:
    """.paraN { font-size: 18pt; font-weight: bold } -> {'paraN': {size, bold}}.
    Sizes in pt, px (x0.75), em/% (relative to 12pt)."""
    out: dict[str, dict] = {}
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
        selectors, body = m.group(1), m.group(2)
        size = None; bold = None
        ms = re.search(r"font-size\s*:\s*(\d*\.?\d+)\s*(pt|px|em|%|rem)?", body)
        if ms:
            try:
                v = float(ms.group(1))
            except ValueError:                  # a malformed rule is not fatal
                v = None
            u = ms.group(2) or "pt"
            if v is not None:
                size = v if u == "pt" else v * 0.75 if u == "px" else v * 12 if u in ("em", "rem") else v * 0.12
        mw = re.search(r"font-weight\s*:\s*(bold|[6-9]00)", body)
        if mw: bold = True
        if re.search(r"font-weight\s*:\s*(normal|400)", body): bold = False
        for sel in selectors.split(","):
            for cls in re.findall(r"\.([A-Za-z0-9_\-]+)", sel):
                d = out.setdefault(cls, {})
                if size is not None: d["size"] = size
                if bold is not None: d["bold"] = bold
    return out


def promote_css_headings(blocks: list, style_map: dict) -> int:
    """An EPUB with no <h*> tags still ranks its headings by CSS size. Body
    size is the modal paragraph size by character count; paragraphs a tier
    larger, or bold and short, are headings, levelled by size rank."""
    all_paras = [b for b in blocks if b.kind == "para"]
    paras = [b for b in all_paras if b.size]
    if len(all_paras) < 5 or not paras:
        return 0
    from collections import Counter
    weight = Counter()
    for b in paras:
        weight[round(b.size, 1)] += len(b.text)
    # when most body paragraphs carry no size (the stylesheet only sets
    # margins on them), the body is the browser default, not the modal
    # size of the few decorated paragraphs
    body = weight.most_common(1)[0][0] if len(paras) >= 0.5 * len(all_paras) else 12.0
    cands = [b for b in paras if b.size >= body * 1.15 or (b.bold and b.size >= body - 0.1 and len(b.text) < 90
                                                            and not b.text.rstrip().endswith((".", ",", ";")))]
    cands = [b for b in cands if len(b.text) < 160 and not b.text.rstrip().endswith((".", ",", ";"))]
    if not cands:
        return 0
    sizes = sorted({round(b.size, 1) for b in cands}, reverse=True)
    rank = {sz: i + 1 for i, sz in enumerate(sizes)}
    for b in cands:
        b.kind = "heading"; b.level = min(6, rank[round(b.size, 1)] + (1 if b.size < body * 1.15 else 0))
    return len(cands)


STRUCTURED_EXT = {".epub", ".docx", ".doc", ".odt", ".rtf"}


# ===========================================================================
# HTML (XHTML) -> blocks
# ===========================================================================
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre",
              "figcaption", "caption", "div", "section", "article", "aside", "header",
              "footer", "table", "tr", "td", "th", "ul", "ol", "figure", "hr", "br", "nav",
              "dt", "dd"}


def decode_xml(raw: bytes) -> str:
    """Decode XHTML/XML honouring its BOM or declared encoding.

    Decoding everything as UTF-8 mangled latin-1 accents into replacement
    characters, and turned a perfectly legal UTF-16 document into a wall of
    NUL bytes that html.parser saw no tags in -- the whole file then landed
    in the output as one paragraph of raw markup.
    """
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"),
                     (b"\xfe\xff", "utf-16")):
        if raw.startswith(bom):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                break
    head = raw[:1024]
    m = re.search(br"""encoding\s*=\s*["']([-\w.]+)["']""", head)
    if not m:
        m = re.search(br"""charset\s*=\s*["']?([-\w.]+)""", head, re.I)
    if m:
        enc = m.group(1).decode("ascii", "replace")
        if enc.lower().replace("_", "-") not in ("utf-8", "utf8", "us-ascii", "ascii"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                pass
    # A file that declares utf-8 but is not utf-8 is common in the wild.
    # Losing every accented word to U+FFFD is worse than trying the two
    # encodings that actually produce readable text; only if both fail do we
    # fall back to lossy replacement.
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


class _HtmlBlocks(HTMLParser):
    """Linear pass over an XHTML chapter, emitting Blocks. Inline emphasis is
    kept as Markdown; footnote references become [^id] markers."""

    def __init__(self, style_map: dict | None = None,
                 spine_index: dict | None = None, href: str = ""):
        super().__init__(convert_charrefs=True)
        self.style_map = style_map or {}
        self.spine_index = spine_index or {}
        self.href = href
        self.blocks: list[Block] = []
        self.stack: list[str] = []
        self.buf: list[str] = []
        self.cur: Block | None = None
        self.list_depth = 0
        self.list_ordered: list[bool] = []
        self.in_table = 0
        self.rows: list[list[str]] = []
        self.cell: list[str] | None = None
        self.in_pre = 0
        self.note: list[str] = []           # nested footnote aside ids
        self.skip = 0                       # inside <nav>/<script>/<style>
        self.title = ""
        self.in_title = False
        self.suppress = 0                   # inside a noteref / backlink anchor
        self.open_els: list[tuple[str, list[str]]] = []   # (tag, state to undo on close)
        self.origins = []
        self.table_occupied = set()
        self.cell_info = None
        self.table_headers = set()
        self.html_nodes = 0
        self.table_stack: list = []      # enclosing tables' rows

    # ---- helpers
    def _apply_style(self, cls: str):
        for c in cls.split():
            st = self.style_map.get(c)
            if not st or self.cur is None:
                continue
            if "size" in st and not self.cur.size:
                self.cur.size = st["size"]
            if st.get("bold"):
                self.cur.bold = True

    def _flush(self):
        if self.cur is not None:
            t = "".join(self.buf)
            t = t if self.in_pre else re.sub(r"[ \t\r\n]+", " ", t).strip()
            if self.cur.kind == "footnote":
                t = re.sub(r"^\s*(\d{1,3})?\s*[.):]?\s*", "", t).replace("\u21a9\ufe0e", "").replace("\u21a9", "").strip()
            if t or self.cur.kind == "hr":
                self.cur.text = t
                self.blocks.append(self.cur)
        self.cur, self.buf = None, []

    def _start(self, kind, **kw):
        self._flush()
        self.cur = Block(kind, **kw)

    # ---- parser callbacks
    #
    # Every piece of parser state that spans elements (skip, note, suppress,
    # table rows, inline emphasis) is owned by the element that opened it and
    # is undone when that element closes. The previous model used bare
    # counters keyed to a handful of tag names, which meant a
    # <section epub:type="toc"> or a <div class="footnote"> raised a counter
    # that nothing ever lowered: everything after it in the file was silently
    # dropped, or silently relabelled a footnote.
    def handle_starttag(self, tag, attrs):
        self.html_nodes += 1
        if self.html_nodes > MAX_XML_NODES or len(self.open_els) > MAX_XML_DEPTH:
            raise ResourceLimitError('HTML depth/node budget exceeded')
        a = dict(attrs)
        types = (a.get("epub:type") or a.get("role") or "").lower()
        cls = (a.get("class") or "").lower()
        undo: list[str] = []

        def done():
            if tag not in VOID_TAGS:
                self.open_els.append((tag, undo))

        if tag in ("script", "style", "nav") or "toc" in types:
            self.skip += 1; undo.append("skip"); return done()
        if self.skip:
            return done()
        if tag == "title":
            self.in_title = True; undo.append("title"); return done()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._start("heading", level=int(tag[1]))
        elif tag == "p":
            if self.note and self.cur is not None and self.cur.kind == "footnote":
                self.buf.append(" ")                # paragraph inside a footnote li: same note
            else:
                kind = "footnote" if self.note else ("caption" if "caption" in cls else "para")
                self._start(kind, note_id=self.note[-1] if self.note else "")
                self._apply_style(cls)
        elif tag == "span" and self.cur is not None and cls:
            self._apply_style(cls)                  # size often lives on the span
        elif tag in ("ul", "ol"):
            self._flush(); self.list_depth += 1; self.list_ordered.append(tag == "ol")
            undo.append("list")
        elif tag == "li" and self.note:
            # pandoc / EPUB 3: <section role="doc-endnotes"><ol><li id="fn1"><p>...
            if a.get("id"):
                self.note[-1] = a.get("id")
            self._start("footnote", note_id=self.note[-1])
        elif tag == "li":
            self._start("list_item", level=self.list_depth, ordered=bool(self.list_ordered and self.list_ordered[-1]))
        elif tag == "blockquote":
            self._flush(); self.stack.append("quote"); undo.append("quote")
        elif tag == "pre":
            self._start("code"); self.in_pre += 1; undo.append("pre")
        elif tag in ("figcaption", "caption"):
            self._start("caption")
        elif tag == "table":
            # A nested table used to wipe the enclosing table's rows.
            self._flush(); self.in_table += 1
            self.table_stack.append((self.rows, self.origins, self.cell, self.cell_info, self.table_headers, self.table_occupied))
            self.rows = []; self.origins = []; self.cell = None; self.cell_info = None; self.table_headers = set(); self.table_occupied = set()
            undo.append("table")
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self.cell = []
            row = max(0, len(self.rows)-1)
            col = 0
            while (row, col) in self.table_occupied:
                col += 1
            rs, cs = int(a.get('rowspan', '1')), int(a.get('colspan', '1'))
            if min(rs, cs) < 1 or (row+rs)*(col+cs) > MAX_TABLE_SLOTS:
                raise ResourceLimitError('HTML table expansion budget exceeded')
            self.cell_info = {'row': row, 'column': col, 'rowspan': rs, 'colspan': cs, 'text': '', 'is_header': (tag == 'th' and a.get('scope') != 'row') or any(t == 'thead' for t, _ in self.open_els)}
            if tag == 'th':
                self.table_headers.add(row)
        elif tag == "img":
            self._flush()
            self.blocks.append(Block("image", text=a.get("alt", ""), src=a.get("src", "")))
        elif tag == "hr":
            if not self.note:
                self._start("hr")
        elif tag == "br":
            self.buf.append(" ")
        elif tag == "aside" and ("footnote" in types or "footnote" in cls or "note" in types):
            self._flush(); self.note.append(a.get("id", "")); undo.append("note")
        elif tag in ("div", "section", "article", "header", "footer", "dt", "dd"):
            self._flush()
            if "footnote" in cls or "footnote" in types or "endnote" in types:
                self.note.append(a.get("id", "")); undo.append("note")
        elif tag == "a" and ("backlink" in types or "footnote-back" in cls or "back" in cls):
            self.suppress += 1; self.stack.append("backlink"); undo.append("backlink")
        elif tag == "a" and ("noteref" in types or "noteref" in cls or "footnote-ref" in cls or "footnote" in cls):
            href = a.get("href", "")
            nid = href.split("#")[-1] if "#" in href else href
            # Namespace by the file the note LIVES in, not the file the
            # reference sits in: endnotes are usually a separate spine item.
            self.buf.append(f"[^{self._note_ref(href, nid)}]")
            self.suppress += 1; self.stack.append("noteref"); undo.append("noteref")
        elif tag in ("em", "i"):
            if not self.suppress: self.buf.append("*")
            self.stack.append("em"); undo.append("em")
        elif tag in ("strong", "b"):
            if not self.suppress: self.buf.append("**")
            self.stack.append("strong"); undo.append("strong")
        elif tag == "code" and not self.in_pre:
            if not self.suppress: self.buf.append("`")
            self.stack.append("code"); undo.append("code")
        elif tag == "sup":
            self.stack.append("sup"); undo.append("sup")
        return done()

    def _note_ref(self, href: str, nid: str) -> str:
        """Namespace a note reference by the spine file that DEFINES the note.

        Prefixing by the referring file broke every endnote collected in a
        separate document: the marker became [^1-fn1] and its definition
        [^2-fn1], leaving a dangling reference and an orphan definition.
        """
        target = unquote(href.split("#")[0])
        if not target or not self.spine_index:
            return nid
        target = str(Path(self.href).parent / target) if "/" in self.href else target
        for key in (target, unquote(href.split("#")[0])):
            if key in self.spine_index:
                return f"{self.spine_index[key] + 1}-{nid}"
        return nid

    def handle_endtag(self, tag):
        # Unwind to the matching open element, closing anything left open
        # inside it. An unclosed <b> inside a <p> used to strand `suppress`
        # or leak a dangling `**` into the prose.
        idx = None
        for i in range(len(self.open_els) - 1, -1, -1):
            if self.open_els[i][0] == tag:
                idx = i
                break
        if idx is None:
            return                              # stray end tag with no start
        while len(self.open_els) > idx:
            t, undo = self.open_els.pop()
            self._close_element(t, undo)

    def _close_element(self, tag, undo):
        if "skip" in undo:
            self.skip = max(0, self.skip - 1); return
        if self.skip:
            return
        if "title" in undo:
            self.in_title = False; return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "li", "figcaption", "caption", "hr"):
            self._flush()
        elif tag == "p" and not (self.note and self.cur is not None and self.cur.kind == "footnote"):
            self._flush()
        elif tag in ("td", "th"):
            if self.cell is not None and self.rows:
                text = re.sub(r"\s+", " ", "".join(self.cell)).strip()
                self.rows[-1].append(text)
                if self.cell_info is not None:
                    self.cell_info['text'] = text
                    info = self.cell_info
                    if len(self.table_occupied) + info['rowspan']*info['colspan'] > MAX_TABLE_SLOTS:
                        raise ResourceLimitError('HTML table slot budget exceeded')
                    for rr in range(info['row'], info['row']+info['rowspan']):
                        for cc in range(info['column'], info['column']+info['colspan']):
                            if (rr, cc) in self.table_occupied:
                                raise ValueError('overlapping HTML table spans')
                            self.table_occupied.add((rr, cc))
                    self.origins.append(info)
                    self.cell_info = None
            self.cell = None

        if "list" in undo:
            self._flush(); self.list_depth = max(0, self.list_depth - 1)
            if self.list_ordered: self.list_ordered.pop()
        if "quote" in undo:
            self._flush()
            if "quote" in self.stack: self.stack.remove("quote")
        if "pre" in undo:
            self._flush(); self.in_pre = max(0, self.in_pre - 1)
        if "table" in undo:
            self.in_table = max(0, self.in_table - 1)
            if self.origins:
                depth = 0
                while any(c['row'] == depth for c in self.origins) and all(
                        c.get('is_header') for c in self.origins if c['row'] == depth):
                    depth += 1
                self.blocks.append(Block('table', rows=expanded_table(self.origins), cells=self.origins, header_rows=depth))
            if self.table_stack:
                self.rows, self.origins, self.cell, self.cell_info, self.table_headers, self.table_occupied = self.table_stack.pop()
            else:
                self.rows = []; self.origins = []; self.cell = None; self.cell_info = None; self.table_headers = set(); self.table_occupied = set()
        if "note" in undo:
            self._flush()
            if self.note: self.note.pop()
        if "noteref" in undo or "backlink" in undo:
            sentinel = "noteref" if "noteref" in undo else "backlink"
            if sentinel in self.stack: self.stack.remove(sentinel)
            self.suppress = max(0, self.suppress - 1)
        if "em" in undo and "em" in self.stack:
            if not self.suppress: self.buf.append("*")
            self.stack.remove("em")
        if "strong" in undo and "strong" in self.stack:
            if not self.suppress: self.buf.append("**")
            self.stack.remove("strong")
        if "code" in undo and "code" in self.stack:
            if not self.suppress: self.buf.append("`")
            self.stack.remove("code")
        if "sup" in undo and "sup" in self.stack:
            self.stack.remove("sup")

        if tag in ("div", "section", "article", "header", "footer", "dt", "dd") \
                and "note" not in undo:
            self._flush()

    def handle_data(self, data):
        if self.skip or self.suppress:
            return
        if self.in_title:
            self.title += data; return
        if self.cell is not None:
            self.cell.append(data); return
        if self.cur is None:
            if data.strip():
                # text outside any block element (bare text in a div)
                kind = "footnote" if self.note else ("quote" if "quote" in self.stack else "para")
                self.cur = Block(kind, note_id=self.note[-1] if self.note else "")
                self.buf.append(data)
            return
        if "sup" in self.stack and re.fullmatch(r"\s*\d{1,3}\s*", data) and not self.note:
            self.buf.append(f"[^{data.strip()}]"); return
        if "quote" in self.stack and self.cur.kind == "para":
            self.cur.kind = "quote"
        self.buf.append(data)

    def close(self):
        super().close()
        self._flush()


def html_to_blocks(markup: str, style_map: dict | None = None,
                   spine_index: dict | None = None, href: str = "") -> tuple[str, list[Block]]:
    p = _HtmlBlocks(style_map, spine_index=spine_index, href=href)
    p.feed(markup)
    p.close()
    return p.title.strip(), p.blocks


# ===========================================================================
# EPUB
# ===========================================================================
NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container",
      "opf": "http://www.idpf.org/2007/opf",
      "dc": "http://purl.org/dc/elements/1.1/",
      "ncx": "http://www.daisy.org/z3986/2005/ncx/"}


def read_epub(path: Path) -> tuple[dict, list[Block]]:
    z = BoundedZip(path)
    container = bounded_xml(z.read("META-INF/container.xml"))
    rootfile = container.find(".//c:rootfile", NS)
    if rootfile is None or not rootfile.get("full-path"):
        raise KeyError("META-INF/container.xml names no rootfile")
    opf_path = rootfile.get("full-path")
    opf_dir = str(Path(opf_path).parent)
    opf = bounded_xml(z.read(opf_path))

    # ---- metadata
    def dc(tag):
        return [(e.text or "").strip() for e in opf.findall(f".//dc:{tag}", NS) if (e.text or "").strip()]
    title = (dc("title") or [""])[0]
    meta = {"title": "" if GENERATOR_NAMES.match(title) else title, "authors": [], "publisher": (dc("publisher") or [None])[0],
            "date": (dc("date") or [None])[0], "language": (dc("language") or [None])[0],
            "isbn": [], "identifiers": dc("identifier"), "toc": [], "format": "epub"}
    for e in opf.findall(".//dc:creator", NS):
        role = e.get("{%s}role" % NS["opf"]) or ""
        if (e.text or "").strip() and role in ("", "aut") and not GENERATOR_NAMES.match(e.text.strip()):
            meta["authors"].append(e.text.strip())
    for ident in meta["identifiers"]:
        digits = re.sub(r"[^0-9X]", "", ident.upper())
        if re.search(r"isbn", ident, re.I) or (len(digits) in (10, 13) and digits.startswith(("97", "0", "1"))):
            if len(digits) in (10, 13):
                meta["isbn"].append(digits)
    if meta["date"]:
        m = re.search(r"\d{4}", meta["date"]); meta["year"] = int(m.group(0)) if m else None

    # ---- manifest + spine
    items = {}
    nav_href = None
    for it in opf.findall(".//opf:manifest/opf:item", NS):
        if not it.get("href"):
            continue                       # a manifest item with no href is unusable
        items[it.get("id")] = (it.get("href"), it.get("media-type") or "")
        if "nav" in (it.get("properties") or "").split():
            nav_href = it.get("href")
    spine = [items[ref.get("idref")][0] for ref in opf.findall(".//opf:spine/opf:itemref", NS)
             if ref.get("idref") in items]
    spine_el = opf.find(".//opf:spine", NS)
    ncx_id = spine_el.get("toc") if spine_el is not None else None

    def zpath(href):
        h = unquote(href.split("#")[0])
        return str(Path(opf_dir) / h) if opf_dir not in (".", "") else h

    style_map: dict = {}
    for _id, (href, mt) in items.items():
        if mt == "text/css" and zpath(href) in z.namelist():
            style_map.update(css_style_map(decode_xml(z.read(zpath(href)))))

    # ---- contents truth: nav.xhtml (EPUB 3) or toc.ncx (EPUB 2)
    toc: list[tuple[int, str, str]] = []          # (depth, title, href)
    if nav_href and zpath(nav_href) in z.namelist():
        toc = _parse_nav(decode_xml(z.read(zpath(nav_href))))
    elif ncx_id in items and zpath(items[ncx_id][0]) in z.namelist():
        ncx = bounded_xml(z.read(zpath(items[ncx_id][0])))
        def walk(np, depth):
            for pt in np.findall("ncx:navPoint", NS):
                lbl = pt.find("ncx:navLabel/ncx:text", NS)
                content = pt.find("ncx:content", NS)
                label = "".join(lbl.itertext()).strip() if lbl is not None else ""
                src = content.get("src", "") if content is not None else ""
                if label:
                    toc.append((depth, label, src))
                walk(pt, depth + 1)
        navmap = ncx.find("ncx:navMap", NS)
        if navmap is not None:
            walk(navmap, 1)
    meta["toc"] = toc
    title_by_file: dict[str, tuple[int, str]] = {}
    for depth, label, href in toc:
        f = unquote(href.split("#")[0])
        title_by_file.setdefault(f, (depth, label))

    # ---- chapters in spine order
    blocks: list[Block] = []
    # position of each spine file, so a noteref can be namespaced by the file
    # its href points AT (endnotes usually live in their own spine item).
    spine_pos = {unquote(h.split("#")[0]): i for i, h in enumerate(spine)}
    for href in spine:
        zp = zpath(href)
        if zp not in z.namelist():
            continue
        markup = decode_xml(z.read(zp))
        def replace_math(match):
            from html import escape
            try:
                record = math_record(bounded_xml(match.group(0)))
            except ET.ParseError as error:
                record = {'status': 'unsupported', 'source_xml': match.group(0),
                          'text': re.sub(r'<[^>]*>', '', match.group(0)), 'reason': str(error)}
            meta.setdefault('math', []).append(record)
            return escape(math_text(record))
        markup = re.sub(r'<math\b[^>]*>.*?</math\s*>', replace_math, markup, flags=re.S|re.I)
        title, chapter = html_to_blocks(markup, style_map,
                                        spine_index=spine_pos, href=href)
        idx = spine_pos.get(unquote(href.split("#")[0]), 0) + 1
        for b in chapter:
            if b.note_id:
                b.note_id = f"{idx}-{b.note_id}"
            if "[^" in b.text:
                # a reference the parser already resolved carries its own
                # "N-" prefix; only bare ids still need this file's index
                b.text = re.sub(r"\[\^([^\]]+)\]",
                                lambda m: m.group(0) if re.match(r"^\d+-", m.group(1))
                                else f"[^{idx}-{m.group(1)}]", b.text)
        # a spine item with no heading of its own takes its title from the contents
        if not any(b.kind == "heading" for b in chapter[:6]):
            hit = title_by_file.get(unquote(href.split("#")[0]))
            if hit and any(b.kind in ("para", "list_item", "table") for b in chapter) \
                    and not re.fullmatch(r"(section|chapter|part)\s*\d+", hit[1].strip(), re.I):
                depth, label = hit
                chapter.insert(0, Block("heading", text=label, level=min(depth, 6)))
        for b in chapter:
            if b.kind == "image" and b.src:
                b.src = zpath(urljoin(href, b.src))
        blocks.extend(chapter)
    meta["css_promoted"] = promote_css_headings(blocks, style_map)
    # a nav-synthesised heading directly followed by the same text as a
    # (now promoted) paragraph is one heading
    dedup: list[Block] = []
    for b in blocks:
        if dedup and b.kind == "heading" and dedup[-1].kind == "heading" \
                and re.sub(r"\W", "", b.text.lower()) == re.sub(r"\W", "", dedup[-1].text.lower()):
            dedup[-1].size = max(dedup[-1].size, b.size); continue
        dedup.append(b)
    blocks = dedup
    meta["zip"] = z
    return meta, blocks


def _parse_nav(markup: str) -> list[tuple[int, str, str]]:
    """The EPUB 3 nav document: <nav epub:type="toc"><ol><li><a href>."""
    out: list[tuple[int, str, str]] = []

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.in_toc = 0; self.depth = 0; self.href = None; self.text = []
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "nav" and "toc" in (a.get("epub:type") or ""):
                self.in_toc = 1
            if not self.in_toc: return
            if tag == "ol": self.depth += 1
            if tag == "a": self.href = a.get("href", ""); self.text = []
        def handle_endtag(self, tag):
            if not self.in_toc: return
            if tag == "ol": self.depth -= 1
            if tag == "a" and self.href is not None:
                out.append((max(1, self.depth), "".join(self.text).strip(), self.href)); self.href = None
            if tag == "nav": self.in_toc = 0
        def handle_data(self, data):
            if self.in_toc and self.href is not None: self.text.append(data)
    p = P(); p.feed(markup); p.close()
    return out


# ===========================================================================
# DOCX
# ===========================================================================
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
DCP = {"dc": "http://purl.org/dc/elements/1.1/", "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
       "dcterms": "http://purl.org/dc/terms/"}


def w(tag): return "{%s}%s" % (W, tag)


def read_docx(path: Path) -> tuple[dict, list[Block]]:
    z = BoundedZip(path)
    names = set(z.namelist())
    meta = {"title": "", "authors": [], "publisher": None, "date": None, "year": None,
            "isbn": [], "language": None, "toc": [], "format": "docx"}
    if "docProps/core.xml" in names:
        core = bounded_xml(z.read("docProps/core.xml"))
        t = core.find("dc:title", DCP); meta["title"] = (t.text or "").strip() if t is not None and t.text else ""
        c = core.find("dc:creator", DCP)
        creator = (c.text or "").strip() if c is not None else ""
        if creator and not GENERATOR_NAMES.match(creator):
            meta["authors"] = [x.strip() for x in re.split(r";|,", creator) if x.strip()]
        d = core.find("dcterms:created", DCP)
        # a tool's template date (python-docx: 2013) is not the document's date
        if d is not None and d.text and not GENERATOR_NAMES.match(creator):
            meta["date"] = d.text.strip(); m = re.search(r"\d{4}", d.text); meta["year"] = int(m.group(0)) if m else None
        if GENERATOR_NAMES.match(meta["title"]): meta["title"] = ""

    # ---- styles: id -> (name, outline level)
    styles: dict[str, tuple[str, int | None, str | None]] = {}
    if "word/styles.xml" in names:
        st = bounded_xml(z.read("word/styles.xml"))
        for s in st.findall(w("style")):
            sid = s.get(w("styleId")) or ""
            name_el = s.find(w("name")); name = name_el.get(w("val")) if name_el is not None else sid
            ol = s.find(w("pPr") + "/" + w("outlineLvl"))
            based = s.find(w("basedOn"))
            styles[sid] = (name or sid, int(ol.get(w("val"))) if ol is not None else None,
                           based.get(w("val")) if based is not None else None)

    def heading_level(style_id: str) -> int:
        seen = set()
        sid = style_id
        while sid and sid not in seen:
            seen.add(sid)
            name, ol, based = styles.get(sid, (sid, None, None))
            if ol is not None:
                return ol + 1
            m = re.match(r"^(?:heading|überschrift|titre|título)\s*(\d)", (name or "").lower())
            if m:
                return int(m.group(1))
            sid = based or ""
        m = re.match(r"^Heading(\d)$", style_id or "")
        return int(m.group(1)) if m else 0

    def style_name(style_id: str) -> str:
        return (styles.get(style_id, (style_id, None, None))[0] or style_id or "").lower()

    # ---- footnotes / endnotes
    notes: dict[str, str] = {}
    for part in ("word/footnotes.xml", "word/endnotes.xml"):
        if part in names:
            fn = bounded_xml(z.read(part))
            tag = "footnote" if "footnotes" in part else "endnote"
            for n in fn.findall(w(tag)):
                nid = n.get(w("id"))
                if nid in ("-1", "0"):
                    continue
                notes[nid] = " ".join(_para_text(p, None)[0] for p in n.findall(".//" + w("p"))).strip()

    # ---- relationships (images)
    rels: dict[str, str] = {}
    if "word/_rels/document.xml.rels" in names:
        rel = bounded_xml(z.read("word/_rels/document.xml.rels"))
        for r in rel:
            rels[r.get("Id")] = "word/" + r.get("Target") if not r.get("Target", "").startswith("/") else r.get("Target").lstrip("/")

    # ---- body
    doc = bounded_xml(z.read("word/document.xml"))
    meta['math'] = [math_record(node) for node in doc.iter()
                    if node.tag.rsplit('}', 1)[-1] == 'oMath']
    body = doc.find(w("body"))
    if body is None:
        raise KeyError("word/document.xml has no w:body")
    blocks: list[Block] = []
    used_notes: list[str] = []

    def walk(container):
        for el in container:
            if el.tag == w("p"):
                text, refs, images = _para_text(el, rels)
                used_notes.extend(refs)
                ppr = el.find(w("pPr"))
                sid = ""
                num = None
                if ppr is not None:
                    ps = ppr.find(w("pStyle")); sid = ps.get(w("val")) if ps is not None else ""
                    npr = ppr.find(w("numPr"))
                    if npr is not None:
                        il = npr.find(w("ilvl")); num = int(il.get(w("val"))) if il is not None else 0
                name = style_name(sid)
                for img in images:
                    blocks.append(Block("image", text=img[1], src=img[0]))
                if not text.strip():
                    continue
                lvl = heading_level(sid)
                if name in ("title",):
                    blocks.append(Block("title", text=text))
                elif name in ("subtitle",):
                    blocks.append(Block("meta", text=text))
                elif lvl:
                    blocks.append(Block("heading", text=text, level=min(lvl, 6)))
                elif num is not None or "list" in name:
                    blocks.append(Block("list_item", text=text, level=(num or 0) + 1,
                                        ordered="number" in name))
                elif "quote" in name:
                    blocks.append(Block("quote", text=text))
                elif "caption" in name:
                    blocks.append(Block("caption", text=text))
                elif "code" in name or "preformatted" in name or "source" in name:
                    blocks.append(Block("code", text=text))
                else:
                    # a short all-bold paragraph with no style is a run-in heading
                    runs = el.findall(".//" + w("r"))
                    bold = runs and all(r.find(w("rPr") + "/" + w("b")) is not None for r in runs
                                        if (r.find(w("t")) is not None and (r.find(w("t")).text or "").strip()))
                    if bold and len(text) < 80 and not text.endswith((".", ":")):
                        blocks.append(Block("heading", text=text, level=0))     # level from outline
                    else:
                        blocks.append(Block("para", text=text))
            elif el.tag == w("tbl"):
                origins = []
                previous = {}
                header_rows = 0
                for ri, tr in enumerate(el.findall(w('tr'))):
                    props = tr.find(w('trPr'))
                    if (ri == header_rows and props is not None and props.find(w('tblHeader')) is not None
                            and props.find(w('tblHeader')).get(w('val'), '1') not in ('0', 'false', 'off')):
                        header_rows += 1
                    before = props.find(w('gridBefore')) if props is not None else None
                    col = int(before.get(w('val'), '0')) if before is not None else 0
                    active = {}
                    for tc in tr.findall(w('tc')):
                        prop = tc.find(w('tcPr'))
                        span_node = prop.find(w('gridSpan')) if prop is not None else None
                        span = int(span_node.get(w('val'), '1')) if span_node is not None else 1
                        if span < 1 or (ri+1)*(col+span) > MAX_TABLE_SLOTS:
                            raise ResourceLimitError('DOCX table expansion budget exceeded')
                        merge = prop.find(w('vMerge')) if prop is not None else None
                        text = ' '.join(_para_text(p, None)[0] for p in tc.findall(w('p'))).strip()
                        if merge is not None and merge.get(w('val')) != 'restart':
                            origin = previous.get(col)
                            if origin is None or origin['colspan'] != span or text:
                                raise ValueError('invalid DOCX vertical table continuation')
                            origin['rowspan'] += 1
                        else:
                            origin = {'row': ri, 'column': col, 'rowspan': 1, 'colspan': span, 'text': text}
                            origins.append(origin)
                        if merge is not None:
                            active[col] = origin
                        col += span
                    previous = active
                if origins:
                    blocks.append(Block('table', rows=expanded_table(origins), cells=origins, header_rows=header_rows))
            elif el.tag in (w("sdt"),):
                content = el.find(w("sdtContent"))
                if content is not None:
                    # a Word-generated table of contents is regenerated by us
                    txt = "".join(content.itertext())
                    if re.search(r"\bcontents\b", txt[:200], re.I) and len(content.findall(".//" + w("hyperlink"))) >= 3:
                        continue
                    walk(content)
            elif el.tag == w("sectPr"):
                continue
    walk(body)
    for nid in dict.fromkeys(used_notes):        # cited twice, defined once
        if nid in notes:
            blocks.append(Block("footnote", text=notes[nid], note_id=nid))
    meta["zip"] = z
    return meta, blocks


def _para_text(p, rels) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Text of a w:p with inline emphasis, footnote refs and images."""
    out: list[str] = []; refs: list[str] = []; images: list[tuple[str, str]] = []
    def walk_inline(node):
        yield node
        if node.tag.rsplit('}', 1)[-1] not in ('oMath', 'oMathPara'):
            for item in node:
                yield from walk_inline(item)
    for r in walk_inline(p):
        if r.tag.rsplit('}', 1)[-1] in ('oMath', 'oMathPara'):
            out.append(math_text(math_record(r)))
            continue
        if r.tag == w("t"):
            out.append(r.text or "")
        elif r.tag == w("tab"):
            out.append("\t")
        elif r.tag in (w("br"), w("cr")):
            out.append(" ")
        elif r.tag == w("footnoteReference") or r.tag == w("endnoteReference"):
            nid = r.get(w("id")); refs.append(nid); out.append(f"[^{nid}]")
        elif r.tag == "{%s}blip" % A_NS and rels is not None:
            rid = r.get("{%s}embed" % R_NS)
            if rid in rels:
                images.append((rels[rid], ""))
        elif r.tag == "{%s}docPr" % WP_NS and images:
            images[-1] = (images[-1][0], r.get("descr") or r.get("name") or "")
    text = "".join(out)
    return re.sub(r"[ \t]+", " ", text).strip(), refs, images


# ===========================================================================
# DOC / ODT / RTF via LibreOffice
# ===========================================================================
def convert_with_soffice(path: Path, soffice: str | None = None) -> Path:
    exe = soffice or shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError(f"{path.name}: converting {path.suffix} needs LibreOffice (soffice) on PATH")
    out_dir = Path(tempfile.mkdtemp(prefix="pdf2md_"))
    cmd = [exe, "--headless", "--norestore", "--convert-to", "docx", "--outdir", str(out_dir), str(path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180,
                       env={"HOME": str(out_dir), "PATH": "/usr/bin:/bin:/usr/local/bin"})
    except subprocess.TimeoutExpired:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"{path.name}: LibreOffice conversion timed out after 180s")
    except subprocess.CalledProcessError as e:
        # Only TimeoutExpired was caught before, so a failing soffice reached
        # the user as a raw CalledProcessError -- with the stderr that says
        # what actually went wrong thrown away.
        detail = (e.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"{path.name}: LibreOffice conversion failed"
                           + (f" -- {detail[-1][:200]}" if detail else
                              f" (exit {e.returncode})"))
    except OSError as e:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"{path.name}: cannot run LibreOffice at {exe!r}: {e}")
    out = out_dir / (path.stem + ".docx")
    if not out.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"{path.name}: LibreOffice produced no DOCX")
    return out
