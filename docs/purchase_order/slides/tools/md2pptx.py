#!/usr/bin/env python3
"""Marp の原稿（report.md）から、編集できる PPTX を python-pptx で直接組み立てる。

Marp の ``--pptx`` は各ページを画像にするので編集できない。``--pptx-editable`` は LibreOffice を
経由するため、表の行の高さやインラインコードの位置が崩れる。そこで原稿を最小限の Markdown として
読み、テキストボックス・表・図形だけのネイティブな PPTX を作る。色と文字の大きさは report.md の
``style`` と同じ値にしてある（px で持ち、1px = 0.75pt = 9525 EMU で換算する）。

対応する記法
  front matter の title / footer / paginate、``---`` によるページ区切り、
  ``<!-- _class: title|section -->``・``<!-- _paginate: false -->``・``<!-- _footer: '' -->``、
  ``#`` / ``##`` / ``###``、段落、箇条書き（``-`` ``*`` ``1.``。2 スペースで入れ子）、表、コードブロック、
  引用（``>``）、画像（``![w:600](path)``）、2 段組み（``<div class="columns">`` の中の ``<div>``）、
  上記以外の HTML コメント（発表者ノートとして PPTX のノートに入れる）。

  python tools/md2pptx.py report.md -o dist/report.pptx
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

# ---- 見た目（report.md の style と揃える） ---------------------------------------------
SLIDE_W, SLIDE_H = 1280, 720
MARGIN_X = 64
TITLE_TOP = 32
CONTENT_BOTTOM = 650
FOOTER_Y = 676
BLOCK_GAP = 12
COLUMN_GAP = 32

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
ACCENT = RGBColor(0xC2, 0x41, 0x0C)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x6B, 0x72, 0x80)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
CODE_BG = RGBColor(0xF3, 0xF4, 0xF6)
LINK = RGBColor(0x1D, 0x4E, 0xD8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SUBTLE_ON_NAVY = RGBColor(0xCB, 0xD5, 0xE1)

FONT = "Yu Gothic"
FONT_MONO = "Consolas"

SIZE = {"body": 24, "h2": 36, "h3": 26, "table": 19, "code": 17, "quote": 22,
        "title": 52, "subtitle": 28, "meta": 20, "section": 44, "footer": 14}
LINE = {"body": 1.4, "h2": 1.25, "h3": 1.3, "table": 1.3, "code": 1.35, "quote": 1.4}
MIN_SCALE = 0.6


def emu(px: float) -> Emu:
    return Emu(int(round(px * 9525)))


def pt(px: float) -> Pt:
    return Pt(px * 0.75)


# ---- Markdown の読み取り -------------------------------------------------------------
@dataclass
class Item:
    text: str
    level: int
    marker: str  # "•" または "1." など


@dataclass
class Block:
    kind: str  # heading / para / list / table / code / quote / image / columns
    text: str = ""
    level: int = 0
    items: list[Item] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    align: list[str] = field(default_factory=list)
    alt: str = ""
    columns: list[list["Block"]] = field(default_factory=list)


@dataclass
class Slide:
    cls: set[str]
    blocks: list[Block]
    notes: str
    paginate: bool
    footer: str


DIRECTIVE_RE = re.compile(r"^\s*(_?[a-zA-Z]+)\s*:\s*(.*?)\s*$")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def split_front_matter(text: str) -> tuple[dict, str]:
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            for line in lines[1:i]:
                m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip().strip("'\"")
            return meta, "\n".join(lines[i + 1:])
    return meta, text


def split_slides(body: str) -> list[str]:
    slides, cur, fenced = [], [], False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
        if not fenced and line.strip() == "---":
            slides.append("\n".join(cur))
            cur = []
        else:
            cur.append(line)
    slides.append("\n".join(cur))
    return [s for s in slides if s.strip()]


def is_wide(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def join_lines(lines: list[str]) -> str:
    out = ""
    for line in (l.strip() for l in lines):
        if out and line and not (is_wide(out[-1]) or is_wide(line[0])):
            out += " "
        out += line
    return out


def split_row(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def parse_columns(lines: list[str], i: int) -> tuple[Block, int]:
    """``<div class="columns">`` の次の行から読み、2 段組みのブロックと次の行の位置を返す。"""
    columns, cur, depth = [], [], 0
    while i < len(lines):
        t = lines[i].strip()
        if t.startswith("<div"):
            if depth == 0:
                cur = []
            else:
                cur.append(lines[i])
            depth += 1
        elif t == "</div>":
            if depth == 0:
                return Block("columns", columns=columns), i + 1
            depth -= 1
            if depth == 0:
                columns.append(parse_blocks(cur))
            else:
                cur.append(lines[i])
        elif depth > 0:
            cur.append(lines[i])
        i += 1
    return Block("columns", columns=columns), i


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i, n = 0, len(lines)
    para: list[str] = []

    def flush_para():
        if para:
            blocks.append(Block("para", text=join_lines(para)))
            para.clear()

    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            flush_para()
            i += 1
            continue
        fence = FENCE_RE.match(line)
        if fence:
            flush_para()
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence.group(1)):
                code.append(lines[i])
                i += 1
            blocks.append(Block("code", text="\n".join(code)))
            i += 1
            continue
        if s == '<div class="columns">':
            flush_para()
            block, i = parse_columns(lines, i + 1)
            blocks.append(block)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            blocks.append(Block("heading", text=m.group(2), level=len(m.group(1))))
            i += 1
            continue
        if s.startswith("|"):
            flush_para()
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            align = []
            if len(rows) >= 2 and all(re.fullmatch(r":?-{2,}:?", c) for c in rows[1]):
                for c in rows[1]:
                    align.append("center" if c.startswith(":") and c.endswith(":")
                                 else "right" if c.endswith(":") else "left")
                rows.pop(1)
            blocks.append(Block("table", rows=rows, align=align))
            continue
        if s.startswith(">"):
            flush_para()
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(Block("quote", text=join_lines(quote)))
            continue
        m = IMAGE_RE.match(s)
        if m:
            flush_para()
            blocks.append(Block("image", alt=m.group(1), text=m.group(2)))
            i += 1
            continue
        if LIST_RE.match(line):
            flush_para()
            items: list[Item] = []
            while i < n:
                m = LIST_RE.match(lines[i])
                if m:
                    marker = m.group(2)
                    items.append(Item(m.group(3).strip(), len(m.group(1).expandtabs(2)) // 2,
                                      "•" if marker in "-*+" else marker.rstrip(".)") + "."))
                elif lines[i].strip() and lines[i].startswith((" ", "\t")) and items:
                    items[-1].text = join_lines([items[-1].text, lines[i]])
                else:
                    break
                i += 1
            blocks.append(Block("list", items=items))
            continue
        if s.startswith("<") and not s.startswith(("<br", "<strong", "<span", "<a ")):
            flush_para()  # 2 段組み以外の HTML の行は描かない
            i += 1
            continue
        para.append(line)
        i += 1
    flush_para()
    return blocks


def parse_slide(raw: str, meta: dict) -> Slide:
    cls: set[str] = set()
    paginate = meta.get("paginate", "false").lower() == "true"
    footer = meta.get("footer", "")
    notes: list[str] = []

    def take_comment(m: re.Match) -> str:
        nonlocal paginate, footer
        body = m.group(1).strip()
        d = DIRECTIVE_RE.match(body)
        if d and "\n" not in body:
            key, value = d.group(1), d.group(2).strip("'\"")
            if key in ("_class", "class"):
                cls.update(value.split())
                return ""
            if key in ("_paginate", "paginate"):
                paginate = value.lower() == "true"
                return ""
            if key in ("_footer", "footer"):
                footer = value
                return ""
        notes.append(body)
        return ""

    text = COMMENT_RE.sub(take_comment, raw)
    return Slide(cls, parse_blocks(text.splitlines()), "\n\n".join(notes), paginate, footer)


# ---- 文字の幅と行数の見積もり --------------------------------------------------------------
INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|<br\s*/?>")


def plain(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def char_w(ch: str) -> float:
    if ch == " ":
        return 0.3
    if is_wide(ch) or (unicodedata.east_asian_width(ch) == "A" and ord(ch) > 0x2000):
        return 1.0
    return 0.58


def count_lines(text: str, size: float, width: float, bold: bool = False) -> int:
    factor = size * (1.05 if bold else 1.0)
    total = 0
    for seg in plain(text).split("\n"):
        lines, cur = 1, 0.0
        for tok in re.findall(r"[A-Za-z0-9_\-./:%$@#+=,'()]+|\s+|.", seg):
            w = sum(char_w(c) for c in tok) * factor
            if cur + w > width and cur > 0:
                lines += 1
                cur = 0.0 if tok.isspace() else w
            else:
                cur += w
        total += lines
    return total


# ---- PPTX の部品 -------------------------------------------------------------------------
def style_run(run, size: float, color: RGBColor, bold=False, mono=False) -> None:
    f = run.font
    f.size = pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = FONT_MONO if mono else FONT
    # 和文のフォント（a:ea）も指定しないと、PowerPoint が和文だけ既定のフォントで描く
    rpr = run._r.get_or_add_rPr()
    ea = etree.SubElement(rpr, qn("a:ea"))
    ea.set("typeface", FONT)
    rpr.find(qn("a:latin")).addnext(ea)


def _add_plain(p, text: str, size: float, color: RGBColor, bold: bool) -> None:
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    if text:
        run = p.add_run()
        run.text = text
        style_run(run, size, color, bold)


def add_inline(p, text: str, size: float, color: RGBColor, bold=False) -> None:
    on_dark = color in (WHITE, SUBTLE_ON_NAVY)
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            _add_plain(p, text[pos:m.start()], size, color, bold)
        if m.group(1) is not None:
            _add_plain(p, m.group(1), size, color if on_dark else ACCENT, True)
        elif m.group(2) is not None:
            run = p.add_run()
            run.text = m.group(2)
            style_run(run, size * 0.92, color if on_dark else NAVY, bold, mono=True)
        elif m.group(3) is not None:
            run = p.add_run()
            run.text = plain(m.group(3))
            style_run(run, size, color if on_dark else LINK, bold)
            run.hyperlink.address = m.group(4)
        else:
            p.add_line_break()
        pos = m.end()
    if pos < len(text):
        _add_plain(p, text[pos:], size, color, bold)


def set_spacing(p, size: float, line: float, after: float = 0.0) -> None:
    # 行間は「固定値」にする。游ゴシックは「1 行」の行間が大きく、見積もりとずれるため
    p.line_spacing = pt(size * line)
    p.space_before = Pt(0)
    p.space_after = pt(after)


def set_hanging(p, left: float, hang: float) -> None:
    ppr = p._p.get_or_add_pPr()
    ppr.set("marL", str(int(emu(left))))
    ppr.set("indent", str(-int(emu(hang))))


def new_textbox(sl, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = sl.shapes.add_textbox(emu(x), emu(y), emu(w), emu(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tb, tf


def add_rect(sl, x, y, w, h, fill: RGBColor):
    shape = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(x), emu(y), emu(w), emu(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


# ---- 配置（draw=False で高さだけ測る） -------------------------------------------------------
class Renderer:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def blocks(self, sl, blocks: list[Block], x, y, w, s, draw) -> float:
        top = y
        for i, b in enumerate(blocks):
            if i:
                y += BLOCK_GAP * s
            y += getattr(self, "_" + b.kind)(sl, b, x, y, w, s, draw)
        return y - top

    def _heading(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["h3"] * s, LINE["h3"]
        h = count_lines(b.text, size, w, bold=True) * size * lh
        if draw:
            _, tf = new_textbox(sl, x, y, w, h)
            set_spacing(tf.paragraphs[0], size, lh)
            add_inline(tf.paragraphs[0], b.text, size, NAVY, bold=True)
        return h

    def _para(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["body"] * s, LINE["body"]
        h = count_lines(b.text, size, w) * size * lh
        if draw:
            _, tf = new_textbox(sl, x, y, w, h)
            set_spacing(tf.paragraphs[0], size, lh)
            add_inline(tf.paragraphs[0], b.text, size, INK)
        return h

    def _list(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["body"] * s, LINE["body"]
        gap = 4 * s
        sizes = [size * (0.92 if it.level else 1.0) for it in b.items]
        heights = [count_lines(it.text, sz, w - (it.level + 1) * 1.2 * size) * sz * lh
                   for it, sz in zip(b.items, sizes)]
        h = sum(heights) + gap * (len(heights) - 1)
        if draw:
            _, tf = new_textbox(sl, x, y, w, h)
            for k, (it, sz) in enumerate(zip(b.items, sizes)):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                hang = 1.2 * size
                set_spacing(p, sz, lh, after=gap if k < len(b.items) - 1 else 0)
                set_hanging(p, (it.level + 1) * hang, hang)
                ordered = it.marker != "•"
                run = p.add_run()
                run.text = (it.marker if ordered else ("•", "–", "·")[min(it.level, 2)]) + "\t"
                style_run(run, sz, NAVY, bold=ordered)
                add_inline(p, it.text, sz, INK)
        return h

    def _quote(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["quote"] * s, LINE["quote"]
        pad_x, pad_y, bar = 18 * s, 12 * s, 6 * s
        h = count_lines(b.text, size, w - bar - pad_x * 2) * size * lh + pad_y * 2
        if draw:
            box = add_rect(sl, x, y, w, h, LIGHT)
            add_rect(sl, x, y, bar, h, NAVY)
            tf = box.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = emu(bar + pad_x)
            tf.margin_right = emu(pad_x)
            tf.margin_top = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            set_spacing(p, size, lh)
            add_inline(p, b.text, size, INK)
        return h

    def _code(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["code"] * s, LINE["code"]
        pad_x, pad_y = 16 * s, 12 * s
        lines = b.text.split("\n")
        n = sum(count_lines(l or " ", size * 1.03, w - pad_x * 2) for l in lines)
        h = n * size * lh + pad_y * 2
        if draw:
            box = add_rect(sl, x, y, w, h, CODE_BG)
            tf = box.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.TOP
            tf.margin_left = tf.margin_right = emu(pad_x)
            tf.margin_top = tf.margin_bottom = emu(pad_y)
            for k, line in enumerate(lines):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                set_spacing(p, size, lh)
                run = p.add_run()
                run.text = line
                style_run(run, size, INK, mono=True)
        return h

    def _table(self, sl, b, x, y, w, s, draw):
        size, lh = SIZE["table"] * s, LINE["table"]
        pad_x, pad_y = 10 * s, 6 * s
        ncols = max(len(r) for r in b.rows)
        rows = [r + [""] * (ncols - len(r)) for r in b.rows]
        natural = [max(sum(char_w(c) for c in plain(r[j])) * size for r in rows) + pad_x * 2
                   for j in range(ncols)]
        weights = [min(max(v, 70 * s), 520 * s) for v in natural]
        widths = [w * v / sum(weights) for v in weights]
        heights = []
        for ri, r in enumerate(rows):
            n = max(count_lines(c, size, widths[j] - pad_x * 2, bold=ri == 0) for j, c in enumerate(r))
            heights.append(n * size * lh + pad_y * 2)
        h = sum(heights)
        if draw:
            tbl = sl.shapes.add_table(len(rows), ncols, emu(x), emu(y), emu(w), emu(h)).table
            tbl.first_row = True
            tbl.horz_banding = False
            for j, cw in enumerate(widths):
                tbl.columns[j].width = emu(cw)
            for ri, r in enumerate(rows):
                tbl.rows[ri].height = emu(heights[ri])
                for j, text in enumerate(r):
                    cell = tbl.cell(ri, j)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = NAVY if ri == 0 else (LIGHT if ri % 2 == 1 else WHITE)
                    cell.margin_left = cell.margin_right = emu(pad_x)
                    cell.margin_top = cell.margin_bottom = emu(pad_y)
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    cell.text_frame.word_wrap = True
                    p = cell.text_frame.paragraphs[0]
                    align = b.align[j] if j < len(b.align) else "left"
                    p.alignment = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}.get(align, PP_ALIGN.LEFT)
                    set_spacing(p, size, lh)
                    add_inline(p, text, size, WHITE if ri == 0 else INK, bold=ri == 0)
        return h

    def _image(self, sl, b, x, y, w, s, draw):
        path = (self.base_dir / b.text).resolve()
        if not path.exists():
            h = 160 * s
            if draw:
                box = add_rect(sl, x, y, w, h, LIGHT)
                box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = box.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                add_inline(p, f"画像が見つかりません: {b.text}", SIZE["meta"] * s, MUTED)
                print(f"  [!] 画像が見つかりません: {b.text}", file=sys.stderr)
            return h
        from PIL import Image

        with Image.open(path) as im:
            nat_w, nat_h = im.size
        want_w = re.search(r"\bw(?:idth)?:(\d+)", b.alt)
        want_h = re.search(r"\bh(?:eight)?:(\d+)", b.alt)
        if want_w:
            iw = float(want_w.group(1))
            ih = iw * nat_h / nat_w
        elif want_h:
            ih = float(want_h.group(1))
            iw = ih * nat_w / nat_h
        else:
            iw, ih = float(nat_w), float(nat_h)
        iw, ih = iw * s, ih * s
        if iw > w:
            iw, ih = w, ih * w / iw
        if draw:
            sl.shapes.add_picture(str(path), emu(x + (w - iw) / 2), emu(y), emu(iw), emu(ih))
        return ih

    def _columns(self, sl, b, x, y, w, s, draw):
        n = max(len(b.columns), 1)
        cw = (w - COLUMN_GAP * (n - 1)) / n
        return max((self.blocks(sl, col, x + k * (cw + COLUMN_GAP), y, cw, s, draw)
                    for k, col in enumerate(b.columns)), default=0)


# ---- ページの種類ごとの組み立て ----------------------------------------------------------------
def add_footer(sl, slide: Slide, number: int) -> None:
    color = SUBTLE_ON_NAVY if "title" in slide.cls else MUTED
    if slide.footer:
        _, tf = new_textbox(sl, MARGIN_X, FOOTER_Y, 900, 24, MSO_ANCHOR.MIDDLE)
        add_inline(tf.paragraphs[0], slide.footer, SIZE["footer"], color)
    if slide.paginate:
        _, tf = new_textbox(sl, SLIDE_W - MARGIN_X - 120, FOOTER_Y, 120, 24, MSO_ANCHOR.MIDDLE)
        tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
        add_inline(tf.paragraphs[0], str(number), SIZE["footer"], color)


def set_background(sl, color: RGBColor) -> None:
    sl.background.fill.solid()
    sl.background.fill.fore_color.rgb = color


def take_heading(blocks: list[Block], levels: tuple[int, ...]) -> tuple[Block | None, list[Block]]:
    for i, b in enumerate(blocks):
        if b.kind == "heading" and b.level in levels:
            return b, blocks[:i] + blocks[i + 1:]
    return None, blocks


def build_title(sl, slide: Slide) -> None:
    set_background(sl, NAVY)
    x, w = 96, SLIDE_W - 96 * 2
    h1, rest = take_heading(slide.blocks, (1,))
    sub, rest = take_heading(rest, (2,))
    y = 200
    add_rect(sl, x, y, 120, 8, ACCENT)
    y += 32
    if h1:
        size = SIZE["title"]
        h = count_lines(h1.text, size, w, bold=True) * size * 1.25
        _, tf = new_textbox(sl, x, y, w, h)
        set_spacing(tf.paragraphs[0], size, 1.25)
        add_inline(tf.paragraphs[0], h1.text, size, WHITE, bold=True)
        y += h + 20
    if sub:
        size = SIZE["subtitle"]
        h = count_lines(sub.text, size, w) * size * 1.4
        _, tf = new_textbox(sl, x, y, w, h)
        set_spacing(tf.paragraphs[0], size, 1.4)
        add_inline(tf.paragraphs[0], sub.text, size, SUBTLE_ON_NAVY)
    texts = [b.text for b in rest if b.kind == "para"]
    if texts:
        size = SIZE["meta"]
        _, tf = new_textbox(sl, x, 520, w, 130)
        for k, t in enumerate(texts):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            set_spacing(p, size, 1.5)
            add_inline(p, t, size, SUBTLE_ON_NAVY)


def build_section(sl, slide: Slide, renderer: Renderer) -> None:
    set_background(sl, LIGHT)
    x, w = MARGIN_X + 34, SLIDE_W - MARGIN_X * 2 - 34
    head, rest = take_heading(slide.blocks, (1, 2))
    size = SIZE["section"]
    h = count_lines(head.text if head else "", size, w, bold=True) * size * 1.3
    rest_h = renderer.blocks(sl, rest, x, 0, w, 1.0, False) + 24 if rest else 0
    y = (SLIDE_H - h - rest_h) / 2
    add_rect(sl, MARGIN_X, y, 10, h, ACCENT)
    if head:
        _, tf = new_textbox(sl, x, y, w, h, MSO_ANCHOR.MIDDLE)
        set_spacing(tf.paragraphs[0], size, 1.3)
        add_inline(tf.paragraphs[0], head.text, size, NAVY, bold=True)
    if rest:
        renderer.blocks(sl, rest, x, y + h + 24, w, 1.0, True)


def build_content(sl, slide: Slide, renderer: Renderer) -> None:
    w = SLIDE_W - MARGIN_X * 2
    head, rest = take_heading(slide.blocks, (1, 2))
    y = TITLE_TOP
    if head:
        size, lh = SIZE["h2"], LINE["h2"]
        h = count_lines(head.text, size, w, bold=True) * size * lh
        _, tf = new_textbox(sl, MARGIN_X, y, w, h)
        set_spacing(tf.paragraphs[0], size, lh)
        add_inline(tf.paragraphs[0], head.text, size, NAVY, bold=True)
        y += h + 10
        add_rect(sl, MARGIN_X, y, w, 3, NAVY)
        y += 3 + 20
    # 収まらないときは、全体の文字と画像を同じ比率で縮める（MIN_SCALE まで）
    avail = CONTENT_BOTTOM - y
    s = 1.0
    need = renderer.blocks(sl, rest, MARGIN_X, y, w, s, False)
    while need > avail and s > MIN_SCALE:
        s = max(MIN_SCALE, s * avail / need * 0.98)
        need = renderer.blocks(sl, rest, MARGIN_X, y, w, s, False)
    if need > avail:
        title = head.text if head else "(見出しなし)"
        print(f"  [!] 「{title}」が下端を {need - avail:.0f}px 越えています。内容を減らしてください",
              file=sys.stderr)
    renderer.blocks(sl, rest, MARGIN_X, y, w, s, True)


def build(deck: Path, out: Path) -> int:
    meta, body = split_front_matter(deck.read_text(encoding="utf-8"))
    slides = [parse_slide(raw, meta) for raw in split_slides(body)]
    prs = Presentation()
    prs.slide_width, prs.slide_height = emu(SLIDE_W), emu(SLIDE_H)
    if meta.get("title"):
        prs.core_properties.title = meta["title"]
    blank = prs.slide_layouts[6]
    renderer = Renderer(deck.parent)
    for number, slide in enumerate(slides, start=1):
        sl = prs.slides.add_slide(blank)
        if "title" in slide.cls:
            build_title(sl, slide)
        elif "section" in slide.cls:
            build_section(sl, slide, renderer)
        else:
            build_content(sl, slide, renderer)
        add_footer(sl, slide, number)
        if slide.notes:
            sl.notes_slide.notes_text_frame.text = slide.notes
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print(f"  pptx: {out}（{len(slides)} 枚）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Marp の原稿から編集できる PPTX を作る")
    ap.add_argument("deck", type=Path, help="Marp の原稿（.md）")
    ap.add_argument("-o", "--output", type=Path, required=True, help="出力する .pptx")
    args = ap.parse_args()
    return build(args.deck, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
