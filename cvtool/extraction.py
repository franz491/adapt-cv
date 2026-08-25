import copy
import json
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def read_previous_cv(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            result = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                    text=True, capture_output=True, check=True)
            return result.stdout
        except FileNotFoundError as exc:
            raise RuntimeError("Reading PDF CVs requires the pdftotext command") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Could not read {path}: {exc.stderr.strip()}") from exc
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        return "\n".join(node.text for node in root.iter() if node.tag.endswith("}t") and node.text)
    return path.read_text(encoding="utf-8")


def parse_json_response(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model did not return valid extraction JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Model extraction response must be a JSON object")
    return value


def _append_unique(target, values):
    if not isinstance(values, list):
        return
    existing = {json.dumps(item, sort_keys=True, default=str).casefold() for item in target}
    for item in values:
        key = json.dumps(item, sort_keys=True, default=str).casefold()
        if key not in existing:
            target.append(item); existing.add(key)


def merge_discoveries(data, additions):
    """Add discoveries without replacing canonical values."""
    merged = copy.deepcopy(data)
    person = merged.setdefault("person", {})
    for key, value in additions.get("person", {}).items():
        if key not in person or person[key] in (None, "", []):
            person[key] = value
    for key in ("summary_facts", "education", "projects", "certifications", "languages"):
        _append_unique(merged.setdefault(key, []), additions.get(key, []))
    skills = merged.setdefault("skills", {})
    for category, values in additions.get("skills", {}).items():
        _append_unique(skills.setdefault(category, []), values)
    experiences = merged.setdefault("experience", [])
    by_id = {item.get("id"): item for item in experiences if isinstance(item, dict)}
    for update in additions.get("experience_updates", []):
        target = by_id.get(update.get("id"))
        if target:
            _append_unique(target.setdefault("facts", []), update.get("facts", []))
            _append_unique(target.setdefault("framings", []), update.get("framings", []))
    for item in additions.get("new_experience", []):
        if isinstance(item, dict) and item.get("id") and item["id"] not in by_id:
            experiences.append(item); by_id[item["id"]] = item
    return merged

