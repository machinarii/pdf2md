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

import html
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


GENERATOR_NAMES = re.compile(r"^(python-docx|libreoffice|openoffice|microsoft (office )?(word|user)|"
                             r"unknown( title| author)?|untitled|calibre|pandoc|author|user|admin|owner)$", re.I)


def css_style_map(css: str) -> dict[str, dict]:
    """.paraN { font-size: 18pt; font-weight: bold } -> {'paraN': {size, bold}}.
    Sizes in pt, px (x0.75), em/% (relative to 12pt)."""
    out: dict[str, dict] = {}
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
        selectors, body = m.group(1), m.group(2)
        size = None; bold = None
        ms = re.search(r"font-size\s*:\s*([\d.]+)\s*(pt|px|em|%|rem)?", body)
        if ms:
            v = float(ms.group(1)); u = ms.group(2) or "pt"
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


class _HtmlBlocks(HTMLParser):
    """Linear pass over an XHTML chapter, emitting Blocks. Inline emphasis is
    kept as Markdown; footnote references become [^id] markers."""

    def __init__(self, style_map: dict | None = None):
        super().__init__(convert_charrefs=True)
        self.style_map = style_map or {}
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
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        types = (a.get("epub:type") or a.get("role") or "").lower()
        cls = (a.get("class") or "").lower()
        if tag in ("script", "style", "nav") or "toc" in types:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "title":
            self.in_title = True; return
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
        elif tag == "li" and self.note:
            # pandoc / EPUB 3: <section role="doc-endnotes"><ol><li id="fn1"><p>...
            if a.get("id"):
                self.note[-1] = a.get("id")
            self._start("footnote", note_id=self.note[-1])
        elif tag == "li":
            self._start("list_item", level=self.list_depth, ordered=bool(self.list_ordered and self.list_ordered[-1]))
        elif tag == "blockquote":
            self._flush(); self.stack.append("quote")
        elif tag == "pre":
            self._start("code"); self.in_pre += 1
        elif tag in ("figcaption", "caption"):
            self._start("caption")
        elif tag == "table":
            self._flush(); self.in_table += 1; self.rows = []
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "img":
            self._flush()
            self.blocks.append(Block("image", text=a.get("alt", ""), src=a.get("src", "")))
        elif tag == "hr":
            if not self.note:
                self._start("hr")
        elif tag == "br":
            self.buf.append(" ")
        elif tag == "aside" and ("footnote" in types or "footnote" in cls or "note" in types):
            self._flush(); self.note.append(a.get("id", ""))
        elif tag in ("div", "section", "article", "header", "footer", "dt", "dd"):
            self._flush()
            if "footnote" in cls or "footnote" in types or "endnote" in types:
                self.note.append(a.get("id", ""))
        elif tag == "a" and ("backlink" in types or "footnote-back" in cls or "back" in cls):
            self.suppress += 1; self.stack.append("backlink")
        elif tag == "a" and ("noteref" in types or "noteref" in cls or "footnote-ref" in cls or "footnote" in cls):
            href = a.get("href", "")
            nid = href.split("#")[-1] if "#" in href else href
            self.buf.append(f"[^{nid}]")
            self.suppress += 1; self.stack.append("noteref")
        elif tag in ("em", "i"):
            self.buf.append("*"); self.stack.append("em")
        elif tag in ("strong", "b"):
            self.buf.append("**"); self.stack.append("strong")
        elif tag == "code" and not self.in_pre:
            self.buf.append("`"); self.stack.append("code")
        elif tag == "sup":
            self.stack.append("sup")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav"):
            self.skip = max(0, self.skip - 1); return
        if self.skip:
            if tag in ("section", "div", "article"):
                pass
            return
        if tag == "title":
            self.in_title = False; return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "li", "figcaption", "caption", "hr"):
            self._flush()
        elif tag == "p" and not (self.note and self.cur is not None and self.cur.kind == "footnote"):
            self._flush()
        elif tag in ("ul", "ol"):
            self._flush(); self.list_depth = max(0, self.list_depth - 1)
            if self.list_ordered: self.list_ordered.pop()
        elif tag == "blockquote":
            self._flush()
            if "quote" in self.stack: self.stack.remove("quote")
        elif tag == "pre":
            self._flush(); self.in_pre = max(0, self.in_pre - 1)
        elif tag in ("td", "th"):
            if self.cell is not None and self.rows:
                self.rows[-1].append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "table":
            self.in_table = max(0, self.in_table - 1)
            rows = [r for r in self.rows if any(c.strip() for c in r)]
            if rows:
                self.blocks.append(Block("table", rows=rows))
            self.rows = []
        elif tag == "aside" and self.note:
            self._flush(); self.note.pop()
        elif tag in ("div", "section", "article", "header", "footer", "dt", "dd"):
            self._flush()
            if self.note and tag == "div":
                pass
        elif tag == "a" and self.stack and self.stack[-1] in ("noteref", "backlink"):
            self.stack.pop(); self.suppress = max(0, self.suppress - 1)
        elif tag in ("em", "i") and "em" in self.stack:
            self.buf.append("*"); self.stack.remove("em")
        elif tag in ("strong", "b") and "strong" in self.stack:
            self.buf.append("**"); self.stack.remove("strong")
        elif tag == "code" and "code" in self.stack:
            self.buf.append("`"); self.stack.remove("code")
        elif tag == "sup" and "sup" in self.stack:
            self.stack.remove("sup")

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


