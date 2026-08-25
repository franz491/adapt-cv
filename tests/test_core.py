import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

from cvtool.cli import main
from cvtool.extraction import merge_discoveries, parse_json_response
from cvtool.formatting import normalize_markdown
from cvtool.prompts import CV_SYSTEM_PROMPT
from cvtool.pdf import _inline


class FormattingTests(unittest.TestCase):
    def test_removes_fence_and_normalizes_bullets(self):
        source = "```markdown\n#Jane Doe\n\n• Built a thing\n```"
        self.assertEqual(normalize_markdown(source), "# Jane Doe\n\n- Built a thing\n")

    def test_generation_prompt_requires_selective_keyword_bolding(self):
        self.assertIn("Markdown bold (`**keyword**`)", CV_SYSTEM_PROMPT)
        self.assertIn("genuinely supported by the candidate data", CV_SYSTEM_PROMPT)
        self.assertIn("never whole bullets", CV_SYSTEM_PROMPT)

    def test_pdf_preserves_bold_markdown_and_escapes_html(self):
        self.assertEqual(_inline("Used **Python** & SQL"), "Used <b>Python</b> &amp; SQL")

    def test_pdf_converts_markdown_links_to_clickable_links(self):
        rendered = _inline("[Portfolio](example.com) · [Email](mailto:me@example.com)")
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn('href="mailto:me@example.com"', rendered)
        self.assertIn("<u>Portfolio</u>", rendered)

    def test_pdf_does_not_make_unsafe_links_clickable(self):
        self.assertEqual(_inline("[Click](javascript:evil)"), "Click")


class ExtractionTests(unittest.TestCase):
    def test_merge_is_additive_and_does_not_overwrite(self):
        data = {"person": {"name": "Real Name"}, "experience": [{
            "id": "job", "facts": ["Built APIs"], "framings": ["Backend delivery"]
        }]}
        additions = {
            "person": {"name": "Wrong Name", "location": "Lisbon"},
            "experience_updates": [{"id": "job", "facts": ["Built APIs", "Led migration"],
                                    "framings": ["Platform modernization"]}]
        }
        merged = merge_discoveries(data, additions)
        self.assertEqual(merged["person"]["name"], "Real Name")
        self.assertEqual(merged["person"]["location"], "Lisbon")
        self.assertEqual(merged["experience"][0]["facts"], ["Built APIs", "Led migration"])
        self.assertEqual(len(merged["experience"][0]["framings"]), 2)

    def test_json_fences_are_tolerated(self):
        self.assertEqual(parse_json_response("```json\n{\"person\": {}}\n```"), {"person": {}})

    def test_invalid_response_is_saved_for_inspection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.yaml"
            source = root / "old.txt"
            response_file = root / "raw.txt"
            data.write_text(yaml.safe_dump({"person": {}, "experience": []}))
            source.write_text("Previous CV contents")
            errors = StringIO()
            def fake_call(*args, **kwargs):
                Path(kwargs["raw_response_file"]).write_text('{"raw": true}')
                return "not json"
            with patch("cvtool.cli._call", side_effect=fake_call), redirect_stderr(errors):
                result = main(["--data", str(data), "extract", str(source),
                               "--response-file", str(response_file)])
            self.assertEqual(result, 1)
            self.assertEqual(response_file.read_text(), '{"raw": true}')
            self.assertIn("8 characters", errors.getvalue())

    def test_extract_token_limit_is_configurable(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.yaml"
            source = root / "old.txt"
            data.write_text(yaml.safe_dump({"person": {}, "experience": []}))
            source.write_text("Previous CV contents")
            captured = {}
            def fake_call(*args, **kwargs):
                captured["max_tokens"] = args[4]
                Path(kwargs["raw_response_file"]).parent.mkdir(parents=True, exist_ok=True)
                Path(kwargs["raw_response_file"]).write_text("{}")
                return "{}"
            with patch("cvtool.cli._call", side_effect=fake_call):
                result = main(["--data", str(data), "extract", str(source),
                               "--dry-run", "--max-tokens", "20000"])
            self.assertEqual(result, 0)
            self.assertEqual(captured["max_tokens"], 20000)

    def test_extract_default_token_limit_is_64000(self):
        from cvtool.cli import _parser
        args = _parser().parse_args(["extract", "old.txt"])
        self.assertEqual(args.max_tokens, 64000)

    def test_generate_default_token_limit_is_64000(self):
        from cvtool.cli import _parser
        args = _parser().parse_args(["generate"])
        self.assertEqual(args.max_tokens, 64000)

    def test_generate_token_limit_is_configurable(self):
        from cvtool.cli import _parser
        args = _parser().parse_args(["generate", "--max-tokens=32000"])
        self.assertEqual(args.max_tokens, 32000)

    def test_response_file_accepts_space_and_equals_forms(self):
        from cvtool.cli import _parser
        parser = _parser()
        generate_space = parser.parse_args(["generate", "--response-file", "one.json"])
        generate_equals = parser.parse_args(["generate", "--response-file=two.json"])
        extract_space = parser.parse_args(["extract", "old.txt", "--response-file", "three.json"])
        extract_equals = parser.parse_args(["extract", "old.txt", "--response-file=four.json"])
        self.assertEqual(generate_space.response_file, "one.json")
        self.assertEqual(generate_equals.response_file, "two.json")
        self.assertEqual(extract_space.response_file, "three.json")
        self.assertEqual(extract_equals.response_file, "four.json")


if __name__ == "__main__":
    unittest.main()
