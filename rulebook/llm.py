"""Call Claude.

Default: headless Claude Code (`claude -p`) on the logged-in Claude subscription, which is
what the experiments here ran on. With ANTHROPIC_API_KEY set: the Anthropic API instead.
Every reply is cached on disk, so re-running an experiment costs nothing.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from rulebook import DATA

CACHE = DATA / "llm_cache"
# Exact model IDs on both paths: the CLI's bare "sonnet"/"haiku" aliases resolve to whatever its version defaults to.
MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
TRANSIENT = ("rate limit", "rate_limit", "overloaded", "429", "529", "timeout", "temporarily")


def ask_timed(prompt: str, system: str, model: str = "haiku", schema: dict | None = None) -> tuple[str, float]:
    """Reply text and the milliseconds the original (uncached) call took. With a JSON schema the reply is
    structured output, so it is valid JSON that matches the schema."""
    key = hashlib.sha256(json.dumps([MODELS[model], system, prompt] + ([schema] if schema else [])).encode()).hexdigest()
    hit = CACHE / f"{key}.json"
    if hit.exists():
        cached = json.loads(hit.read_text(encoding="utf-8"))
        return cached["text"], cached["ms"]
    text, ms = _call(prompt, system, model, schema)
    CACHE.mkdir(parents=True, exist_ok=True)
    hit.write_text(json.dumps({"text": text, "ms": ms, "model": MODELS[model]}, ensure_ascii=False), encoding="utf-8")
    return text, ms


def _call(prompt: str, system: str, model: str, schema: dict | None) -> tuple[str, float]:
    """Retry transient errors with backoff; a usage limit stops the run. Latency is the successful attempt only."""
    backend = _api if os.environ.get("ANTHROPIC_API_KEY") else _cli
    for attempt in range(6):
        t = time.perf_counter()
        try:
            return backend(prompt, system, model, schema), (time.perf_counter() - t) * 1000
        except RuntimeError as e:
            msg = str(e).lower()
            if attempt == 5 or "usage limit" in msg or not any(s in msg for s in TRANSIENT):
                raise
            time.sleep(10 * 2 ** attempt)  # 10, 20, 40, 80, 160 s


def ask(prompt: str, system: str, model: str = "haiku") -> str:
    return ask_timed(prompt, system, model)[0]


def ask_json(prompt: str, system: str, schema: dict, model: str = "haiku") -> dict:
    # Structured output, not "reply with JSON only": a German „quote" closed with an ASCII " broke a plain JSON reply.
    return json.loads(ask_timed(prompt, system, model, schema)[0])


def _claude_exe() -> str:
    # On Windows the npm shim (claude.cmd) re-parses arguments through cmd.exe; call the binary.
    shim = shutil.which("claude")
    if not shim:
        raise RuntimeError("Claude Code CLI not found: install it, or set ANTHROPIC_API_KEY")
    exe = Path(shim).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    return str(exe) if exe.exists() else shim


def _cli(prompt: str, system: str, model: str, schema: dict | None = None) -> str:
    # The prompt carries retrieved document text, so the model gets no tools, no MCP servers,
    # no settings at all (hooks, plugins, CLAUDE.md), an empty working directory, and nothing is saved.
    # --json-schema adds only its own StructuredOutput tool.
    with tempfile.TemporaryDirectory() as cwd:
        system_file = Path(cwd) / "system.txt"
        system_file.write_text(system, encoding="utf-8")
        cmd = [_claude_exe(), "-p", "--model", MODELS[model], "--tools", "", "--strict-mcp-config",
               "--setting-sources", "", "--system-prompt-file", str(system_file),
               "--output-format", "json", "--no-session-persistence"]
        if schema:
            cmd += ["--json-schema", json.dumps(schema)]
        try:
            out = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                 encoding="utf-8", cwd=cwd, timeout=600)
        except subprocess.TimeoutExpired:
            raise RuntimeError("claude -p timeout") from None
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {(out.stderr or out.stdout)[-400:]}")
    res = json.loads(out.stdout)
    if res.get("is_error"):
        raise RuntimeError(f"claude -p error: {res.get('result')}")
    if schema:
        if res.get("structured_output") is None:
            raise RuntimeError("claude -p returned no structured output")
        return json.dumps(res["structured_output"], ensure_ascii=False)
    return res["result"]


def _api(prompt: str, system: str, model: str, schema: dict | None = None) -> str:
    import anthropic

    extra = {}
    if model == "sonnet":  # a safety-classifier decline is re-run on a fallback model
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    if schema:
        extra["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    msg = anthropic.Anthropic().beta.messages.create(
        model=MODELS[model], max_tokens=4096, system=system,
        messages=[{"role": "user", "content": prompt}], **extra,
    )
    if msg.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    return "".join(b.text for b in msg.content if b.type == "text")
