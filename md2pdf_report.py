# -*- coding: utf-8 -*-
"""md2pdf_report.py - convert EXPERIMENT_REPORT.md to a Chinese PDF.

Rules (per md-to-pdf-report skill): H2 -> TOC entry, tables -> styled Table,
bold/code inline, code fences -> monospace block, bullet lists, quotes.
Uses msyh.ttc / msyhbd.ttc. multiBuild for TOC page numbers.
"""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)

BASE = Path(r"${PROBE_ROOT}")
MD = BASE / "FINAL_REPORT_minimal-toolkit方案.md"
OUT = BASE / "deepseekv4pro最佳使用方式.pdf"

pdfmetrics.registerFont(TTFont("MSYH", r"C:\Windows\Fonts\msyh.ttc"))
pdfmetrics.registerFont(TTFont("MSYHBD", r"C:\Windows\Fonts\msyhbd.ttc"))
pdfmetrics.registerFontFamily("MSYH", normal="MSYH", bold="MSYHBD", italic="MSYH", boldItalic="MSYHBD")

ST_BODY = ParagraphStyle("body", fontName="MSYH", fontSize=9.5, leading=15, alignment=TA_LEFT)
ST_H2 = ParagraphStyle("h2", fontName="MSYHBD", fontSize=14, leading=20, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#1a3a6b"))
ST_H1 = ParagraphStyle("h1", fontName="MSYHBD", fontSize=20, leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#1a3a6b"))
ST_META = ParagraphStyle("meta", fontName="MSYH", fontSize=10, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
ST_CELL = ParagraphStyle("cell", fontName="MSYH", fontSize=8.5, leading=12)
ST_CELLH = ParagraphStyle("cellh", fontName="MSYHBD", fontSize=8.5, leading=12, textColor=colors.white)
ST_BULLET = ParagraphStyle("bullet", parent=ST_BODY, leftIndent=14, bulletIndent=4, spaceAfter=2)
ST_QUOTE = ParagraphStyle("quote", parent=ST_BODY, leftIndent=12, backColor=colors.HexColor("#eef3fa"), borderColor=colors.HexColor("#9db8d9"), borderWidth=1, borderPadding=6, spaceAfter=4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    """Apply **bold** and `code` inline markup after XML-escaping."""
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', s)
    return s


def parse_table(lines):
    rows = []
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return None, 0
    ncols = max(len(r) for r in rows)
    # skip separator row |---|---|
    data = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    if not data:
        return None, len(rows)
    tbl = Table([[Paragraph(inline(c), ST_CELLH) if i == 0 else Paragraph(inline(c), ST_CELL) for c in row] for i, row in enumerate(data)])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3fa")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl, len(rows)


class ReportDoc(BaseDocTemplate):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._toc = []

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name == "h2":
            text = fl.getPlainText()
            self._toc.append((0, text, self.page))


def build():
    text = MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    doc = ReportDoc(str(OUT), pagesize=A4,
                    leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])

    story = []
    i = 0
    title_done = False
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            # code fence: collect until closing ```, render as plain body text
            # (Courier lacks CJK glyphs -> was garbled; use body style instead)
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            story.append(Paragraph(esc("\n".join(buf)).replace("\n", "<br/>"), ST_BODY))
            story.append(Spacer(1, 6))
            continue
        if ln.startswith("|"):
            # table block
            j = i
            while j < len(lines) and (lines[j].startswith("|") or lines[j].strip() == ""):
                if lines[j].strip().startswith("|"):
                    j += 1
                else:
                    break
            tbl, _ = parse_table(lines[i:j])
            if tbl:
                story.append(tbl)
                story.append(Spacer(1, 8))
            i = j
            continue
        if ln.startswith("## "):
            story.append(Paragraph(inline(ln[3:].strip()), ST_H2))
            i += 1
            continue
        if ln.startswith("# "):
            if not title_done:
                story.append(Spacer(1, 60))
                story.append(Paragraph(inline(ln[2:].strip()), ST_H1))
                title_done = True
            i += 1
            continue
        if ln.strip() == "---":
            # md horizontal rule -> small spacer, NOT a page break (was forcing
            # one page per section)
            story.append(Spacer(1, 6))
            i += 1
            continue
        if ln.startswith("> "):
            story.append(Paragraph(inline(ln[2:].strip()), ST_QUOTE))
            i += 1
            continue
        if ln.lstrip().startswith("- ") or ln.lstrip().startswith("* "):
            txt = ln.lstrip()[2:].strip()
            story.append(Paragraph(inline(txt), ST_BULLET, bulletText="•"))
            i += 1
            continue
        if re.match(r"^\d+\.\s", ln):
            txt = re.sub(r"^\d+\.\s", "", ln)
            story.append(Paragraph(inline(txt), ST_BULLET, bulletText="•"))
            i += 1
            continue
        story.append(Paragraph(inline(ln), ST_BODY))
        i += 1

    # compact: no separate cover/TOC pages - title block then straight into body
    cover = []
    cover.append(Spacer(1, 10))
    cover.append(Paragraph("DeepSeek V4 Pro 最佳使用方式", ST_H1))
    cover.append(Paragraph("minimal + toolkit 方案定稿 ｜ 2026-08-15", ST_META))
    cover.append(Spacer(1, 6))
    doc.multiBuild(cover + story)


def verify(pdf=OUT):
    import fitz
    d = fitz.open(str(pdf))
    print(f"pages={len(d)}")
    t0 = d[0].get_text()[:120].replace("\n", " | ")
    print(f"cover: {t0}")
    last = d[-1].get_text()[-120:].replace("\n", " | ")
    print(f"last: {last}")
    # find TOC page
    for p in d:
        if "目 录" in p.get_text():
            print(f"TOC on page {p.number + 1}")
            break


if __name__ == "__main__":
    build()
    verify()
    print("OK ->", OUT)
