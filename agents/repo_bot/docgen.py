# agents/repo_bot/docgen.py
from __future__ import annotations

from pathlib import Path
from collections import defaultdict
from typing import Dict, List

from agents.repo_bot.repo_index import load_index, Chunk
from agents.repo_bot.repo_trace import trace_symbol


def module_name_from_path(path: str) -> str:
    # agents/tools.py -> tools
    p = Path(path)
    return p.stem


def render_chunk_md(chunk: Chunk, repo_root: str) -> str:
    callers, callees = trace_symbol(repo_root, chunk.symbol)

    if not callers and "." in chunk.symbol:
        callers = [chunk.symbol.split(".")[0]]

    header = f"### `{chunk.symbol}`\n\n"
    meta = f"- **File:** `{chunk.path}` (lines {chunk.start_line}-{chunk.end_line})\n"
    meta += f"- **Called by:** {', '.join(callers) if callers else '(not found)'}\n"
    meta += f"- **Calls:** {', '.join(callees) if callees else '(none found)'}\n\n"

    code = "```python\n" + chunk.text.strip() + "\n```\n\n"

    return header + meta + code


def generate_docs(index_path: str = ".repo_index.json", out_dir: str = "docs/modules"):
    repo_root = str(Path.cwd())
    chunks: List[Chunk] = load_index(index_path)

    # group chunks by module (agents/tools.py -> tools.md)
    groups: Dict[str, List[Chunk]] = defaultdict(list)
    for c in chunks:
        if not c.path.endswith(".py"):
            continue
        if not c.path.startswith("agents/") and not c.path.startswith("api/"):
            continue
        if c.kind not in {"function", "class"}:
            continue
        groups[module_name_from_path(c.path)].append(c)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    created = []
    for mod, items in sorted(groups.items()):
        items_sorted = sorted(items, key=lambda x: (x.path, x.start_line))

        md = [f"# {mod}\n"]
        md.append(f"_Auto-generated from repo index. Run `python -m agents.repo_bot.docgen` to refresh._\n")

        for chunk in items_sorted:
            md.append(render_chunk_md(chunk, repo_root))

        dest = out / f"{mod}.md"
        dest.write_text("\n".join(md), encoding="utf-8")
        created.append(dest.as_posix())

    print("✅ Generated module docs:")
    for p in created:
        print(" -", p)


if __name__ == "__main__":
    generate_docs()
