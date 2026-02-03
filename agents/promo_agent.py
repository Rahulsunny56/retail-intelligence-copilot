"""
Promo Agent responsible for generating bundle-based promotion recommendations.

This module implements the core logic for:
- Selecting candidate add-on products using co-purchase affinity
- Scoring multi-item bundles using relevance, synergy, and diversity constraints
- Producing both human-readable promotional explanations and structured
  outputs for downstream UI or API consumption
"""
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from itertools import combinations

from agents.tools import (
    product_semantic_search,
    get_product_card,
    promo_candidates,
    search_products_by_name,
)
import re

def family_key(name: str) -> str:
    """
    Normalize product names into a 'family' so bundles don't include
    avocado+avocado, banana+bananas, yogurt+yogurt, etc.
    """
    n = (name or "").lower()

    # strong family buckets
    if "avocado" in n:
        return "avocado"
    if "banana" in n:
        return "banana"
    if "milk" in n:
        return "milk"
    if "yogurt" in n:
        return "yogurt"
    if "egg" in n:
        return "eggs"
    if "spinach" in n:
        return "spinach"
    if "strawberr" in n:
        return "strawberries"

    # fallback: remove common adjectives and normalize
    n = re.sub(
        r"\b(organic|whole|reduced|fat|free|range|large|grade|nonfat|lowfat|greek|strained|with|and|bag|of)\b",
        "",
        n,
    )
    n = re.sub(r"[^a-z\s]", " ", n)
    n = " ".join(w for w in n.split() if len(w) > 2)

    return n[:30] if n else "other"

def infer_theme(anchor_name: str, add_on_names: list[str]) -> str:
    a = (anchor_name or "").lower()
    items = " ".join([n.lower() for n in add_on_names if n])

    # ✅ Anchor-first rules (most important)
    if "yogurt" in a:
        return "Healthy Breakfast / Smoothie"

    if "egg" in a or "eggs" in a:
        # Eggs: always breakfast theme
        return "Breakfast Essentials"
    if "avocado" in a:
        # Most avocado promos are meal prep / guac / cooking
        return "Fresh Prep / Cooking (Guac & Sides)"

    # ✅ Item-driven rules (only if anchor is not yogurt/eggs)
    if any(k in items for k in ["avocado", "lime", "lemon", "cilantro", "onion"]):
        return "Fresh Prep / Cooking (Guac & Sides)"

    if any(k in items for k in ["banana", "strawberr", "blueberr", "raspberr", "spinach", "almond milk"]):
        return "Healthy Breakfast / Smoothie"

    if any(k in items for k in ["sparkling water", "chips", "cookies", "soda"]):
        return "Snack & Beverage"

    return "Everyday Staples"

def discount_from_affinity(min_aff: int) -> str:
    """
    Calibrated for Instacart affinity ranges:
    - yogurt/eggs pairs often 1k–9k
    - produce staples can be 20k–60k+
    """
    if min_aff >= 30000:
        return "Save $1"   # very strong natural pairing → small discount
    if min_aff >= 10000:
        return "Save $2"
    if min_aff >= 4000:
        return "Save $3"
    return "Save $4"       # weaker pairing → bigger incentive

def promo_confidence(min_aff: int) -> str:
    if min_aff >= 20000:
        return "High"
    if min_aff >= 6000:
        return "Medium"
    return "Low"

def expected_impact(anchor: dict, min_aff: int) -> str:
    rr = float(anchor.get("reorder_rate", 0.0))
    units = int(anchor.get("total_units", 0))

    if rr < 0.60:
        return "Trial driver (increase conversion for low-repeat shoppers)"
    if min_aff >= 20000 and units >= 50000:
        return "Basket builder (high-likelihood attach; lift AOV)"
    if min_aff >= 6000:
        return "Attach-rate lift (strong pairing; modest discount works)"
    return "Discovery assist (bundle helps shoppers find complementary items)"


def suggest_offer_type(anchor: dict, a: dict, b: dict) -> str:
    rr = float(anchor.get("reorder_rate", 0.0))
    units = int(anchor.get("total_units", 0))
    min_aff = min(int(a.get("co_purchase_count", 0)), int(b.get("co_purchase_count", 0)))
    save = discount_from_affinity(min_aff)

    if rr < 0.60:
        return "BOGO: Buy 1 get 1 50% off (trial driver)"

    if units >= 50000:
        return f"Bundle Discount: Buy anchor + 2 add-ons, {save}"

    return f"Bundle Discount: Buy anchor + 1 add-on, {save}"

def suggest_placement(theme: str) -> list[str]:
    """
    Where to show this promo for best conversion.
    """
    t = theme.lower()
    if "smoothie" in t or "breakfast" in t:
        return ["Cart upsell", "Product detail page (PDP)", "Weekly deals email/app banner"]
    if "cooking" in t or "prep" in t or "guac" in t:
        return ["Recipe/meal page", "Cart upsell", "Search results badges"]
    return ["Cart upsell", "PDP", "Home page deal tile"]


class PromoState(TypedDict):
    user_query: str
    retrieved: List[Dict[str, Any]]
    anchor_product_id: Optional[int]
    anchor_card: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    bundles: List[Dict[str, Any]]
    final: str

