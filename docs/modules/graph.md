# `graph` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `State`

- **File:** `agents/graph.py` (lines 13-20)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Defines the shared state schema for the agent graph. It standardizes how a user query, retrieval results, selected product, recommendations, and the final response are passed between steps.

### Inputs / Outputs
- Input: user_query (str).
- Intermediate fields: retrieved (list of dicts), chosen_product_id (optional int), recommendations (list of dicts).
- Output: final (str), the composed reply.

### How it connects
Used by graph nodes to read/write consistent keys during orchestration. Each stage updates specific fields (e.g., retrieval fills retrieved; selection sets chosen_product_id; ranking populates recommendations; generation writes final).

### Why it matters in this project
A clear state contract keeps promotion and recommendation flows reliable. It enables deterministic handoffs between steps, simplifies debugging, and ensures the Copilot can turn a retail query into actionable product picks and a final answer.

```python
class State(TypedDict):
    user_query: str
    retrieved: List[Dict[str, Any]]
    chosen_product_id: Optional[int]
    recommendations: List[Dict[str, Any]]
    final: str
```


## `retrieve_node`

- **File:** `agents/graph.py` (lines 21-25)
- **Called by:** (not shown)
- **Calls:** product_semantic_search

### Purpose
Fetches relevant products for a user’s query using semantic search and stores them in the orchestration state. This seeds downstream recommendation or promotion steps with a focused candidate set.

### Inputs / Outputs
- Input: state dict-like with state["user_query"] (string).
- Output: same state plus state["retrieved"] = product_semantic_search(user_query, k=15).

### How it connects
Acts as a graph node that calls product_semantic_search and enriches the state. Downstream nodes read state["retrieved"] to rank, personalize, or apply promo logic.

### Why it matters in this project
Limits the working set to up to 15 semantically matched products, improving relevance and performance for retail recommendations and promotion orchestration.

```python
def retrieve_node(state: State) -> State:
    retrieved = product_semantic_search(state["user_query"], k=15)
    return {**state, "retrieved": retrieved}
```


## `choose_product_node`

- **File:** `agents/graph.py` (lines 26-43)
- **Called by:** (not shown)
- **Calls:** find_product_by_exact_name, lower

### Purpose
Pick a single product ID from the user’s query to drive downstream actions. Adds a canonical fallback for “banana” to avoid ambiguity and stabilize common-item handling.

### Inputs / Outputs
Inputs: state with user_query (string) and retrieved (list of product dicts).  
Outputs: same state plus chosen_product_id (product_id from exact-match bananas or first retrieved; None if no candidates).

### How it connects
Normalizes the query (lower) and, for “banana”, calls find_product_by_exact_name to prefer canonical SKUs. Otherwise, selects the top retrieved candidate. Returns an updated state used by downstream promotion/recommendation steps.

### Why it matters in this project
A reliable chosen_product_id lets promo and recommendation flows target the correct SKU. The banana fallback reduces retrieval noise for a high-frequency item, improving offer precision and orchestration stability.

```python
def choose_product_node(state: State) -> State:
    q = state["user_query"].lower()

    # Canonical fallback for common items
    if "banana" in q:
        hits = find_product_by_exact_name(["Bananas", "Organic Bananas"])
        if hits:
            return {**state, "chosen_product_id": hits[0]["product_id"]}

    # Otherwise pick best from retrieved list (existing logic)
    candidates = state["retrieved"] or []
    if not candidates:
        return {**state, "chosen_product_id": None}

    best = candidates[0]
    return {**state, "chosen_product_id": best.get("product_id")}
```


## `recommend_node`

- **File:** `agents/graph.py` (lines 44-51)
- **Called by:** (not shown)
- **Calls:** co_purchase_recommendations

### Purpose
Return co-purchase recommendations for a selected product and attach them to the shared agent state. This node powers cross-sell logic by fetching the top 10 items commonly bought with the chosen product.

### Inputs / Outputs
- Input: state dict with "chosen_product_id".
- Output: same state plus "recommendations" (list). Empty list if no product is selected; otherwise the result of co_purchase_recommendations(pid, k=10).

### How it connects
This node reads the chosen product from the graph state, calls co_purchase_recommendations, and writes the results back under "recommendations". Upstream logic must set "chosen_product_id"; downstream steps consume "recommendations" for UI, messaging, or follow-up actions.

### Why it matters in this project
Co-purchase recommendations enable targeted promotions and increase basket size. Centralizing results in the graph state keeps orchestration simple and lets other agents reuse the recommendations without re-computing them.

