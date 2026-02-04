# agents/repo_bot/repo_chat.py
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

from agents.repo_bot.repo_index import build_index, load_index, Chunk
from agents.repo_bot.repo_trace import trace_symbol

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


def search_chunks(chunks: List[Chunk], query: str, top_k: int = 5) -> List[Tuple[int, Chunk]]:
    scored = [(simple_rank(query, c.text, c.symbol, c.path), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(s, c) for s, c in scored if s > 0][:top_k]

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


def grep_chunks(chunks: List[Chunk], keyword: str, top_k: int = 25) -> List[Chunk]:
    kw = keyword.lower()
    hits = []
    for c in chunks:
        if kw in c.text.lower():
            hits.append(c)
        if len(hits) >= top_k:
            break
    return hits


def format_chunk(c: Chunk) -> str:
    header = f"{c.path}  ({c.kind} {c.symbol})  lines {c.start_line}-{c.end_line}"
    snippet = "\n".join(c.text.splitlines()[:35])
    return f"\n---\n{header}\n{snippet}\n---\n"

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
