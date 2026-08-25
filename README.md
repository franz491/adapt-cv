# cv-editor

A small, local-first CV generator. It combines a canonical YAML data file and
`job opening.txt`, asks a llama.cpp model to write a tailored Markdown CV, then
normalizes the Markdown and renders a PDF.

## Quick start

1. Copy `user data.example.yaml` to `user data.yaml` and fill in your facts.
2. Copy `job opening.example.txt` to `job opening.txt` and paste the vacancy.
3. Start llama.cpp's OpenAI-compatible server, for example:

   ```sh
   llama-server -m /path/to/model.gguf --port 8080
   ```

4. Generate the CV:

   ```sh
   ./cv generate
   ```

The results are written to `output/cv.md` and `output/cv.pdf`.

To recover missing information from old CVs before generating:

```sh
./cv extract old-cv.pdf older-cv.md
./cv generate
```

To inspect exactly what the model returned during extraction:

```sh
./cv extract old-cv.pdf --dry-run --show-response
./cv extract old-cv.pdf --response-file output/raw-extraction.json
./cv extract old-cv.pdf --max-tokens 64000
```

`--response-file` contains the complete HTTP response body from llama-server,
including usage, finish reason, reasoning fields, and assistant content. A copy
is automatically saved to `output/extraction-response.json` when no path is
specified.

Extraction updates `user data.yaml` and first creates a timestamped backup.
Merging is additive: existing values are not overwritten, new list entries are
deduplicated and appended, and facts/framings are appended to an existing
experience with the same ID. Conflicting source details are only reported for
manual review.
PDF, Markdown, plain text, and DOCX inputs are accepted (DOCX needs
`python-docx`; PDFs use the `pdftotext` command).

## Model configuration

By default the CLI calls `http://127.0.0.1:8080/v1/chat/completions`. Override
it with `--server-url`, `LLAMA_SERVER_URL`, or `--model`. If you prefer direct
execution, pass a llama.cpp binary and GGUF model:

```sh
./cv --llama-cli /path/to/llama-cli --model /path/to/model.gguf generate
```

Useful options:

```text
./cv generate --data "user data.yaml" --job "job opening.txt" --output output
./cv generate --response-file output/raw-generation.json
./cv generate --max-tokens 64000
./cv extract previous.pdf --dry-run
./cv show-prompt
```

Options accept both conventional forms, for example
`--response-file output.json` and `--response-file=output.json`.

Personal data, job openings, generated PDFs, model files, and raw server
responses are excluded by `.gitignore` so they are not accidentally published.

Run tests with `python3 -m unittest discover -s tests`.
