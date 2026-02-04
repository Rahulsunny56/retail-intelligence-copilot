# `repo_trace` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `iter_py_files`

- **File:** `agents/repo_bot/repo_trace.py` (lines 19-29)
- **Called by:** build_call_graph
- **Calls:** rglob

### Purpose
Collect all Python source files in a repository while skipping irrelevant folders. It narrows the scan to real code, reducing noise for downstream analysis like call graph building.

### Inputs / Outputs
- Input: repo_root (Path) — the repository root to scan.
- Output: List[Path] — all “.py” files under repo_root, excluding any path containing “.git” or “site”.

### How it connects
Used by build_call_graph to enumerate files before building the code graph. Internally relies on Path.rglob("*.py") and filters out non-source directories.

### Why it matters in this project
Accurate file enumeration ensures the call graph reflects actual application logic, not vendor or build artifacts. This improves system orchestration insight for Retail Intelligence Copilot, enabling reliable tracing of code paths that drive promotion and recommendation workflows.

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


## `CallGraph`

- **File:** `agents/repo_bot/repo_trace.py` (lines 30-84)
- **Called by:** build_call_graph
- **Calls:** (none)

### Purpose
Build a per-file call graph by walking Python AST. It records where functions/methods are defined and which callees they invoke, using qualified names for nested functions and class methods.

### Inputs / Outputs
- Input: file_path for the analyzed module; visit(...) is called with an AST.
- Output (on the instance): defs = {qualified_name: (file_path, lineno)}, calls = {qualified_name: set(callee_names)}.

### How it connects
Called by build_call_graph to extract function definitions and call edges from a single file. Other orchestration steps can merge these maps across files; this class itself does not call other project code.

### Why it matters in this project
Promotion and recommendation logic spans many modules. This call graph lets the copilot trace dependencies, find impact points, and orchestrate targeted analyses or runs (e.g., which pricing or offer routines call a changed function), improving reliability of retail workflows.

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


## `CallGraph.__init__`

- **File:** `agents/repo_bot/repo_trace.py` (lines 31-41)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Initialize state to build a per-file call graph. It tracks nested scopes, the currently visited function, where definitions live (file, line), and which functions call which.

### Inputs / Outputs
Input: file_path (str) of the Python source to analyze.  
Output: none returned; it prepares in-memory structures: stack (scope), current_func, defs {qualified_name -> (file, lineno)}, calls {qualified_name -> set(callee_names)}.

### How it connects
Subsequent parsing/walking code populates defs and calls using these containers. Other components can then query where a function is defined and its outbound calls to understand code flow.

### Why it matters in this project
Promotion and recommendation pipelines rely on many small functions. A precise call graph lets the copilot trace dependencies, assess impact of changes, and orchestrate targeted updates or explanations across the retail logic.

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


## `CallGraph._qual`

- **File:** `agents/repo_bot/repo_trace.py` (lines 42-44)
- **Called by:** CallGraph.visit_FunctionDef
- **Calls:** (none)

### Purpose
Build a fully qualified function name from the current traversal context. It joins the active scope stack with the function name, producing unique identifiers for call-graph nodes.

### Inputs / Outputs
- Input: name (str) — the local function/method name.
- Uses: self.stack (list[str]) — the current scope path.
- Output: str — "scope1.scope2.name" or just "name" if no scope.

### How it connects
Called by CallGraph.visit_FunctionDef to label discovered functions with stable, disambiguated names. It makes no external calls and is a pure helper for call-graph construction.

### Why it matters in this project
Accurate qualified names let us trace which promotion, pricing, or recommendation functions are invoked across nested services. This improves orchestration visibility, impact analysis, and safe rollout of changes in retail pipelines.

```python
def _qual(self, name: str) -> str:
        return ".".join(self.stack + [name]) if self.stack else name
```


## `CallGraph.visit_FunctionDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 45-59)
- **Called by:** (not shown)
- **Calls:** _qual, generic_visit, pop, setdefault

### Purpose
Handles a function definition during AST traversal and updates the call-graph state. It sets the current function context, records where the function is defined, initializes its call set, and visits its body with correct nesting.

### Inputs / Outputs
Inputs: node (ast.FunctionDef), internal state (file_path, current_func, stack).  
Outputs: Side effects only—updates defs[qual] with (file, line) and ensures calls[qual] exists; no return value.

### How it connects
Uses _qual to build a fully qualified function name, pushes the function onto a nesting stack, and calls generic_visit to traverse its body. It restores context afterward (stack.pop, current_func reset), enabling child visitors to attribute call edges to the right function.

### Why it matters in this project
An accurate call graph lets the copilot trace which code paths drive promotions and recommendations, and how modules depend on each other. This supports safe orchestration, impact analysis, and targeted assistance when modifying or routing retail logic.

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


## `CallGraph.visit_AsyncFunctionDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 60-62)
- **Called by:** (not shown)
- **Calls:** visit_FunctionDef

### Purpose
Handles async function definitions during AST traversal by treating them the same as regular functions. Ensures async code paths are included in the repository call graph.

