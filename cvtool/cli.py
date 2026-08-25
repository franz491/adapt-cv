import argparse
import datetime as dt
import os
import shutil
import sys
from pathlib import Path

import yaml

from .extraction import merge_discoveries, parse_json_response, read_previous_cv
from .formatting import normalize_markdown
from .model import ModelError, complete
from .pdf import render_pdf
from .prompts import (CV_SYSTEM_PROMPT, EXTRACT_SYSTEM_PROMPT, cv_user_prompt,
                      extraction_user_prompt)


def _parser():
    parser = argparse.ArgumentParser(prog="cv", description="Generate truthful, tailored CVs with llama.cpp")
    parser.add_argument("--data", default="user data.yaml", help="canonical YAML data file")
    parser.add_argument("--server-url", help="llama-server chat completions URL")
    parser.add_argument("--llama-cli", help="path to llama-cli instead of llama-server")
    parser.add_argument("--model", help="server model name or GGUF path with --llama-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="create Markdown and PDF CV")
    gen.add_argument("--job", default="job opening.txt")
    gen.add_argument("--output", default="output")
    gen.add_argument("--max-tokens", type=int, default=64000,
                     help="maximum generated tokens (default: 64000)")
    gen.add_argument("--response-file", metavar="PATH",
                     help="save the complete raw llama-server HTTP response body")
    ext = sub.add_parser("extract", help="merge missing facts from previous CVs")
    ext.add_argument("sources", nargs="+")
    ext.add_argument("--dry-run", action="store_true", help="print proposed merged YAML without writing")
    ext.add_argument("--max-tokens", type=int, default=64000,
                     help="maximum generated tokens (default: 64000)")
    ext.add_argument("--show-response", action="store_true",
                     help="print the extracted assistant content to stderr")
    ext.add_argument("--response-file", metavar="PATH",
                     help="save the complete raw llama-server HTTP response body")
    sub.add_parser("show-prompt", help="print the generation system prompt")
    return parser


def _read_data(path):
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"Missing {path}. Copy 'user data.example.yaml' and fill it in.")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping")
    return value


def _yaml(data):
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def _call(args, system, user, temperature, max_tokens, raw_response_file=None):
    return complete(system, user, server_url=args.server_url, model=args.model,
                    llama_cli=args.llama_cli, temperature=temperature,
                    max_tokens=max_tokens, raw_response_file=raw_response_file)


def _generate(args):
    data = _read_data(args.data)
    job_path = Path(args.job)
    if not job_path.exists():
        raise RuntimeError(f"Missing job opening: {job_path}")
    job = job_path.read_text(encoding="utf-8").strip()
    if not job or job == "Paste the complete job opening here.":
        raise RuntimeError(f"Add the vacancy text to {job_path} first")
    raw = _call(args, CV_SYSTEM_PROMPT, cv_user_prompt(_yaml(data), job), 0.25,
                args.max_tokens,
                raw_response_file=args.response_file)
    if args.response_file:
        print(f"Raw llama-server response: {args.response_file}", file=sys.stderr)
    markdown = normalize_markdown(raw)
    if not markdown.startswith("# "):
        raise RuntimeError("Model output was not a Markdown CV (expected a '# Name' heading)")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    md_path, pdf_path = output / "cv.md", output / "cv.pdf"
    md_path.write_text(markdown, encoding="utf-8")
    render_pdf(markdown, pdf_path)
    print(f"Created {md_path} and {pdf_path}")


def _extract(args):
    data_path = Path(args.data)
    data = _read_data(data_path)
    chunks = []
    for source in args.sources:
        text = read_previous_cv(source).strip()
        if text:
            chunks.append(f"SOURCE: {source}\n{text}")
    if not chunks:
        raise RuntimeError("No readable text found in the supplied previous CVs")
    raw_path = Path(args.response_file) if args.response_file else Path("output/extraction-response.json")
    response = _call(args, EXTRACT_SYSTEM_PROMPT,
                     extraction_user_prompt(_yaml(data), "\n\n".join(chunks)), 0.0,
                     args.max_tokens,
                     raw_response_file=raw_path)
    if args.show_response:
        print("----- raw model response -----", file=sys.stderr)
        print(response if response else "[empty response]", file=sys.stderr)
        print("----- end raw model response -----", file=sys.stderr)
    print(f"Raw llama-server response: {raw_path}", file=sys.stderr)
    try:
        additions = parse_json_response(response)
    except RuntimeError as exc:
        description = "empty" if not response else f"{len(response)} characters"
        raise RuntimeError(
            f"{exc}. Assistant content was {description}; complete server response saved to {raw_path}") from exc
    merged = merge_discoveries(data, additions)
    rendered = _yaml(merged)
    conflicts = additions.get("conflicts", [])
    if conflicts:
        print("Conflicts requiring manual review:", file=sys.stderr)
        for conflict in conflicts:
            print(f"  - {conflict}", file=sys.stderr)
    if args.dry_run:
        print(rendered, end="")
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = data_path.with_name(f"{data_path.name}.backup-{stamp}")
    shutil.copy2(data_path, backup)
    data_path.write_text(rendered, encoding="utf-8")
    print(f"Updated {data_path} (backup: {backup})")


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "show-prompt":
            print(CV_SYSTEM_PROMPT); return 0
        if args.command == "generate":
            _generate(args)
        elif args.command == "extract":
            _extract(args)
        return 0
    except (RuntimeError, ModelError, OSError, yaml.YAMLError) as exc:
        print(f"cv: error: {exc}", file=sys.stderr)
        return 1