```python
def recommend_node(state: State) -> State:
    pid = state["chosen_product_id"]
    recs = []
    if pid is not None:
        recs = co_purchase_recommendations(int(pid), k=10)
    return {**state, "recommendations": recs}
```


## `respond_node`

- **File:** `agents/graph.py` (lines 52-85)
- **Called by:** (not shown)
- **Calls:** bundle_score, expected_impact, family_key, get_product_card, infer_theme, popular_alternatives, promo_confidence, round, score_bundle, sort, suggest_offer_type, suggest_placement

### Purpose
Turn retrieval and intent resolution results into a concise, user-facing response: the chosen product, frequently-bought-together (FBT) items, or department alternatives if affinity is weak.

### Inputs / Outputs
- Input: State dict with keys: retrieved (list of hits with text), chosen_product_id (int|None), recommendations (list with product_name, co_purchase_count).
- Output: Same state plus final (string) summarizing the chosen product and either FBT pairs or popular alternatives (with reorder_rate and units).

### How it connects
- Relies on previous steps to populate retrieved, chosen_product_id, and recommendations.
- Fetches product details via get_product_card(pid) and, if needed, department alternatives via popular_alternatives(dept_id, k=10).
- Produces the terminal text consumed by the UI/agent.

### Why it matters in this project
- Elevates cross-sell opportunities by listing FBT items with co_purchase_count for promotion targeting.
- Ensures coverage by suggesting popular same-department alternatives when affinity data is missing.
- Provides clear fallbacks so orchestration always yields an actionable recommendation message.

```python
def respond_node(state: State) -> State:
    if not state["retrieved"] and state["chosen_product_id"] is None:
        return {**state, "final": "No matching products found. Try a different query (e.g., 'banana', 'yogurt', 'almond milk')."}

    pid = state["chosen_product_id"]
    if pid is None:
        # fallback to first retrieved if chooser failed
        top = state["retrieved"][0]
        final = "Top matching product (semantic search):\n" + top["text"]
        return {**state, "final": final}

    chosen = get_product_card(int(pid))

    lines = []
    lines.append("Chosen product (after intent + canonical matching):")
    lines.append(chosen["text"])
    lines.append("")
    lines.append(f"Frequently bought together (based on basket affinity) for product_id={pid}:")

    if state["recommendations"]:
        for r in state["recommendations"][:10]:
            lines.append(f"- {r['product_name']} (co_purchase_count={r['co_purchase_count']})")
    else:
        lines.append("- No strong co-purchase pairs found in affinity table.")
        dept_id = chosen.get("department_id")
        if dept_id is not None:
            lines.append("")
            lines.append(f"Popular alternatives in the same department (department_id={dept_id}):")
            for r in popular_alternatives(int(dept_id), k=10):
                lines.append(f"- {r['product_name']} (reorder_rate={r['reorder_rate']:.3f}, units={r['total_units']})")

    return {**state, "final": "\n".join(lines)}
```


## `build_graph`

- **File:** `agents/graph.py` (lines 86-111)
- **Called by:** (not shown)
- **Calls:** StateGraph, add_edge, add_node, compile, set_entry_point

### Purpose
Builds and compiles a stateful workflow that drives the recommendation flow: retrieve → choose product → recommend → respond. Returns an executable graph for consistent, ordered execution.

### Inputs / Outputs
Inputs (state keys): user_query (string), retrieved (list), chosen_product_id (id/None), recommendations (list), final (string).  
Output: a compiled app; when invoked, it returns the updated state with final populated by the respond step.

### How it connects
Registers four nodes (retrieve_node, choose_product_node, recommend_node, respond_node) and wires them in sequence, ending at END.  
Other components call build_graph() to obtain the compiled graph and invoke it with the current state.

### Why it matters in this project
Provides clear orchestration for retail recommendations: gather relevant items, pick a product, generate suggestions, and craft the final reply.  
Keeps each step modular and auditable, improving reliability and making it easy to tune promotion and recommendation logic.

```python
def build_graph():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve_node)
    g.add_node("choose_product", choose_product_node)
    g.add_node("recommend", recommend_node)
    g.add_node("respond", respond_node)

    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "choose_product")
    g.add_edge("choose_product", "recommend")
    g.add_edge("recommend", "respond")
    g.add_edge("respond", END)

    return g.compile()


if __name__ == "__main__":
    app = build_graph()
    result = app.invoke({
        "user_query": "healthy snack like bananas",
        "retrieved": [],
        "chosen_product_id": None,
        "recommendations": [],
        "final": ""
    })
    print(result["final"])
```