def html_to_blocks(markup: str, style_map: dict | None = None) -> tuple[str, list[Block]]:
    p = _HtmlBlocks(style_map)
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
    z = zipfile.ZipFile(path)
    container = ET.fromstring(z.read("META-INF/container.xml"))
    opf_path = container.find(".//c:rootfile", NS).get("full-path")
    opf_dir = str(Path(opf_path).parent)
    opf = ET.fromstring(z.read(opf_path))

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
            style_map.update(css_style_map(z.read(zpath(href)).decode("utf-8", "replace")))

    # ---- contents truth: nav.xhtml (EPUB 3) or toc.ncx (EPUB 2)
    toc: list[tuple[int, str, str]] = []          # (depth, title, href)
    if nav_href and zpath(nav_href) in z.namelist():
        toc = _parse_nav(z.read(zpath(nav_href)).decode("utf-8", "replace"))
    elif ncx_id in items and zpath(items[ncx_id][0]) in z.namelist():
        ncx = ET.fromstring(z.read(zpath(items[ncx_id][0])))
        def walk(np, depth):
            for pt in np.findall("ncx:navPoint", NS):
                label = "".join(pt.find("ncx:navLabel/ncx:text", NS).itertext()).strip()
                src = pt.find("ncx:content", NS).get("src", "")
                toc.append((depth, label, src)); walk(pt, depth + 1)
        walk(ncx.find("ncx:navMap", NS), 1)
    meta["toc"] = toc
    title_by_file: dict[str, tuple[int, str]] = {}
    for depth, label, href in toc:
        f = unquote(href.split("#")[0])
        title_by_file.setdefault(f, (depth, label))

    # ---- chapters in spine order
    blocks: list[Block] = []
    for href in spine:
        zp = zpath(href)
        if zp not in z.namelist():
            continue
        title, chapter = html_to_blocks(z.read(zp).decode("utf-8", "replace"), style_map)
        idx = spine.index(href) + 1
        for b in chapter:
            if b.note_id:
                b.note_id = f"{idx}-{b.note_id}"
            if "[^" in b.text:
                b.text = re.sub(r"\[\^([^\]]+)\]", lambda m: f"[^{idx}-{m.group(1)}]", b.text)
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
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    meta = {"title": "", "authors": [], "publisher": None, "date": None, "year": None,
            "isbn": [], "language": None, "toc": [], "format": "docx"}
    if "docProps/core.xml" in names:
        core = ET.fromstring(z.read("docProps/core.xml"))
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
        st = ET.fromstring(z.read("word/styles.xml"))
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
            fn = ET.fromstring(z.read(part))
            tag = "footnote" if "footnotes" in part else "endnote"
            for n in fn.findall(w(tag)):
                nid = n.get(w("id"))
                if nid in ("-1", "0"):
                    continue
                notes[nid] = " ".join(_para_text(p, None)[0] for p in n.findall(".//" + w("p"))).strip()

    # ---- relationships (images)
    rels: dict[str, str] = {}
    if "word/_rels/document.xml.rels" in names:
        rel = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        for r in rel:
            rels[r.get("Id")] = "word/" + r.get("Target") if not r.get("Target", "").startswith("/") else r.get("Target").lstrip("/")

    # ---- body
    doc = ET.fromstring(z.read("word/document.xml"))
    body = doc.find(w("body"))
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
                rows = []
                for tr in el.findall(w("tr")):
                    cells = []
                    for tc in tr.findall(w("tc")):
                        cells.append(" ".join(_para_text(p, None)[0] for p in tc.findall(w("p"))).strip())
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append(Block("table", rows=rows))
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
    for nid in used_notes:
        if nid in notes:
            blocks.append(Block("footnote", text=notes[nid], note_id=nid))
    meta["zip"] = z
    return meta, blocks


def _para_text(p, rels) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Text of a w:p with inline emphasis, footnote refs and images."""
    out: list[str] = []; refs: list[str] = []; images: list[tuple[str, str]] = []
    for r in p.iter():
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
        raise RuntimeError(f"{path.name}: LibreOffice conversion timed out")
    out = out_dir / (path.stem + ".docx")
    if not out.exists():
        raise RuntimeError(f"{path.name}: LibreOffice produced no DOCX")
    return out
