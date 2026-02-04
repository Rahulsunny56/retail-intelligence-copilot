# repo_trace

_Auto-generated from repo index. Run `python -m agents.repo_bot.docgen` to refresh._

### `iter_py_files`

- **File:** `agents/repo_bot/repo_trace.py` (lines 19-29)
- **Called by:** build_call_graph
- **Calls:** rglob

```python
def iter_py_files(repo_root: Path) -> List[Path]:
    files = []
    for p in repo_root.rglob("*.py"):
        if ".git" in p.parts:
            continue
        if "site" in p.parts:
            continue
        files.append(p)
    return files
```


### `CallGraph`

- **File:** `agents/repo_bot/repo_trace.py` (lines 30-84)
- **Called by:** build_call_graph
- **Calls:** (none found)

```python
class CallGraph(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.stack: List[str] = []  # nested function/class names
        self.current_func: str | None = None

        # qualified_name -> (file, lineno)
        self.defs: Dict[str, Tuple[str, int]] = {}

        # qualified_name -> set(callee_names)
        self.calls: Dict[str, Set[str]] = {}

    def _qual(self, name: str) -> str:
        return ".".join(self.stack + [name]) if self.stack else name

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qual = self._qual(node.name)
        prev = self.current_func

        self.current_func = qual
        self.defs[qual] = (self.file_path, node.lineno)
        self.calls.setdefault(qual, set())

        # push into nesting stack
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

        self.current_func = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # treat same

    def visit_ClassDef(self, node: ast.ClassDef):
        # include class names in stack so methods can be qualified too
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Call(self, node: ast.Call):
        if self.current_func is None:
            return

        callee = None
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr

        if callee and callee not in IGNORE_CALLEES:
            self.calls.setdefault(self.current_func, set()).add(callee)

        self.generic_visit(node)
```


### `CallGraph.__init__`

- **File:** `agents/repo_bot/repo_trace.py` (lines 31-41)
- **Called by:** CallGraph
- **Calls:** (none found)

```python
def __init__(self, file_path: str):
        self.file_path = file_path
        self.stack: List[str] = []  # nested function/class names
        self.current_func: str | None = None

        # qualified_name -> (file, lineno)
        self.defs: Dict[str, Tuple[str, int]] = {}

        # qualified_name -> set(callee_names)
        self.calls: Dict[str, Set[str]] = {}
```


### `CallGraph._qual`

- **File:** `agents/repo_bot/repo_trace.py` (lines 42-44)
- **Called by:** CallGraph.visit_FunctionDef
- **Calls:** (none found)

```python
def _qual(self, name: str) -> str:
        return ".".join(self.stack + [name]) if self.stack else name
```


### `CallGraph.visit_FunctionDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 45-59)
- **Called by:** CallGraph
- **Calls:** _qual, generic_visit, pop, setdefault

```python
def visit_FunctionDef(self, node: ast.FunctionDef):
        qual = self._qual(node.name)
        prev = self.current_func

        self.current_func = qual
        self.defs[qual] = (self.file_path, node.lineno)
        self.calls.setdefault(qual, set())

        # push into nesting stack
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

        self.current_func = prev
```


### `CallGraph.visit_AsyncFunctionDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 60-62)
- **Called by:** CallGraph
- **Calls:** visit_FunctionDef

```python
def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # treat same
```


### `CallGraph.visit_ClassDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 63-68)
- **Called by:** CallGraph
- **Calls:** generic_visit, pop

```python
def visit_ClassDef(self, node: ast.ClassDef):
        # include class names in stack so methods can be qualified too
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()
```


### `CallGraph.visit_Call`

- **File:** `agents/repo_bot/repo_trace.py` (lines 69-84)
- **Called by:** CallGraph
- **Calls:** generic_visit, isinstance, setdefault

```python
def visit_Call(self, node: ast.Call):
        if self.current_func is None:
            return

        callee = None
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr

        if callee and callee not in IGNORE_CALLEES:
            self.calls.setdefault(self.current_func, set()).add(callee)

        self.generic_visit(node)
```


### `build_call_graph`

- **File:** `agents/repo_bot/repo_trace.py` (lines 85-104)
- **Called by:** trace_symbol
- **Calls:** CallGraph, Path, iter_py_files, parse, read_text, relative_to, resolve, setdefault, update, visit

```python
def build_call_graph(repo_root: str) -> Tuple[Dict[str, Set[str]], Dict[str, List[str]]]:
    root = Path(repo_root).resolve()

    caller_to_callees: Dict[str, Set[str]] = {}
    callee_to_callers: Dict[str, Set[str]] = {}

    for file in iter_py_files(root):
        tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
        cg = CallGraph(str(file.relative_to(root)))
        cg.visit(tree)

        for caller, callees in cg.calls.items():
            caller_to_callees.setdefault(caller, set()).update(callees)
            for callee in callees:
                callee_to_callers.setdefault(callee, set()).add(caller)

    callee_to_callers_list = {k: sorted(list(v)) for k, v in callee_to_callers.items()}
    return caller_to_callees, callee_to_callers_list
```


### `trace_symbol`

- **File:** `agents/repo_bot/repo_trace.py` (lines 105-119)
- **Called by:** main, render_chunk_md
- **Calls:** build_call_graph, split, strip

```python
def trace_symbol(repo_root: str, symbol: str):
    caller_to_callees, callee_to_callers = build_call_graph(repo_root)

    sym = symbol.strip()
    # exact match first
    callees = sorted(list(caller_to_callees.get(sym, set())))
    callers = callee_to_callers.get(sym, [])

    # fallback: if user gave qualified name, try tail name for "called by"
    if not callees and not callers and "." in sym:
        tail = sym.split(".")[-1]
        callers = callee_to_callers.get(tail, [])
        callees = sorted(list(caller_to_callees.get(tail, set())))

    return callers, callees
```

