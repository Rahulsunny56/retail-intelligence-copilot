# `repo_chat` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `parse_command`

- **File:** `agents/repo_bot/repo_chat.py` (lines 12-32)
- **Called by:** main
- **Calls:** endswith, lower, startswith, strip

### Purpose
Parse a user’s repo-bot command into a deterministic mode and argument. It normalizes input and detects explicit modes or a backtick shortcut to drive repository analysis actions.

### Inputs / Outputs
- Input: user_input (str)
- Output: (mode, arg) where mode ∈ {"explain", "trace", "where", "ask"} and arg is the remaining text (or "")

### How it connects
Called by main to route user intent to the right handler. Uses simple string ops (strip, lower, startswith, endswith) to avoid ambiguity and external dependencies.

### Why it matters in this project
Clear command parsing lets the copilot reliably switch between repo analysis modes, improving orchestration. This speeds up diagnosing and explaining code that underpins retail promotions and recommendations, enabling faster, safer iteration.

```python
def parse_command(user_input: str) -> tuple[str, str]:
    """
    Returns (mode, arg)
    mode in {"explain", "trace", "where", "ask"}
    """
    s = user_input.strip()
    if not s:
        return ("ask", "")

    low = s.lower()
    for cmd in ("explain", "trace", "where"):
        if low.startswith(cmd + " "):
            return (cmd, s[len(cmd) + 1 :].strip())

    # Backticks shortcut: `symbol` behaves like explain
    if s.startswith("`") and s.endswith("`") and len(s) > 2:
        return ("explain", s.strip("`").strip())

    return ("ask", s)
```


## `pick_target_symbol`

- **File:** `agents/repo_bot/repo_chat.py` (lines 33-50)
- **Called by:** main
- **Calls:** (none)

### Purpose
Select the most relevant code symbol for a repo chat query by preferring exact/contained matches (e.g., "respond_node.bundle_score") from already retrieved results, with a fallback to the full index.

### Inputs / Outputs
- Inputs: query (str), top_matches (List of (score, Chunk)).
- Output: symbol name (str).
- Notes: Fallback scan uses a global all_chunks index; matching is substring-based on chunk.symbol.

### How it connects
Called by main. It does not call other project functions. It first searches the provided top_matches, then falls back to scanning all_chunks to find a matching symbol.

### Why it matters in this project
Accurately mapping a natural-language query to the right code symbol keeps repo chat grounded. This sharp targeting improves explanations and troubleshooting for promotion rules, recommendation logic, and orchestration components in Retail Intelligence Copilot.

```python
def pick_target_symbol(query: str, top_matches: List[Tuple[int, Chunk]]) -> str:
    """
    Choose the most relevant symbol from top matches based on query text.
    Prefer an exact (or contained) symbol match like 'respond_node.bundle_score'.
    """
    def pick(sym_contains: str) -> Chunk | None:
    # 1) Prefer chunks already retrieved in top matches
        for _, c in top_matches:
            if sym_contains in c.symbol.lower():
                return c
        # 2) Fallback: scan full index
        for c in all_chunks:
            if sym_contains in c.symbol.lower():
                return c
        return None
```


## `pick_target_symbol.pick`

- **File:** `agents/repo_bot/repo_chat.py` (lines 38-50)
- **Called by:** (not shown)
- **Calls:** lower

### Purpose
Select the first code chunk whose symbol contains a given substring, preferring already-retrieved top matches and falling back to a full index. This accelerates symbol resolution during repo chat operations.

### Inputs / Outputs
- Input: sym_contains (str) — substring to match; compared against c.symbol.lower() (caller should pass lowercase for case-insensitive search).
- Output: Chunk | None — first matching chunk, or None if not found.

### How it connects
Lives in agents/repo_bot/repo_chat.py as pick_target_symbol.pick. Reads from top_matches (pre-ranked results) and all_chunks (full index) defined elsewhere, and uses str.lower() for matching.

### Why it matters in this project
Fast, deterministic symbol picking lets the Repo Bot route actions (inspect, summarize, or modify code) to the correct unit with minimal latency. This supports reliable orchestration when diagnosing or evolving promotion/recommendation logic in Retail Intelligence Copilot.

```python
def pick(sym_contains: str) -> Chunk | None:
    # 1) Prefer chunks already retrieved in top matches
        for _, c in top_matches:
            if sym_contains in c.symbol.lower():
                return c
        # 2) Fallback: scan full index
        for c in all_chunks:
            if sym_contains in c.symbol.lower():
                return c
        return None