def retrieve_node(state: PromoState) -> PromoState:
    retrieved = product_semantic_search(state["user_query"], k=15)
    return {**state, "retrieved": retrieved}

import re

def choose_anchor_node(state: PromoState) -> PromoState:
    q = state["user_query"].strip().lower()
    pid = None

    candidates = search_products_by_name(q, limit=25)

    # normalize query tokens
    q_tokens = [t for t in re.split(r"\s+", q) if t]
    q_one_word = len(q_tokens) == 1

    def anchor_score(c):
        name = c["product_name"].lower()
        units = c["total_units"]
        rr = c["reorder_rate"]

        score = (units * 1.0) + (rr * 10000.0) - (len(name) * 25.0)

        # bonus: exact-ish matches for single-word queries
        if q_one_word:
            if name == q:
                score += 50000
            if name == q + "s":
                score += 40000
            if name.startswith(q + " "):
                score += 15000

        # penalty: overly specific / flavored / brand-ish terms (helps "eggs", "yogurt")
        bad_words = ["strawberry", "blueberry", "peach", "vanilla", "chocolate", "alfresco", "stage", "baby"]
        for w in bad_words:
            if w in name:
                score -= 12000

        return score

    if candidates:
        best = max(candidates, key=anchor_score)
        pid = best["product_id"]

    if pid is None and state["retrieved"]:
        pid = state["retrieved"][0].get("product_id")

    return {**state, "anchor_product_id": pid}


def load_anchor_node(state: PromoState) -> PromoState:
    pid = state["anchor_product_id"]
    card = get_product_card(int(pid)) if pid is not None else None
    return {**state, "anchor_card": card}

def candidates_node(state: PromoState) -> PromoState:
    pid = state["anchor_product_id"]
    cands = promo_candidates(int(pid), k=12) if pid is not None else []
    return {**state, "candidates": cands}

def score_bundle(anchor: Dict[str, Any], cand: Dict[str, Any], user_query: str) -> float:
    co = cand["co_purchase_count"]
    rr = cand["reorder_rate"]
    units = cand["total_units"]

    score = (co * 1.0) + (rr * 200.0) + (min(units, 5000) / 50.0)

    # boost same-department add-ons (dairy->dairy works well for eggs/yogurt)
    if cand.get("department_id") == anchor.get("department_id"):
        score += 5000

    # penalty for banana-heavy bundles unless user asked for fruit
    q = user_query.lower()
    name = cand["product_name"].lower()
    if ("banana" in name) and not any(x in q for x in ["banana", "fruit", "smoothie"]):
        score -= 4000

    return score


