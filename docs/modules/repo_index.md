# repo_index

_Auto-generated from repo index. Run `python -m agents.repo_bot.docgen` to refresh._

### `Chunk`

- **File:** `agents/repo_bot/repo_index.py` (lines 16-24)
- **Called by:** chunk_generic_file, chunk_python_file, load_index
- **Calls:** (none found)

```python
class Chunk:
    path: str
    symbol: str
    kind: str  # "function" | "class" | "file"
    start_line: int
    end_line: int
    text: str
```


### `iter_repo_files`

- **File:** `agents/repo_bot/repo_index.py` (lines 25-38)
- **Called by:** build_index
- **Calls:** is_file, lower, rglob

```python
def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        # ✅ ignore generated index + build output
        if p.name in {".repo_index.json"}:
            continue
        if p.parts and p.parts[0] in {"site"}:
            continue
        if p.suffix.lower() not in ALLOWED_EXTS:
            continue
        yield p
```


### `chunk_python_file`

- **File:** `agents/repo_bot/repo_index.py` (lines 39-122)
- **Called by:** build_index
- **Calls:** Chunk, compile, find_block_end, group, match, pop, read_text, splitlines

```python
def chunk_python_file(path: Path, rel_path: str) -> List[Chunk]:
    """
    Chunk Python files by extracting def/class blocks, including nested defs.

    - Top-level: def foo -> symbol "foo"
    - Nested: def bundle_score inside respond_node -> symbol "respond_node.bundle_score"
    """
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    chunks: List[Chunk] = []

    # Match any def/class with indentation
    pattern = re.compile(r"^(\s*)(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]")

    # Build a list of symbols with (indent, kind, name, line_no)
    hits: List[tuple] = []
    for i, line in enumerate(lines, start=1):
        m = pattern.match(line)
        if m:
            indent = len(m.group(1))
            kind = m.group(2)
            name = m.group(3)
            hits.append((indent, kind, name, i))

    if not hits:
        chunks.append(
            Chunk(
                path=rel_path,
                symbol=path.name,
                kind="file",
                start_line=1,
                end_line=min(len(lines), 400),
                text="\n".join(lines[:400]),
            )
        )
        return chunks

    # Helper: determine block end by indentation
    def find_block_end(start_idx_1based: int, start_indent: int) -> int:
        start0 = start_idx_1based - 1
        for j in range(start0 + 1, len(lines)):
            l = lines[j]
            if not l.strip():
                continue
            m2 = pattern.match(l)
            if m2:
                indent2 = len(m2.group(1))
                if indent2 <= start_indent:
                    return j  # exclusive
        return len(lines)

    # Maintain a stack to build parent names for nested defs
    # Each stack item: (indent, name)
    stack: List[tuple] = []

    for idx, (indent, kind, name, start_line) in enumerate(hits):
        # Pop stack until current indent is greater than top indent
        while stack and indent <= stack[-1][0]:
            stack.pop()

        # Parent chain (only include def/class names)
        parent_chain = ".".join([s[1] for s in stack])
        full_name = f"{parent_chain}.{name}" if parent_chain else name

        end0_excl = find_block_end(start_line, indent)
        text = "\n".join(lines[start_line - 1 : end0_excl])

        chunks.append(
            Chunk(
                path=rel_path,
                symbol=full_name,
                kind="function" if kind == "def" else "class",
                start_line=start_line,
                end_line=end0_excl,
                text=text,
            )
        )

        # Push current symbol onto stack
        stack.append((indent, name))

    return chunks
```


### `chunk_python_file.find_block_end`

- **File:** `agents/repo_bot/repo_index.py` (lines 76-122)
- **Called by:** chunk_python_file
- **Calls:** group, match, strip

```python
def find_block_end(start_idx_1based: int, start_indent: int) -> int:
        start0 = start_idx_1based - 1
        for j in range(start0 + 1, len(lines)):
            l = lines[j]
            if not l.strip():
                continue
            m2 = pattern.match(l)
            if m2:
                indent2 = len(m2.group(1))
                if indent2 <= start_indent:
                    return j  # exclusive
        return len(lines)

    # Maintain a stack to build parent names for nested defs
    # Each stack item: (indent, name)
    stack: List[tuple] = []

    for idx, (indent, kind, name, start_line) in enumerate(hits):
        # Pop stack until current indent is greater than top indent
        while stack and indent <= stack[-1][0]:
            stack.pop()

        # Parent chain (only include def/class names)
        parent_chain = ".".join([s[1] for s in stack])
        full_name = f"{parent_chain}.{name}" if parent_chain else name

        end0_excl = find_block_end(start_line, indent)
        text = "\n".join(lines[start_line - 1 : end0_excl])

        chunks.append(
            Chunk(
                path=rel_path,
                symbol=full_name,
                kind="function" if kind == "def" else "class",
                start_line=start_line,
                end_line=end0_excl,
                text=text,
            )
        )

        # Push current symbol onto stack
        stack.append((indent, name))

    return chunks
```


### `chunk_generic_file`

- **File:** `agents/repo_bot/repo_index.py` (lines 123-143)
- **Called by:** build_index
- **Calls:** Chunk, read_text, splitlines

```python
def chunk_generic_file(path: Path, rel_path: str) -> List[Chunk]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Small chunking: split into ~200 lines
    lines = text.splitlines()
    chunks: List[Chunk] = []
    step = 200
    for i in range(0, len(lines), step):
        part = "\n".join(lines[i : i + step])
        chunks.append(
            Chunk(
                path=rel_path,
                symbol=f"{path.name}:{i+1}",
                kind="file",
                start_line=i + 1,
                end_line=min(i + step, len(lines)),
                text=part,
            )
        )
    return chunks
```


### `build_index`

- **File:** `agents/repo_bot/repo_index.py` (lines 144-163)
- **Called by:** main
- **Calls:** Path, asdict, chunk_generic_file, chunk_python_file, dumps, iter_repo_files, lower, relative_to, resolve, startswith, write_text

```python
def build_index(repo_root: str, out_path: str = ".repo_index.json") -> Dict[str, int]:
    root = Path(repo_root).resolve()
    all_chunks: List[Chunk] = []

    for file_path in iter_repo_files(root):
        rel_path = str(file_path.relative_to(root))
        if rel_path.startswith(("site/", "venv/", ".venv/", "__pycache__/")):
            continue

        if file_path.suffix.lower() == ".py":
            all_chunks.extend(chunk_python_file(file_path, rel_path))
        else:
            all_chunks.extend(chunk_generic_file(file_path, rel_path))

    payload = [asdict(c) for c in all_chunks]
    Path(out_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {"files": len(list(iter_repo_files(root))), "chunks": len(all_chunks), "index_path": 1}
```


### `load_index`

- **File:** `agents/repo_bot/repo_index.py` (lines 164-166)
- **Called by:** generate_docs, main
- **Calls:** Chunk, Path, loads, read_text

```python
def load_index(index_path: str = ".repo_index.json") -> List[Chunk]:
    data = json.loads(Path(index_path).read_text(encoding="utf-8"))
    return [Chunk(**d) for d in data]
```