```


## `simple_rank`

- **File:** `agents/repo_bot/repo_chat.py` (lines 51-80)
- **Called by:** search_chunks
- **Calls:** lower, startswith

### Purpose
Rank a repository chunk against a user query so search_chunks can surface the most relevant code/docs. It biases results toward parts of the system used for promotions, recommendations, and orchestration.

### Inputs / Outputs
- Inputs: Chunk (with text, symbol, path) and a query string.
- Output: Integer relevance score combining keyword hits and path-based boosts/penalties.

### How it connects
Called by search_chunks to sort candidates. It normalizes case with lower() and checks paths with startswith() to penalize repo_bot internals and boost promo/graph/tools/sql/rag content.

### Why it matters in this project
By prioritizing agents/promo_agent.py, agents/tools.py, agents/graph.py, sql/, and rag/, it elevates code and data most useful for building promotions, product recommendations, and orchestration flows, while downranking internal repo_bot code that isn’t helpful to end tasks.

```python
def simple_rank(chunk: Chunk, query: str) -> int:
    score = 0
    q = query.lower()
    text = chunk.text.lower()
    symbol = (chunk.symbol or "").lower()
    path = chunk.path.lower()

    # keyword relevance
    if q in text:
        score += 50
    if q in symbol:
        score += 80

    # ✅ FIX #1 GOES HERE
    if path.startswith("agents/repo_bot/"):
        score -= 500

    BOOST_PATHS = (
        "agents/promo_agent.py",
        "agents/tools.py",
        "agents/graph.py",
        "sql/",
        "rag/",
    )
    if path.startswith(BOOST_PATHS):
        score += 600

    return score
