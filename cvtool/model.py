import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


class ModelError(RuntimeError):
    pass


def complete(system, user, *, server_url=None, model=None, llama_cli=None,
             temperature=0.2, max_tokens=4096, raw_response_file=None):
    if llama_cli:
        if not model:
            raise ModelError("--model is required with --llama-cli")
        prompt = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        cmd = [llama_cli, "-m", model, "-p", prompt, "-n", str(max_tokens),
               "--temp", str(temperature), "--no-display-prompt"]
        try:
            result = subprocess.run(cmd, text=True, capture_output=True, check=True)
        except FileNotFoundError as exc:
            raise ModelError(f"llama.cpp executable not found: {llama_cli}") from exc
        except subprocess.CalledProcessError as exc:
            raise ModelError(exc.stderr.strip() or "llama-cli failed") from exc
        if raw_response_file:
            path = Path(raw_response_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result.stdout, encoding="utf-8")
        return result.stdout.strip()

    url = (server_url or os.environ.get("LLAMA_SERVER_URL") or
           "http://127.0.0.1:8080/v1/chat/completions")
    payload = {
        "model": model or "local-model",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw_body = response.read()
        if raw_response_file:
            path = Path(raw_response_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw_body)
        body = json.loads(raw_body)
        return body["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as exc:
        raise ModelError(
            f"Could not reach llama.cpp at {url}. Start llama-server or use "
            f"--llama-cli. Details: {exc.reason}") from exc
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ModelError("llama.cpp returned an unexpected response") from exc
