import re
from html import escape, unescape
from pathlib import Path


def _inline(text):
    text = escape(text)
    def link(match):
        label, displayed_url = match.group(1), match.group(2).strip()
        url = unescape(displayed_url)
        lowered = url.casefold()
        if lowered.startswith(("http://", "https://", "mailto:")):
            href = displayed_url
        elif re.fullmatch(r"(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:[/#?].*)?", url):
            href = "https://" + displayed_url
        else:
            return label
        return f'<link href="{href}" color="#1c527a"><u>{label}</u></link>'
    text = re.sub(r"\[([^]]+)]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"[*_`]+", "", text)
    return text


def render_pdf(markdown, destination):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF export requires reportlab: pip install -r requirements.txt") from exc

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("CVBody", parent=styles["BodyText"], fontName="Helvetica",
                          fontSize=9.2, leading=12, spaceAfter=2.5 * mm,
                          textColor=colors.HexColor("#20242a"))
    title = ParagraphStyle("CVTitle", parent=body, fontName="Helvetica-Bold",
                           fontSize=22, leading=25, alignment=TA_CENTER,
                           spaceAfter=2 * mm, textColor=colors.HexColor("#182b49"))
    section = ParagraphStyle("CVSection", parent=body, fontName="Helvetica-Bold",
                             fontSize=12, leading=15, spaceBefore=4 * mm,
                             spaceAfter=1.5 * mm, textColor=colors.HexColor("#1c527a"),
                             borderWidth=0, borderPadding=0)
    subhead = ParagraphStyle("CVSubhead", parent=body, fontName="Helvetica-Bold",
                             fontSize=10, leading=13, spaceBefore=1.5 * mm,
                             spaceAfter=1 * mm)
    contact = ParagraphStyle("CVContact", parent=body, fontSize=8.5, leading=11,
                             alignment=TA_CENTER, textColor=colors.HexColor("#4a5560"))
    bullet = ParagraphStyle("CVBullet", parent=body, leftIndent=4 * mm,
                            firstLineIndent=-3 * mm, bulletIndent=0,
                            spaceAfter=1.2 * mm)
    story = []
    first_content = True
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        safe = _inline(line)
        if line.startswith("# "):
            story.append(Paragraph(_inline(line[2:]), title)); first_content = False
        elif line.startswith("## "):
            story.append(Paragraph(_inline(line[3:]).upper(), section))
        elif line.startswith("### "):
            story.append(Paragraph(_inline(line[4:]), subhead))
        elif line.startswith("- "):
            story.append(Paragraph(_inline(line[2:]), bullet, bulletText="•"))
        else:
            story.append(Paragraph(safe, contact if not first_content and len(story) == 1 else body))
            first_content = False
    doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=15 * mm,
                            leftMargin=15 * mm, topMargin=13 * mm, bottomMargin=13 * mm,
                            title="Curriculum Vitae", author="cv-editor")
    doc.build(story)
