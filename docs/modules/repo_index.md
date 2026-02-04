# `repo_index` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `Chunk`

- **File:** `agents/repo_bot/repo_index.py` (lines 16-24)
- **Called by:** chunk_generic_file, chunk_python_file, load_index
- **Calls:** (none)

### Purpose
Represents a single, indexable slice of the repository with precise location and type. It captures the code or file segment used for building a searchable repo index.

### Inputs / Outputs
Holds: path, symbol, kind ("function" | "class" | "file"), start_line, end_line, text. It’s a data-only container; instances carry chunk metadata and content.

### How it connects
Constructed by chunk_generic_file and chunk_python_file; aggregated by load_index. It doesn’t call anything itself—other components read these records to build and query the index.

### Why it matters in this project
Fine-grained chunks let the copilot retrieve only the relevant logic (e.g., promo rules, recommendation handlers, orchestration glue) instead of whole files. This improves accuracy and speed when reasoning about or modifying retail promotion and recommendation workflows.

```python
class Chunk:
    path: str
    symbol: str
    kind: str  # "function" | "class" | "file"
    start_line: int
    end_line: int
    text: str
```


## `iter_repo_files`

- **File:** `agents/repo_bot/repo_index.py` (lines 25-38)
- **Called by:** build_index
- **Calls:** is_file, lower, rglob

### Purpose
Enumerate indexable files in the repository, skipping generated artifacts and build output.
Ensures only allowed file types are considered for the repo index.

### Inputs / Outputs
Input: repo_root (Path) as the repository root.
Output: iterable of Path objects for eligible files to index.

### How it connects
Called by build_index to supply the file list.
Uses rglob for recursion, is_file to filter, suffix.lower with ALLOWED_EXTS, and ignores .repo_index.json and the top-level site directory.

### Why it matters in this project
A clean, precise index speeds code search and reduces noise for the Repo Bot.
This improves orchestration workflows that power retail promotions and recommendations by making relevant code easier to find and reason about.

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


## `chunk_python_file`

- **File:** `agents/repo_bot/repo_index.py` (lines 39-122)
- **Called by:** build_index
- **Calls:** Chunk, compile, find_block_end, group, match, pop, read_text, splitlines

### Purpose
Split a Python file into symbol-level chunks (functions/classes), preserving nesting via dot-qualified names (e.g., respond_node.bundle_score). Enables precise code indexing for the Repo Bot.

### Inputs / Outputs
Inputs: path (Path) to the file, rel_path (str) for index display.  
Outputs: List[Chunk] with path, symbol, kind, start_line, end_line, text; if no defs/classes, returns a single “file” chunk of up to 400 lines.

### How it connects
Called by build_index to populate the repository symbol index.  
Uses re.compile/match/group, Path.read_text/splitlines, a stack with pop to track nesting, and a local find_block_end to bound blocks by indentation. Produces Chunk objects for each def/class.

### Why it matters in this project
Retail Intelligence Copilot needs symbol-accurate indexing to locate promotion rules, recommendation logic, and orchestration code quickly. This function enables targeted search, summarization, and safe edits at function/class granularity, including nested logic often used in scoring and rule evaluation.

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


## `chunk_python_file.find_block_end`

- **File:** `agents/repo_bot/repo_index.py` (lines 76-122)
- **Called by:** (not shown)
- **Calls:** group, match, strip

### Purpose
Find the exclusive end line of a Python block (def/class) by scanning forward until a line with matching pattern appears at the same or lower indentation. Used to slice the source into precise chunks.

### Inputs / Outputs
- Inputs: start_idx_1based (block’s 1-based start line), start_indent (indent width at start). Uses outer variables: lines (file lines), pattern (regex with group(1) for leading spaces).
- Output: An exclusive line index into lines where the block ends; defaults to len(lines) if no boundary is found.

### How it connects
This helper supplies end indices to build Chunk objects (path, symbol, kind, start_line, end_line, text). Combined with a stack-based parent chain, it names nested symbols cleanly for the repo index.

### Why it matters in this project
Accurate block boundaries produce clean, searchable symbols, letting the Copilot resolve and orchestrate code paths reliably. That precision supports promotion and recommendation workflows by linking queries to the exact functions/classes that implement them.

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


## `chunk_generic_file`

- **File:** `agents/repo_bot/repo_index.py` (lines 123-143)
- **Called by:** build_index
- **Calls:** Chunk, read_text, splitlines

### Purpose
Split a generic text file into ~200-line chunks for indexing. Each chunk carries file/line metadata to support precise retrieval and navigation across large files.

### Inputs / Outputs
- Inputs: path (Path to the file), rel_path (string relative path).
- Output: List[Chunk], each with path=rel_path, symbol="<filename>:<start_line>", kind="file", start_line, end_line, and text.

### How it connects
Called by build_index to build the repository index. Uses Path.read_text and splitlines, then constructs Chunk objects for downstream search and retrieval.

### Why it matters in this project
Chunked indexing lets the Copilot quickly fetch only the relevant parts of code/config driving promotions, recommendations, and orchestration flows. This improves search precision, reduces context size, and speeds up reasoning over retail systems.

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


## `build_index`

- **File:** `agents/repo_bot/repo_index.py` (lines 144-163)
- **Called by:** main
- **Calls:** Path, asdict, chunk_generic_file, chunk_python_file, dumps, iter_repo_files, lower, relative_to, resolve, startswith, write_text

### Purpose
Build a searchable index of the repository by chunking files and writing them to a JSON file. Skips virtualenv and build artifacts, and uses language-aware chunking for Python files vs generic text.

### Inputs / Outputs
- Inputs: repo_root (str), out_path (str, default ".repo_index.json").
- Outputs: Writes a JSON array of chunk dictionaries to out_path. Returns counts for files and chunks, plus index_path set to 1.

### How it connects
Called by main. Walks files via iter_repo_files, filters paths, chunks with chunk_python_file or chunk_generic_file, converts chunks with asdict, and writes JSON via Path.write_text and json.dumps. Uses resolve/relative_to/lower/startswith for robust path handling.

### Why it matters in this project
A clean, chunked repo index lets the Copilot quickly locate relevant code and configs to orchestrate tasks. This improves grounding for features like promotion logic reviews, recommendation pipeline insights, and coordinated changes across services.

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


## `load_index`

- **File:** `agents/repo_bot/repo_index.py` (lines 164-166)
- **Called by:** generate_docs, main
- **Calls:** Chunk, Path, loads, read_text

### Purpose
Load a prebuilt repository index from JSON and reconstruct it as a list of Chunk objects. This enables fast, repeatable access to code/document fragments without re-indexing.

### Inputs / Outputs
- Input: index_path (str), default ".repo_index.json" (UTF-8 JSON).  
- Output: List[Chunk] created from the JSON entries. Assumes the file exists and matches the Chunk schema.

### How it connects
Called by generate_docs and main to hydrate the in-memory index. Uses Path.read_text and json.loads, then maps dicts to Chunk.

### Why it matters in this project
A reliable repo index is critical for orchestrating doc generation and analysis that underpin retail promotion and recommendation workflows. It ensures consistent, fast access to code knowledge, improving system automation and traceability.

```python
def load_index(index_path: str = ".repo_index.json") -> List[Chunk]:
    data = json.loads(Path(index_path).read_text(encoding="utf-8"))
    return [Chunk(**d) for d in data]
```