```


## `search_chunks`

- **File:** `agents/repo_bot/repo_chat.py` (lines 81-85)
- **Called by:** main
- **Calls:** simple_rank, sort

### Purpose
Ranks repository chunks against a user query and returns the top matches.  
Used to quickly surface relevant code/config when the Copilot needs context.

### Inputs / Outputs
Inputs: chunks (List[Chunk]), query (str), top_k (int, default 5).  
Outputs: List of (score, chunk) tuples, filtered to positive scores and limited to top_k.

### How it connects
Called by main to fetch the most relevant repo chunks for a query.  
Internally calls simple_rank for scoring and uses sort to order results.

### Why it matters in this project
Enables the Copilot to find code that governs promotions, recommendations, and orchestration logic.  
Grounded retrieval improves accuracy when assembling or explaining retail workflows.

```python
def search_chunks(chunks: List[Chunk], query: str, top_k: int = 5) -> List[Tuple[int, Chunk]]:
    scored = [(simple_rank(query, c.text, c.symbol, c.path), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(s, c) for s, c in scored if s > 0][:top_k]
```


## `find_by_symbol`

- **File:** `agents/repo_bot/repo_chat.py` (lines 86-104)
- **Called by:** main
- **Calls:** endswith, lower, strip

### Purpose
Find code/documentation chunks by symbol name, prioritizing exact matches and then partial matches. This lets the repo bot quickly resolve a user’s symbol query to the relevant code context.

### Inputs / Outputs
- Inputs: chunks (List[Chunk]), symbol_query (str), top_k (int, default 5).
- Output: up to top_k matching Chunk objects, case-insensitive; empty if query is blank or nothing matches.
- Behavior: trims whitespace, exact match first; otherwise contains/endswith partials.

### How it connects
Called by main to map a user’s symbol request to indexed chunks. Uses simple string ops (strip, lower, endswith) and returns results for downstream display/analysis steps.

### Why it matters in this project
Fast, precise symbol lookup helps the Copilot surface the right code for promotion logic, recommendation flows, or orchestration tasks. This reduces noise and accelerates fixes or changes in retail workflows.

```python
def find_by_symbol(chunks: List[Chunk], symbol_query: str, top_k: int = 5) -> List[Chunk]:
    q = symbol_query.strip().lower()
    if not q:
        return []
    exact = [c for c in chunks if c.symbol.lower() == q]
    if exact:
        return exact[:top_k]

    # partial match (contains / endswith)
    hits = []
    for c in chunks:
        sym = c.symbol.lower()
        if q in sym or sym.endswith(q):
            hits.append(c)
            if len(hits) >= top_k:
                break
    return hits
```


## `grep_chunks`

- **File:** `agents/repo_bot/repo_chat.py` (lines 105-115)
- **Called by:** main
- **Calls:** lower

### Purpose
Perform a case-insensitive grep over repository chunks to find where a keyword appears. Returns up to top_k matches, enabling quick narrowing of relevant repo content for the chat agent.

### Inputs / Outputs
- Inputs: chunks (List[Chunk] with .text), keyword (str), top_k (int, default 25).
- Output: List[Chunk] containing matches in input order, stopping after top_k.

### How it connects
Called by main to fetch relevant repo snippets for a user query. Internally only uses lower() for case-insensitive matching.

### Why it matters in this project
Quickly surfaces code/docs related to promotions, recommendation logic, or orchestration flows. This speeds the Copilot’s ability to answer, guide changes, or trigger workflows without scanning the entire repository.

```python
def grep_chunks(chunks: List[Chunk], keyword: str, top_k: int = 25) -> List[Chunk]:
    kw = keyword.lower()
    hits = []
    for c in chunks:
        if kw in c.text.lower():
            hits.append(c)
        if len(hits) >= top_k:
            break
    return hits
```


## `format_chunk`

- **File:** `agents/repo_bot/repo_chat.py` (lines 116-120)
- **Called by:** main
- **Calls:** splitlines

### Purpose
Format a repository chunk into a compact, readable string with metadata and a short snippet. This aids presenting code context clearly during repo chat interactions.

### Inputs / Outputs
- Input: Chunk c with path, kind, symbol, start_line, end_line, and text.
- Output: A string delimited by --- containing a header and the first 35 lines of c.text.

### How it connects
Called by main in agents/repo_bot/repo_chat.py to render chunks; internally uses splitlines to cap the snippet length. Provides consistent formatting for downstream display or processing.

### Why it matters in this project
Concise, structured code snippets keep prompts lean and scannable, improving context quality for the Copilot. This helps quicker understanding and safer changes to promotion logic, recommendation flows, and orchestration components in Retail Intelligence Copilot.

```python
def format_chunk(c: Chunk) -> str:
    header = f"{c.path}  ({c.kind} {c.symbol})  lines {c.start_line}-{c.end_line}"
    snippet = "\n".join(c.text.splitlines()[:35])
    return f"\n---\n{header}\n{snippet}\n---\n"
```


## `explain_symbol`

- **File:** `agents/repo_bot/repo_chat.py` (lines 121-163)
- **Called by:** main
- **Calls:** endswith, replace, splitlines, strip

### Purpose
Generate a concise, human-readable explainer for a code symbol using its source chunk and simple call graph. It summarizes what the function is/does and, when relevant, clarifies bundle scoring and synergy logic used for promotions.

### Inputs / Outputs
- Inputs: query (unused), chunk (with symbol, path, text), callers, callees.  
- It derives a signature from the first line of chunk.text using splitlines/strip/replace.  
- Output: a newline-joined Markdown string with “What it is/does” and connection info.

### How it connects
- Called by: main.  
- Calls: endswith, replace, splitlines, strip for lightweight parsing.  
- It embeds callers/callees to show how the symbol fits into the codebase.

### Why it matters in this project
- If the symbol name includes bundle_score or the code mentions “synergy,” it explains bundle ranking: relevance to anchor + co-purchase synergy.  
- It notes that respond_node uses this score to rank and show Top 3 promo bundles, improving transparency for promotion and recommendation orchestration.

```python
def explain_symbol(query: str, chunk: Chunk, callers: list[str], callees: list[str]) -> str:
    """
    Turns a code chunk + call graph into a human explanation.
    """
    sym = chunk.symbol
    path = chunk.path

    # naive parameter extraction for display
    first_line = chunk.text.splitlines()[0].strip()
    signature = first_line.replace("def ", "").replace(":", "")

    lines = []
    lines.append(f"✅ What it is")
    lines.append(f"- `{sym}` is a function in `{path}`.")
    lines.append(f"- Signature: `{signature}`")

    lines.append("")
    lines.append(f"✅ What it does (simple)")
    if "synergy" in chunk.text:
        lines.append("- It scores a bundle (2 add-on products) by combining:")
        lines.append("  1) relevance score of add-on A vs anchor")
        lines.append("  2) relevance score of add-on B vs anchor")
        lines.append("  3) synergy bonus from co-purchase counts")
    else:
        lines.append("- It performs logic defined in the code snippet shown.")

    lines.append("")
    lines.append("✅ How it’s connected in your project")
    if callers:
        lines.append(f"- Called by: {', '.join(callers)}")
    if callees:
        lines.append(f"- Calls: {', '.join(callees)}")

    # Project-specific helpful interpretation
    if sym.endswith("bundle_score") or "bundle_score" in sym:
        lines.append("")
        lines.append("✅ Why it matters for promotions")
        lines.append("- `respond_node` uses this score to rank all possible bundles (Anchor + 2 items).")
        lines.append("- Higher score → bundle is shown in “Top 3 promo bundles”.")
        lines.append("- Synergy ensures bundles where BOTH add-ons strongly co-occur with the anchor rank higher.")

    return "\n".join(lines)
```


## `explain_concept_product_id`

- **File:** `agents/repo_bot/repo_chat.py` (lines 164-222)
- **Called by:** main
- **Calls:** find_chunk

### Purpose
Generate a project-aware explanation of product_id and how it drives promo recommendations. It builds a concise, Markdown summary grounded in actual code locations when available.

### Inputs / Outputs
- Inputs: all_chunks (repo index of Chunk), top_matches (ranked Chunk hits).
- Output: A single Markdown string describing product_id, its end-to-end promo flow, code references, and a simple SQL join pattern.
- Behavior: Prefers symbols from top_matches, then falls back to scanning all_chunks under agents/.

### How it connects
- Called by: main.
- Calls: an internal find_chunk to resolve get_product_card, promo_candidates, co_purchase_recommendations in agents/.
- Embeds resolved paths in the text so downstream UI can show where product_id is used.

### Why it matters in this project
It ties the retail promotion workflow to real code: anchor selection, product card retrieval, co-purchase candidate generation, and bundle scoring. This keeps explanations consistent, actionable, and aligned with the system’s orchestration around product_id.

```python
def explain_concept_product_id(all_chunks: list[Chunk], top_matches: list[tuple[int, Chunk]]) -> str:
    """
    Project-aware explanation for product_id: what it is + how it's used in promo recommendations.
    Robust lookup: checks top_matches first, then scans the whole index.
    """
    def find_chunk(symbol_contains: str) -> Chunk | None:
        # 1) Prefer top matches
        for _, c in top_matches:
            if symbol_contains in c.symbol.lower() and c.path.startswith("agents/"):
                return c
        # 2) Fallback: full index scan
        for c in all_chunks:
            if symbol_contains in c.symbol.lower() and c.path.startswith("agents/"):
                return c
        return None

    get_card = find_chunk("get_product_card")
    promo_cands = find_chunk("promo_candidates")
    co_purch = find_chunk("co_purchase_recommendations")

    lines = []
    lines.append("✅ What is `product_id` (in your project)")
    lines.append("- `product_id` is the unique identifier for a product/SKU in your dataset.")
    lines.append("- Think of it like a **primary key** that links your tables + features + recommendations.")

    lines.append("")
    lines.append("✅ How it helps promotion recommendations (end-to-end flow)")
    lines.append("1) **Anchor selection**: you first pick an anchor product (the SKU you want to promote).")
    lines.append("2) **Fetch product details**: `product_id` is used to load a product card (name, aisle, reorder_rate, units).")
    lines.append("3) **Get bundle candidates**: `product_id` is used to query your co-purchase/affinity table to find products often bought together.")
    lines.append("4) **Bundle scoring**: those candidate products are scored and combined into top promo bundles.")

    lines.append("")
    lines.append("✅ Where it appears in code (most relevant functions)")
    if get_card:
        lines.append(f"- Product details (anchor card): `{get_card.path}::{get_card.symbol}`")
    if promo_cands:
        lines.append(f"- Candidate generation (add-ons): `{promo_cands.path}::{promo_cands.symbol}`")
    if co_purch:
        lines.append(f"- Co-purchase retrieval (affinity): `{co_purch.path}::{co_purch.symbol}`")

    # If any are missing, print a helpful hint
    missing = []
    if not get_card: missing.append("get_product_card")
    if not promo_cands: missing.append("promo_candidates")
    if not co_purch: missing.append("co_purchase_recommendations")
    if missing:
        lines.append("")
        lines.append(f"⚠️ Note: couldn’t locate in index: {', '.join(missing)} (check symbol names or indexing).")

    lines.append("")
    lines.append("✅ How the SQL/table join works (simple)")
    lines.append("- Your affinity table stores product pairs like: `product_id_a`, `product_id_b`, `co_purchase_count`.")
    lines.append("- When you pass an anchor `product_id`, you select rows where it appears in A or B,")
    lines.append("  then join the `other_id` to the `products` table to get the product name/details.")

    return "\n".join(lines)
```


## `explain_concept_product_id.find_chunk`

- **File:** `agents/repo_bot/repo_chat.py` (lines 169-222)
- **Called by:** (not shown)
- **Calls:** lower, startswith

### Purpose
Helper to find a repo index Chunk whose symbol contains a given substring within the agents/ folder. It powers the product_id explainer by linking to real functions used in promotions and recommendations.

### Inputs / Outputs
- Input: symbol_contains (str)
- Output: Chunk or None
- Behavior: Prefer matches from top_matches, then scan all_chunks; case-insensitive symbol check via lower(), and path filter via startswith("agents/").

### How it connects
It resolves get_product_card, promo_candidates, and co_purchase_recommendations into concrete code locations. Those links are embedded in the generated explanation; if not found, a warning line is added.

### Why it matters in this project
Grounding the product_id narrative in actual code anchors the promotion flow: product details, candidate generation, and co-purchase retrieval. This reduces guesswork and improves orchestration across agents for retail promotions and recommendations.

```python
def find_chunk(symbol_contains: str) -> Chunk | None:
        # 1) Prefer top matches
        for _, c in top_matches:
            if symbol_contains in c.symbol.lower() and c.path.startswith("agents/"):
                return c
        # 2) Fallback: full index scan
        for c in all_chunks:
            if symbol_contains in c.symbol.lower() and c.path.startswith("agents/"):
                return c
        return None

    get_card = find_chunk("get_product_card")
    promo_cands = find_chunk("promo_candidates")
    co_purch = find_chunk("co_purchase_recommendations")

    lines = []
    lines.append("✅ What is `product_id` (in your project)")
    lines.append("- `product_id` is the unique identifier for a product/SKU in your dataset.")
    lines.append("- Think of it like a **primary key** that links your tables + features + recommendations.")

    lines.append("")
    lines.append("✅ How it helps promotion recommendations (end-to-end flow)")
    lines.append("1) **Anchor selection**: you first pick an anchor product (the SKU you want to promote).")
    lines.append("2) **Fetch product details**: `product_id` is used to load a product card (name, aisle, reorder_rate, units).")
    lines.append("3) **Get bundle candidates**: `product_id` is used to query your co-purchase/affinity table to find products often bought together.")
    lines.append("4) **Bundle scoring**: those candidate products are scored and combined into top promo bundles.")

    lines.append("")
    lines.append("✅ Where it appears in code (most relevant functions)")
    if get_card:
        lines.append(f"- Product details (anchor card): `{get_card.path}::{get_card.symbol}`")
    if promo_cands:
        lines.append(f"- Candidate generation (add-ons): `{promo_cands.path}::{promo_cands.symbol}`")
    if co_purch:
        lines.append(f"- Co-purchase retrieval (affinity): `{co_purch.path}::{co_purch.symbol}`")

    # If any are missing, print a helpful hint
    missing = []
    if not get_card: missing.append("get_product_card")
    if not promo_cands: missing.append("promo_candidates")
    if not co_purch: missing.append("co_purchase_recommendations")
    if missing:
        lines.append("")
        lines.append(f"⚠️ Note: couldn’t locate in index: {', '.join(missing)} (check symbol names or indexing).")

    lines.append("")
    lines.append("✅ How the SQL/table join works (simple)")
    lines.append("- Your affinity table stores product pairs like: `product_id_a`, `product_id_b`, `co_purchase_count`.")
    lines.append("- When you pass an anchor `product_id`, you select rows where it appears in A or B,")
    lines.append("  then join the `other_id` to the `products` table to get the product name/details.")

    return "\n".join(lines)
```


## `main`

- **File:** `agents/repo_bot/repo_chat.py` (lines 223-390)
- **Called by:** (not shown)
- **Calls:** ArgumentParser, Document, HuggingFaceEmbeddings, Path, PersistentClient, add_argument, apply, build_index, connect, count, cwd, execute, exists, explain_concept_product_id, explain_concept_promo_agent, explain_symbol, find_by_symbol, findall, format_chunk, from_documents, get_collection, grep_chunks, group, input, iterrows, load_csv, load_index, lower, next, parse_args, parse_command, persist, pick_target_symbol, read_parquet, read_sql, rmtree, search, search_chunks, split, strip, text, to_parquet, trace_symbol

### Purpose
Interactive CLI to chat with the codebase using a prebuilt repo index. It explains symbols, traces caller/callee flows, and greps keywords. Special handlers surface concepts tied to promo_agent and product_id.

### Inputs / Outputs
Inputs: command-line flags (--reindex, --index) and interactive commands/questions (ask, where, trace, explain).  
Outputs: console prints of top matches, best-match code chunk, call graph (callers/callees), grep hits, and tailored explanations for promo_agent/product_id.

### How it connects
Orchestrates indexing and search utilities: build_index/load_index, search_chunks/grep_chunks/find_by_symbol, trace_symbol, format_chunk, pick_target_symbol. Uses explain_symbol and domain explainers (explain_concept_promo_agent, explain_concept_product_id) to produce focused answers, working against the repo at Path.cwd().

### Why it matters in this project
Lets engineers quickly locate and understand promotion and recommendation code paths, including how promo agents interact and where product_id flows through the system. Speeds debugging and change planning by exposing call graphs and usage hotspots, improving orchestration across Retail Intelligence Copilot components.

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true", help="Rebuild repo index")
    ap.add_argument("--index", default=".repo_index.json", help="Path to index json")
    args = ap.parse_args()

    repo_root = str(Path.cwd())

    if args.reindex or not Path(args.index).exists():
        stats = build_index(repo_root, args.index)
        print(f"✅ Index built: {args.index}")

    chunks = load_index(args.index)
    print("Repo Chat (MVP). Ask questions about your code. Type 'exit' to quit.\n")

    print("Commands:")
    print("  explain <symbol>   - show and explain a function/class")
    print("  trace <symbol>     - show caller/callee connections")
    print("  where <keyword>    - show where a keyword appears")
    print("  Or ask normally in English. Type 'exit' to quit.\n")

    while True:
        raw = input("You> ").strip()
        if raw.lower() in {"exit", "quit"}:
            break

        mode, arg = parse_command(raw)
        if mode == "ask" and "promo_agent" in raw.lower():
            print("\n" + explain_concept_promo_agent(chunks) + "\n")
            continue

            # --- WHERE: keyword search ---
        if mode == "where":
            keyword = arg
            hits = grep_chunks(chunks, keyword, top_k=25)
            if not hits:
                print(f"No matches for '{keyword}'.\n")
                continue

            print(f"\nWhere '{keyword}' appears (top {min(len(hits),25)}):")
            for h in hits[:25]:
                print(f"- {h.path}::{h.symbol}  lines {h.start_line}-{h.end_line}")
            print("")
            continue

        # --- TRACE: connections only ---
        if mode == "trace":
            sym = arg
            # find best chunk by symbol name
            sym_hits = find_by_symbol(chunks, sym, top_k=5)
            target = sym_hits[0] if sym_hits else None
            target_symbol = target.symbol if target else sym

            callers, callees = trace_symbol(str(Path.cwd()), target_symbol)

            # nested fallback: respond_node.bundle_score => called by respond_node
            if not callers and "." in target_symbol:
                callers = [target_symbol.split(".")[0]]

            print(f"\nConnections for: {target_symbol}")
            print("  Called by:", ", ".join(callers) if callers else "(not found)")
            print("  Calls:", ", ".join(callees) if callees else "(none found)")
            print("")
            continue

        # --- EXPLAIN: show chunk + connections + explanation template ---
        if mode == "explain":
            sym = arg
            sym_hits = find_by_symbol(chunks, sym, top_k=5)
            if not sym_hits:
                # fallback to semantic-ish keyword search
                top = search_chunks(chunks, sym, top_k=5)
                if not top:
                    print(f"Couldn't find symbol '{sym}'. Try `where {sym}`.\n")
                    continue
                target_chunk = top[0][1]
            else:
                target_chunk = sym_hits[0]

            callers, callees = trace_symbol(str(Path.cwd()), target_chunk.symbol)
            if not callers and "." in target_chunk.symbol:
                callers = [target_chunk.symbol.split(".")[0]]

            print("\nBest match details:")
            print(format_chunk(target_chunk))

            print(f"\nConnections for: {target_chunk.symbol}")
            print("  Called by:", ", ".join(callers) if callers else "(not found)")
            print("  Calls:", ", ".join(callees) if callees else "(none found)")

            # If it’s a concept arguestion (product_id), reuse your special explainer
            if "product_id" in raw.lower():
                # you already added this earlier
                print("\n" + explain_concept_product_id(chunks, [(1, target_chunk)]) + "\n")
            else:
                print("\n" + explain_symbol(raw, target_chunk, callers, callees) + "\n")

            continue

        mode, arg = parse_command(raw)



        # Heuristic: if user uses backticks or asks "where", do grep too
        keyword = None
        m = re.search(r"`([^`]+)`", arg)
        if m:
            keyword = m.group(1)
        # If question contains a likely code symbol, grep it automatically
            if keyword is None:
                # pick first token that looks like a python identifier
                for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", q):
                    if tok in {"product_id", "bundle_score", "score_bundle", "respond_node", "promo_candidates"}:
                        keyword = tok
                        break

            # last token as keyword fallback
            toks = [t for t in re.split(r"\s+", q) if t]
            if toks:
                keyword = toks[-1]

        top = search_chunks(chunks, raw, top_k=5)
        if "product_id" in arg.lower():
            print("\n" + explain_concept_product_id(chunks,top) + "\n")
            continue
        # pick the most relevant symbol chunk to display (not always the top scored one)
        target_symbol = pick_target_symbol(arg, top)
        target_chunk = next((c for _, c in top if c.symbol == target_symbol), top[0][1])
        if not top:
            print("No strong matches. Try a different keyword (e.g., function name).\n")
            continue

        print("\nTop matches:")
        for s, c in top:
            print(f"- score={s}  {c.path}::{c.symbol}  ({c.kind})")

        print("\nBest match details:")
        print(format_chunk(target_chunk))


        # If user asks "connect" or "connected" or "flow", show call graph
        if any(w in arg.lower() for w in ["connect", "connected", "flow", "calls", "called"]):
            # choose best symbol from top match
            target_symbol = pick_target_symbol(arg, top)
            callers, callees = trace_symbol(str(Path.cwd()), target_symbol)
            if not callers and "." in target_symbol:
              callers = [target_symbol.split(".")[0]]
            print(f"\nConnections for: {target_symbol}")
            print("\n" + explain_symbol(arg, target_chunk, callers, callees) + "\n")
            if callers:
                print("  Called by:", ", ".join(callers[:12]))
            else:
                print("  Called by: (not found / maybe nested / dynamic)")

            if callees:
                print("  Calls:", ", ".join(callees[:12]))
            else:
                print("  Calls: (none found)")

        if keyword:
            hits = grep_chunks(chunks, keyword, top_k=5)
            if hits:
                print(f"\nGrep hits for '{keyword}':")
                for h in hits:
                    print(f"- {h.path}::{h.symbol} lines {h.start_line}-{h.end_line}")

        print("\nTip: Ask like: `bundle_score` or `product_id` or 'explain respond_node flow'\n")
```


## `explain_concept_promo_agent`

- **File:** `agents/repo_bot/repo_chat.py` (lines 391-417)
- **Called by:** main
- **Calls:** next

### Purpose
Generate a concise Markdown explainer for promo_agent, describing how promotion bundle recommendations (anchor + 2 items) are produced. It’s used to communicate the promo flow to users of the repository chat.

### Inputs / Outputs
- Input: all_chunks (list[Chunk]); it looks for the promo_agent file chunk but does not use it further.
- Output: A Markdown string summarizing promo_agent’s role, flow, and file locations.

### How it connects
Called by main; internally uses next to search for agents/promo_agent.py in the provided chunks. It does not execute promo logic—only returns a curated description referencing promo_agent, tools, and graph modules.

### Why it matters in this project
Gives a clear, quick reference for how promo bundles are formed (anchor selection, co‑purchase candidates, scoring, top 3 diverse bundles). Improves explainability and orchestration of the Retail Intelligence Copilot’s promotion recommendation workflow.

```python
def explain_concept_promo_agent(all_chunks: list[Chunk]) -> str:
    promo_file = next((c for c in all_chunks if c.path == "agents/promo_agent.py" and c.kind == "file"), None)

    lines = []
    lines.append("✅ What is `promo_agent` in your project")
    lines.append("- `promo_agent` is the agent responsible for creating **promotion bundle recommendations** (Anchor + 2 items).")
    lines.append("- It takes a user query, selects an anchor product, pulls co-purchase candidates, scores bundles, and returns the top promo bundles.")

    lines.append("")
    lines.append("✅ Core flow (high level)")
    lines.append("1) Retrieve products related to the user query (semantic search / lookup).")
    lines.append("2) Choose an **anchor product_id** (the main item to promote).")
    lines.append("3) Load anchor product card (name, aisle, department, reorder_rate, units).")
    lines.append("4) Pull candidate add-ons using co-purchase affinity (`feat_basket_affinity`).")
    lines.append("5) Score candidates + score pairs using `bundle_score` and helper functions.")
    lines.append("6) Return top 3 diverse bundles + explanation text.")

    lines.append("")
    lines.append("✅ Where it lives")
    lines.append("- Main module: `agents/promo_agent.py`")
    lines.append("- Support tools: `agents/tools.py` (product card + co-purchase candidates)")
    lines.append("- Graph wiring: `agents/graph.py` (connects nodes into an agent flow)")

    return "\n".join(lines)

if __name__ == "__main__":
    main()
```