def respond_node(state: PromoState) -> PromoState:
    """
    Finalizes the promotional response by selecting and scoring bundle candidates.

    This agent node evaluates candidate products associated with an anchor product,
    scores them using user intent and affinity signals, and selects the top-ranked
    bundle options to construct the final promotional response.

    If no anchor product or candidates are available, the node returns a
    user-friendly fallback message.

    Args:
        state (PromoState): Current agent state containing:
            - anchor_card (dict): Selected anchor product for promotion
            - candidates (list): Potential bundle products from co-purchase affinity
            - user_query (str): Original user request or intent

    Returns:
        PromoState: Updated agent state including the final promotional response
        or an explanatory fallback message.
    """
    anchor = state["anchor_card"]
    if not anchor:
        return {**state, "final": "Could not identify an anchor product for promotion. Try a different query."}

    cands = state["candidates"]
    if not cands:
        return {**state, "final": f"Anchor: {anchor.get('product_name','(unknown)')}. No bundle candidates found in affinity table."}

    # 1) Score all candidates (best-first)
    scored = sorted(
        ((score_bundle(anchor, c, state["user_query"]), c) for c in cands),
        key=lambda x: x[0],
        reverse=True
    )

    # Keep top N candidates so bundle combinations stay fast
    top_candidates = [c for _, c in scored[:10]]

    # 2) Build bundles (anchor + 2 items)
    # We don’t have add-on-to-add-on affinity, so we add a conservative synergy bonus.
    def bundle_score(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        """
    Scores a 2-item add-on bundle for a given anchor product.

    The final score combines:
    - Individual relevance scores of each add-on item vs the anchor and user intent
    - A synergy term based on the minimum co-purchase count across both add-ons
      (encourages bundles where both items strongly associate with the anchor)

    Args:
        anchor (Dict[str, Any]): Anchor product card selected for promotion.
        a (Dict[str, Any]): First add-on candidate product.
        b (Dict[str, Any]): Second add-on candidate product.
        user_query (str): Original user query to capture intent.
        score_bundle_fn: Function that scores (anchor, candidate, user_query) relevance.

    Returns:
        float: Final bundle score (higher is better).
    """
        sa = score_bundle(anchor, a, state["user_query"])
        sb = score_bundle(anchor, b, state["user_query"])
        synergy = 0.30 * min(a.get("co_purchase_count", 0), b.get("co_purchase_count", 0))
        return sa + sb + synergy

    bundles = []
    for i in range(len(top_candidates)):
        for j in range(i + 1, len(top_candidates)):
            a = top_candidates[i]
            b = top_candidates[j]

            # ✅ NEW: avoid duplicate-family inside same bundle
            if family_key(a.get("product_name", "")) == family_key(b.get("product_name", "")):
                continue

            bundles.append((bundle_score(a, b), a, b))

    bundles.sort(key=lambda x: x[0], reverse=True)

    # 3) Pick top 3 bundles with diversity (don’t reuse the same add-on across bundles)
    selected_bundles = []
    structured_bundles = []
    used_products = set()

    for s, a, b in bundles:
        a_id, b_id = a["product_id"], b["product_id"]

        # Don't reuse exact products across bundles
        if a_id in used_products or b_id in used_products:
            continue

        selected_bundles.append((s, a, b))
        used_products.add(a_id)
        used_products.add(b_id)

        if len(selected_bundles) == 3:
            break

    if not selected_bundles:
        return {**state, "final": f"Anchor: {anchor['product_name']}. Not enough unique candidates to form 3 bundles."}

    # 4) Render response
    lines = []
    lines.append("Promotion Recommendation (Top 3 Bundles)")
    lines.append("")
    lines.append("Anchor SKU:")
    lines.append(anchor["text"])
    lines.append("")
    lines.append("Top 3 promo bundles (Anchor + 2 items):")
    

# Print ALL selected bundles, numbered 1..3
    for idx, (s, a, b) in enumerate(selected_bundles[:3], start=1):
        theme = infer_theme(anchor.get("product_name", ""), [a["product_name"], b["product_name"]])
        offer = suggest_offer_type(anchor, a, b)
        placement = suggest_placement(theme)

        min_aff = min(int(a.get("co_purchase_count", 0)), int(b.get("co_purchase_count", 0)))
        confidence = promo_confidence(min_aff)
        impact = expected_impact(anchor, min_aff)
        
        structured_bundles.append({
        "rank": idx,
        "bundle_score": float(round(s, 1)),
        "theme": theme,
        "offer": offer,
        "confidence": confidence,
        "expected_impact": impact,
        "placement": placement,
        "anchor": {
            "product_id": anchor.get("product_id"),
            "product_name": anchor.get("product_name"),
            "aisle_id": anchor.get("aisle_id"),
            "department_id": anchor.get("department_id"),
            "reorder_rate": float(anchor.get("reorder_rate", 0.0)),
            "total_units": int(anchor.get("total_units", 0)),
            "total_orders": int(anchor.get("total_orders", 0)),
        },
        "add_ons": [
            {
                "product_id": a.get("product_id"),
                "product_name": a.get("product_name"),
                "co_purchase_count": int(a.get("co_purchase_count", 0)),
                "reorder_rate": float(a.get("reorder_rate", 0.0)),
                "total_units": int(a.get("total_units", 0)),
            },
            {
                "product_id": b.get("product_id"),
                "product_name": b.get("product_name"),
                "co_purchase_count": int(b.get("co_purchase_count", 0)),
                "reorder_rate": float(b.get("reorder_rate", 0.0)),
                "total_units": int(b.get("total_units", 0)),
            }
        ]
    })


        lines.append(f"{idx}. Bundle Score={s:.1f}")
        lines.append(f"   Theme: {theme}")
        lines.append(f"   Offer: {offer}")
        lines.append(f"   Confidence: {confidence}")
        lines.append(f"   Expected impact: {impact}")
        lines.append(f"   Placement: {', '.join(placement)}")
        lines.append(f"   - {anchor['product_name']} (Anchor)")
        lines.append(
            f"   - {a['product_name']} (affinity={a['co_purchase_count']}, rr={a['reorder_rate']:.3f}, units={a['total_units']})"
        )
        lines.append(
            f"   - {b['product_name']} (affinity={b['co_purchase_count']}, rr={b['reorder_rate']:.3f}, units={b['total_units']})"
        )
        lines.append("")  # blank line between bundles

    lines.append("Why these bundles work:")
    lines.append("- High co-purchase counts indicate strong basket association (easy upsell).")
    lines.append("- High reorder rates imply repeat buying behavior (sticky categories).")
    lines.append("- Higher unit volume suggests better promo impact.")
    lines.append("- Bundles are diversified to avoid repeating similar add-on items.")

    return {**state, "bundles": structured_bundles, "final": "\n".join(lines)}


def build_promo_graph():
    g = StateGraph(PromoState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("choose_anchor", choose_anchor_node)
    g.add_node("load_anchor", load_anchor_node)
    g.add_node("candidates", candidates_node)
    g.add_node("respond", respond_node)

    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "choose_anchor")
    g.add_edge("choose_anchor", "load_anchor")
    g.add_edge("load_anchor", "candidates")
    g.add_edge("candidates", "respond")
    g.add_edge("respond", END)

    return g.compile()

if __name__ == "__main__":
    app = build_promo_graph()
    out = app.invoke({
        "user_query": "bananas",
        "retrieved": [],
        "anchor_product_id": None,
        "anchor_card": None,
        "candidates": [],
        "final": ""
    })
    print(out["final"])