### Inputs / Outputs
- Input: a Python AST node (ast.AsyncFunctionDef).
- Output: none directly; side effect is updating the call graph via existing function-definition logic.

### How it connects
Part of CallGraph in agents/repo_bot/repo_trace.py. Triggered when the AST visitor sees an async def, and it delegates to visit_FunctionDef to reuse the same processing pipeline.

### Why it matters in this project
Retail Intelligence Copilot may orchestrate async workflows (e.g., I/O or service calls) for promotions and recommendations. Including async functions in the call graph keeps dependency mapping complete, enabling robust orchestration and safer changes.

```python
def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # treat same
```


## `CallGraph.visit_ClassDef`

- **File:** `agents/repo_bot/repo_trace.py` (lines 63-68)
- **Called by:** (not shown)
- **Calls:** generic_visit, pop

### Purpose
Track class scope while traversing the AST so method names are fully qualified with their class. This enables precise call/trace mapping across the repository.

### Inputs / Outputs
Input: node (ast.ClassDef).  
Output: No return; side effect is pushing the class name onto a stack during traversal and popping it after, providing context for nested nodes.

### How it connects
Used by the AST visitor in repo_trace to walk Python code. Calls generic_visit to process class contents and uses a stack to maintain class context for methods and attributes.

### Why it matters in this project
Accurate, qualified method names prevent collisions across classes, allowing the Copilot to reliably map dependencies in promotion and recommendation code paths. This improves system orchestration, impact analysis, and targeted updates in retail workflows.

```python
def visit_ClassDef(self, node: ast.ClassDef):
        # include class names in stack so methods can be qualified too
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()
```


## `CallGraph.visit_Call`

- **File:** `agents/repo_bot/repo_trace.py` (lines 69-84)
- **Called by:** (not shown)
- **Calls:** generic_visit, isinstance, setdefault

### Purpose
Builds a per-function call graph entry by recording which callees are invoked inside the currently visited function. It extracts the callee name from simple names or attributes and skips any in IGNORE_CALLEES.

### Inputs / Outputs
- Input: an ast.Call node and the traversal context self.current_func.
- Output: Updates self.calls[current_func] with the callee name; then continues traversal via generic_visit to catch nested calls.

### How it connects
This is part of the CallGraph visitor in repo_bot/repo_trace.py, which statically maps function-to-function calls. That mapping helps trace which code paths participate in promotion or recommendation flows, aiding orchestration and impact analysis.

### Why it matters in this project
Retail Intelligence Copilot needs to understand dependencies to safely orchestrate promotion/recommendation logic. A precise call graph surfaces touchpoints and side effects, enabling targeted refactors, audits, and runtime coordination across promotion and recommendation components.

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


## `build_call_graph`

- **File:** `agents/repo_bot/repo_trace.py` (lines 85-104)
- **Called by:** trace_symbol
- **Calls:** CallGraph, Path, iter_py_files, parse, read_text, relative_to, resolve, setdefault, update, visit

### Purpose
Build a repository-wide static call graph by parsing Python files and aggregating which symbols call which others. Enables fast, deterministic tracing of code paths across the repo.

### Inputs / Outputs
- Input: repo_root (str) — filesystem path to the project.
- Output:
  - caller_to_callees: Dict[str, Set[str]] mapping each caller to the set of callees.
  - callee_to_callers: Dict[str, List[str]] mapping each callee to a sorted list of callers (deterministic for downstream tools).
  - Symbol strings come from CallGraph’s extraction logic.

### How it connects
Called by trace_symbol. Walks all .py files via iter_py_files, parses ASTs (ast.parse/read_text), and feeds them to CallGraph.visit. Uses Path.resolve/relative_to to normalize file context and merges results with setdefault/update.

### Why it matters in this project
Supports impact analysis and traceability for retail promotion and recommendation logic—e.g., identifying where promotion rules or ranking functions are invoked. This underpins safe system orchestration, helping the copilot explain dependencies, plan changes, and route prompts to the right components.

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


## `trace_symbol`

- **File:** `agents/repo_bot/repo_trace.py` (lines 105-119)
- **Called by:** main, render_chunk_md
- **Calls:** build_call_graph, split, strip

### Purpose
Find where a code symbol is used (its callers) and what it invokes (its callees) within the repo. Ensures deterministic ordering of callees and handles both exact and qualified symbol names by falling back to the tail name.

### Inputs / Outputs
Inputs: repo_root (path to repo), symbol (string to trace).  
Outputs: (callers, callees) — both lists of symbol names from the repository call graph.

### How it connects
Called by main and render_chunk_md to surface call relationships in CLI and generated Markdown. Internally uses build_call_graph, plus simple string strip/split to normalize and fallback on qualified names.

### Why it matters in this project
Knowing who calls what lets us safely change promotion logic, recommendation flows, or orchestration steps without breaking downstream components. It supports impact analysis, explainability, and accurate documentation of agent interactions in Retail Intelligence Copilot.

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

