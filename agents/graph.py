from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from agents.tools import (
    product_semantic_search,
    co_purchase_recommendations,
    popular_alternatives,
    find_product_by_exact_name,
    get_product_card,
)


class State(TypedDict):
    user_query: str
    retrieved: List[Dict[str, Any]]
    chosen_product_id: Optional[int]
    recommendations: List[Dict[str, Any]]
    final: str


def retrieve_node(state: State) -> State:
    retrieved = product_semantic_search(state["user_query"], k=15)
    return {**state, "retrieved": retrieved}


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


def recommend_node(state: State) -> State:
    pid = state["chosen_product_id"]
    recs = []
    if pid is not None:
        recs = co_purchase_recommendations(int(pid), k=10)
    return {**state, "recommendations": recs}


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
