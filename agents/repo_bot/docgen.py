# agents/repo_bot/docgen.py
# agents/repo_bot/docgen.py
from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


from agents.repo_bot.repo_index import load_index, Chunk
from agents.repo_bot.repo_trace import trace_symbol


CACHE_PATH = ".docgen_cache.json"


# -----------------------
# Utilities
# -----------------------

def llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def load_cache() -> dict:
    p = Path(CACHE_PATH)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict):
    Path(CACHE_PATH).write_text(json.dumps(cache, indent=2), encoding="utf-8")


def chunk_hash(chunk: Chunk, callers: list[str], callees: list[str]) -> str:
    m = hashlib.sha256()
    m.update(chunk.text.encode("utf-8", errors="ignore"))
    m.update(("|".join(callers)).encode("utf-8"))
    m.update(("|".join(callees)).encode("utf-8"))
    return m.hexdigest()


def module_name_from_path(path: str) -> str:
    return Path(path).stem


# -----------------------
# GPT-5 summarization
# -----------------------

def llm_summary_for_chunk(chunk: Chunk, callers: list[str], callees: list[str]) -> str:
    if not llm_enabled():
        return ""

    from openai import OpenAI
    client = OpenAI()

    prompt = f"""
You are documenting a real production codebase called **Retail Intelligence Copilot**.

Write a concise, accurate Markdown explanation for the code below.

STRICT REQUIREMENTS:
- Do NOT hallucinate.
- Use simple, senior-engineer-friendly language.
- Keep each section short (2–4 lines max).
- Focus on how this helps retail promotion, recommendations, or system orchestration.

Use EXACTLY these sections:

### Purpose
### Inputs / Outputs
### How it connects
### Why it matters in this project

Context:
- File: {chunk.path}
- Symbol: {chunk.symbol}
- Called by: {", ".join(callers) if callers else "(not shown)"}
- Calls: {", ".join(callees) if callees else "(none)"}

Code:
```python
{chunk.text.strip()}
""".strip()
    response = client.responses.create(
    model="gpt-5",
    instructions="You are a senior software engineer writing technical documentation.",
    input=prompt,
)

    return response.output_text.strip()

def render_chunk_md(chunk: Chunk, repo_root: str, cache: dict) -> str:
    callers, callees = trace_symbol(repo_root, chunk.symbol)
    key = f"{chunk.path}::{chunk.symbol}"
    h = chunk_hash(chunk, callers, callees)

    cached = cache.get(key)
    if cached and cached.get("hash") == h:
        summary = cached.get("summary", "")
    else:
        summary = llm_summary_for_chunk(chunk, callers, callees)
        cache[key] = {"hash": h, "summary": summary}

    header = f"## `{chunk.symbol}`\n\n"

    meta = (
        f"- **File:** `{chunk.path}` (lines {chunk.start_line}-{chunk.end_line})\n"
        f"- **Called by:** {', '.join(callers) if callers else '(not shown)'}\n"
        f"- **Calls:** {', '.join(callees) if callees else '(none)'}\n\n"
    )

    summary_md = f"{summary}\n\n" if summary else ""

    code = f"```python\n{chunk.text.strip()}\n```\n\n"

    return header + meta + summary_md + code

def generate_docs(index_path: str = ".repo_index.json", out_dir: str = "docs/modules"):
    repo_root = str(Path.cwd())
    chunks: List[Chunk] = load_index(index_path)
    cache = load_cache()

    groups: Dict[str, List[Chunk]] = defaultdict(list)
    for c in chunks:
        if not c.path.endswith(".py"):
            continue
        if c.kind not in {"function", "class"}:
            continue
        if not (c.path.startswith("agents/") or c.path.startswith("api/")):
            continue
        groups[module_name_from_path(c.path)].append(c)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    created = []

    for mod, items in sorted(groups.items()):
        md = [f"# `{mod}` Module\n"]
        md.append(
            "_Auto-generated documentation. Summaries are produced by GPT-5 and "
            "cached to avoid unnecessary re-generation._\n"
        )

        for chunk in sorted(items, key=lambda x: x.start_line):
            md.append(render_chunk_md(chunk, repo_root, cache))

        dest = out / f"{mod}.md"
        dest.write_text("\n".join(md), encoding="utf-8")
        created.append(dest.as_posix())

    save_cache(cache)

    print("✅ Generated GPT-5 enhanced module docs:")
    for p in created:
        print(" -", p)

if __name__ == "__main__":
        generate_docs()


 
 

