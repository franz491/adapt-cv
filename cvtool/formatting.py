import re


def normalize_markdown(text):
    """Remove model wrappers and normalize CV Markdown conservatively."""
    text = text.strip().replace("\r\n", "\n")
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text, flags=re.I)
        text = re.sub(r"\n```\s*$", "", text)
    lines = []
    blank = False
    for raw in text.splitlines():
        line = raw.rstrip()
        line = re.sub(r"^\s*[•●▪]\s+", "- ", line)
        line = re.sub(r"^\s*[-*]\s+", "- ", line)
        if not line.strip():
            if lines and not blank:
                lines.append("")
            blank = True
            continue
        if line.startswith("#"):
            line = re.sub(r"^(#{1,6})\s*", r"\1 ", line)
        lines.append(line)
        blank = False
    return "\n".join(lines).strip() + "\n"

