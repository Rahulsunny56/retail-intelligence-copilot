# `promo_agent` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `family_key`

- **File:** `agents/promo_agent.py` (lines 22-55)
- **Called by:** respond_node
- **Calls:** lower, split, sub

### Purpose
Group product names into a consistent “family” so promo bundles and recommendations don’t double-count near-duplicates (e.g., avocado vs. avocados, yogurt variants).

### Inputs / Outputs
- Input: name (str) — raw product name.
- Output: family key (str) — normalized label like "avocado", "eggs", "strawberries", or a cleaned base term (max 30 chars), falling back to "other".

### How it connects
Called by respond_node to canonicalize items before bundling or deduping. Internally uses lower, re.sub, and split to strip descriptors and normalize tokens.

### Why it matters in this project
Prevents redundant bundle components and cleaner cross-item recommendations by aligning SKUs to families. Improves promo logic, avoids avocado+avocado style bundles, and stabilizes orchestration across varied product naming.

```python
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
```


## `infer_theme`

- **File:** `agents/promo_agent.py` (lines 56-82)
- **Called by:** respond_node
- **Calls:** lower

### Purpose
Infer a promotion theme from an anchor product and optional add-ons using simple keyword rules. The logic is anchor-first (yogurt, eggs, avocado override), then falls back to add-on driven categories.

### Inputs / Outputs
- Inputs: anchor_name (str), add_on_names (list[str]); both normalized to lowercase, add-ons concatenated into a single string.
- Output: one of "Healthy Breakfast / Smoothie", "Breakfast Essentials", "Fresh Prep / Cooking (Guac & Sides)", "Snack & Beverage", or default "Everyday Staples".

### How it connects
- Location: agents/promo_agent.py, symbol infer_theme; called by respond_node.
- Uses only str.lower for normalization; no external dependencies.
- The returned theme label feeds downstream promo messaging or recommendation selection.

### Why it matters in this project
- Provides fast, deterministic theming to align promotions and bundles with shopper intent, prioritizing the anchor item.
- Ensures consistent orchestration in respond_node, with clear defaults when no specific theme is detected.

```python
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
```


## `discount_from_affinity`

- **File:** `agents/promo_agent.py` (lines 83-96)
- **Called by:** suggest_offer_type
- **Calls:** (none)

### Purpose
Translate an item-pair affinity score into a concrete discount message. Calibrated to Instacart-like affinity ranges so stronger natural pairings get smaller discounts and weaker pairs get larger incentives.

### Inputs / Outputs
- Input: min_aff (int) — minimum observed affinity for the pair.
- Output: str — one of "Save $1", "Save $2", "Save $3", or "Save $4", based on thresholds (≥30k, ≥10k, ≥4k, else).

### How it connects
Used by suggest_offer_type to pick the discount magnitude shown to customers. Pure function with no dependencies, ensuring consistent, deterministic discount banding across the promo flow.

### Why it matters in this project
Aligns promotion strength with recommendation confidence: strong complements aren’t over-discounted, while weaker pairs get extra incentive. This improves promo ROI and nudges cross-sell adoption in Retail Intelligence Copilot.

```python
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
```


## `promo_confidence`

- **File:** `agents/promo_agent.py` (lines 97-103)
- **Called by:** respond_node
- **Calls:** (none)

### Purpose
Translate a numeric metric into a three-level confidence label used for promotion decisions and messaging.

### Inputs / Outputs
- Input: min_aff (int).
- Output: "High" if min_aff ≥ 20000, "Medium" if ≥ 6000, else "Low".

### How it connects
Called by respond_node to attach a confidence label to promotional responses. It doesn’t call other functions.

### Why it matters in this project
Provides a simple, consistent confidence bucket that downstream orchestration can use to prioritize, filter, or explain promotion recommendations. This keeps decisioning straightforward and auditable.

```python
def promo_confidence(min_aff: int) -> str:
    if min_aff >= 20000:
        return "High"
    if min_aff >= 6000:
        return "Medium"
    return "Low"
```


## `expected_impact`

- **File:** `agents/promo_agent.py` (lines 104-116)
- **Called by:** respond_node
- **Calls:** (none)

### Purpose
Classifies a product pairing’s expected promotional impact. It turns basic behavioral signals into a clear label (e.g., “Trial driver”, “Basket builder”) to guide promo or recommendation strategy.

### Inputs / Outputs
- Inputs: anchor (dict with reorder_rate, total_units), min_aff (int).
- Output: one of four strings based on rules:
  - rr < 0.60 → “Trial driver”
  - min_aff ≥ 20000 and units ≥ 50000 → “Basket builder”
  - min_aff ≥ 6000 → “Attach-rate lift”
  - else → “Discovery assist”

### How it connects
Called by respond_node. It does not call other functions; it returns a label used downstream to frame promotional recommendations or messaging.

### Why it matters in this project
Provides a consistent, lightweight impact label that steers promo tactics—trial, basket building, attach-rate, or discovery—improving relevance and orchestration of retail promotions and recommendations.

```python
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
```


## `suggest_offer_type`

- **File:** `agents/promo_agent.py` (lines 117-130)
- **Called by:** respond_node
- **Calls:** discount_from_affinity

### Purpose
Selects a promotional offer for an anchor product based on reorder rate, sales volume, and add-on co-purchase affinity. It returns either a BOGO trial offer or a bundle discount with 1–2 add-ons.

### Inputs / Outputs
Inputs: dicts for anchor, a, b. Uses anchor.reorder_rate, anchor.total_units, a.co_purchase_count, b.co_purchase_count.  
Output: a string: "BOGO..." or "Bundle Discount: Buy anchor + N add-ons, {save}", where {save} comes from discount_from_affinity.

### How it connects
Called by respond_node to produce a concrete offer string for responses.  
Delegates savings text to discount_from_affinity using the minimum co-purchase count between a and b.

### Why it matters in this project
Encodes consistent, lightweight promo logic for the Copilot to recommend trial-driving BOGO when reorder is low and bundle upsells when volume is high.  
Uses conservative affinity (min) to size the discount, aligning bundle strength with observed demand.

```python
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
```


## `suggest_placement`

- **File:** `agents/promo_agent.py` (lines 131-142)
- **Called by:** respond_node
- **Calls:** lower

### Purpose
Return recommended on-site/app/email placements for a promo based on its theme to maximize conversion.

### Inputs / Outputs
- Input: theme (str). Case-normalized for keyword checks.
- Output: list[str] of placement surfaces (e.g., Cart upsell, PDP, email/app banner).

### How it connects
- Location: agents/promo_agent.py, function suggest_placement.
- Called by: respond_node.
- Calls: str.lower for case-insensitive matching.

### Why it matters in this project
Encodes lightweight, theme-based heuristics to route promotions to high-impact surfaces (cart, PDP, recipe pages, search, banners). This improves promo relevance and conversion and supports orchestration by giving downstream steps concrete placement targets.

```python
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
```


## `PromoState`

- **File:** `agents/promo_agent.py` (lines 143-151)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Defines the canonical state for the Promotion Agent. It tracks the user’s query, retrieved context, an optional anchor product, candidate items/promos, bundle options, and the final composed output.

### Inputs / Outputs
- Inputs: user_query (str), retrieved (list of dicts), optional anchor_product_id (int) and anchor_card (dict).
- Working sets: candidates (list of dicts), bundles (list of dicts).
- Output: final (str) — the rendered promo/recommendation response.

### How it connects
Acts as the shared schema passed between steps that build promotions. Other components read/write these fields while orchestrating promo generation; this type itself has no behavior or outbound calls.

### Why it matters in this project
Provides a stable contract for promo and recommendation orchestration, enabling consistent pipelines from retrieval to anchor selection to bundling to response. This reduces coupling, eases testing/observability, and keeps the promotion flow predictable.

```python
class PromoState(TypedDict):
    user_query: str
    retrieved: List[Dict[str, Any]]
    anchor_product_id: Optional[int]
    anchor_card: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    bundles: List[Dict[str, Any]]
    final: str
```


## `retrieve_node`

- **File:** `agents/promo_agent.py` (lines 152-157)
- **Called by:** (not shown)
- **Calls:** product_semantic_search

### Purpose
Retrieve semantically relevant products for a user’s query and attach them to the agent state. This acts as the retrieval step in the promotion/recommendation pipeline.

### Inputs / Outputs
- Input: PromoState (mapping) containing "user_query".
- Output: Same state plus "retrieved" set to the top-15 results from product_semantic_search(state["user_query"], k=15).

### How it connects
Calls product_semantic_search and writes results to state["retrieved"]. Designed as a pipeline node so downstream steps can consume candidates without re-querying.

### Why it matters in this project
Provides the candidate product set that promotions and recommendations are built on. Keeps orchestration clean (state in/state out), enabling composable, reliable promo workflows.

```python
def retrieve_node(state: PromoState) -> PromoState:
    retrieved = product_semantic_search(state["user_query"], k=15)
    return {**state, "retrieved": retrieved}

import re
```


## `choose_anchor_node`

- **File:** `agents/promo_agent.py` (lines 158-201)
- **Called by:** (not shown)
- **Calls:** lower, search_products_by_name, split, strip

### Purpose
Select a single “anchor” product for a user’s query to center promotion or recommendation flows. It scores candidates by demand (total_units), loyalty (reorder_rate), and name brevity, with bonuses for exact/plural/prefix matches and penalties for flavored/brand-ish terms.

### Inputs / Outputs
Input: state dict with "user_query" and optional "retrieved" list.  
Output: same state plus "anchor_product_id" set to the best candidate; if none found, falls back to the first item in "retrieved"; otherwise remains None.

### How it connects
Normalizes the query via strip and lower, tokenizes with regex split, and fetches candidates using search_products_by_name(q, limit=25). Downstream steps read "anchor_product_id" to orchestrate subsequent promo or recommendation logic.

### Why it matters in this project
Picking a high-signal anchor keeps promotions focused and coherent. Favoring popular, frequently re-ordered, generic items ensures broad relevance, while penalizing flavored/brand terms avoids over-specific matches for generic intents (e.g., “eggs”, “yogurt”).

```python
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
```


## `choose_anchor_node.anchor_score`

- **File:** `agents/promo_agent.py` (lines 168-201)
- **Called by:** (not shown)
- **Calls:** lower, startswith

### Purpose
Score and select an “anchor” product from candidates to center promotions/recommendations. Favors high-volume and high-reorder items, boosts exact single-word matches, and penalizes long or overly specific/flavored names.

### Inputs / Outputs
Input to anchor_score(c): a candidate dict with product_name, total_units, reorder_rate; also relies on external q and q_one_word. Overall flow: pick max(candidates, key=anchor_score), fall back to state["retrieved"][0] if needed. Output: state augmented with anchor_product_id.

### How it connects
Implemented as choose_anchor_node.anchor_score in agents/promo_agent.py. Uses string.lower() and startswith() for normalization and prefix checks. The score blends units (+1×), reorder_rate (+10,000×), name length (−25× per char), bad-word penalties (−12,000), and single-word exact-ish bonuses (+15k to +50k).

### Why it matters in this project
A strong anchor stabilizes orchestration for downstream promo logic and product recommendations. By prioritizing broadly relevant staples and filtering flavored/brand-y terms, it improves promotional relevance and click-through potential.

```python
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
```


## `load_anchor_node`

- **File:** `agents/promo_agent.py` (lines 202-206)
- **Called by:** (not shown)
- **Calls:** get_product_card

### Purpose
Load the anchor product’s card into the promo agent state so downstream promotion/recommendation logic can reason about a specific product. It enriches the state without mutating the original.

### Inputs / Outputs
Input: PromoState dict containing anchor_product_id (may be None).  
Output: Same state plus anchor_card set to the fetched product card (or None). The ID is cast to int before lookup.

### How it connects
Calls get_product_card to retrieve canonical product data for the anchor product. Publishes anchor_card back into the shared state for subsequent nodes in the promotion pipeline.

### Why it matters in this project
Promotions and recommendations often pivot around an anchor product; this step standardizes and centralizes that lookup. It enables consistent orchestration and graceful handling when the anchor ID is missing.

```python
def load_anchor_node(state: PromoState) -> PromoState:
    pid = state["anchor_product_id"]
    card = get_product_card(int(pid)) if pid is not None else None
    return {**state, "anchor_card": card}
```


## `candidates_node`

- **File:** `agents/promo_agent.py` (lines 207-211)
- **Called by:** (not shown)
- **Calls:** promo_candidates

### Purpose
Build a candidate set of products for a given anchor product to drive promotion and recommendation steps. It enriches the agent’s state with up to 12 relevant candidates.

### Inputs / Outputs
Input: PromoState containing "anchor_product_id".  
Output: The same state plus "candidates" set to the result of promo_candidates(...) or [] if no anchor id.

### How it connects
Consumes "anchor_product_id" from upstream state.  
Calls promo_candidates(pid, k=12) and writes "candidates" for downstream nodes to rank, price, or assemble promo offers.

### Why it matters in this project
It standardizes candidate generation, caps volume for efficiency, and gracefully handles missing anchors. This is a key orchestration step for reliable, scalable retail promotions and recommendations.

```python
def candidates_node(state: PromoState) -> PromoState:
    pid = state["anchor_product_id"]
    cands = promo_candidates(int(pid), k=12) if pid is not None else []
    return {**state, "candidates": cands}
```


## `score_bundle`

- **File:** `agents/promo_agent.py` (lines 212-231)
- **Called by:** respond_node, respond_node.bundle_score
- **Calls:** lower

### Purpose
Scores a candidate product as an add-on to an anchor item for bundle recommendations. Combines co-purchase behavior, reorder propensity, and sales velocity to rank bundles.

### Inputs / Outputs
- Inputs: anchor (dict), cand (dict with co_purchase_count, reorder_rate, total_units, department_id, product_name), user_query (str).
- Output: float score; higher is better for promotion/ranking.

### How it connects
Used by respond_node and respond_node.bundle_score to rank bundle suggestions. Internally only calls lower() on strings for intent and name checks.

### Why it matters in this project
Drives retail promotion by prioritizing high-lift, low-friction add-ons. Boosts same-department complements, caps popularity to avoid runaway items, and penalizes irrelevant “banana” bundles unless user intent matches—resulting in more relevant, higher-conversion recommendations.

```python
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
```


## `respond_node`

- **File:** `agents/promo_agent.py` (lines 232-412)
- **Called by:** (not shown)
- **Calls:** bundle_score, expected_impact, family_key, get_product_card, infer_theme, popular_alternatives, promo_confidence, round, score_bundle, sort, suggest_offer_type, suggest_placement

### Purpose
Selects and scores add-on bundles around a chosen anchor product, using user intent and co-purchase signals. Produces the top 1–3 bundle recommendations with themes, offers, placement, confidence, and expected impact.

### Inputs / Outputs
Inputs: PromoState with anchor_card, candidates (affinity-based add-ons), and user_query.  
Outputs: Updated state with a human-readable “final” summary and a structured “bundles” list; graceful fallbacks if anchor/candidates are missing or not diverse.

### How it connects
Assumes earlier nodes set the anchor and candidate list. Calls score_bundle, family_key, infer_theme, suggest_offer_type, suggest_placement, promo_confidence, and expected_impact to enrich each bundle. Downstream UI/campaign systems can render or schedule these bundles directly.

### Why it matters in this project
Turns raw affinity and intent into actionable promotions that increase basket size. Enforces diversity (no duplicate-family items and no add-on reuse) and limits to top-10 candidates for speed. Adds confidence and impact estimates to guide placement and offer strategy.

```python
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
```


## `respond_node.bundle_score`

- **File:** `agents/promo_agent.py` (lines 273-412)
- **Called by:** (not shown)
- **Calls:** score_bundle

### Purpose
Compute a relevance score for a 2-item add‑on bundle around an anchor product, then rank and select the top 3 diverse promo bundles. It blends item relevance to intent with a synergy term from co‑purchase signals to drive effective cross‑sell recommendations.

### Inputs / Outputs
Inputs:
- bundle_score takes two add-on candidates (a, b) and uses ambient anchor and state["user_query"].
- Uses fields like co_purchase_count, reorder_rate, total_units.

Outputs:
- bundle_score returns a float score.
- The surrounding logic returns a dict with structured_bundles (ranked bundles with metadata) and a human-readable "final" string.

### How it connects
- Calls score_bundle(anchor, candidate, user_query) to get per-item relevance.
- Used locally to score all candidate pairs, filter out same-family pairs (family_key), and enforce product diversity across top bundles.
- Enriches selected bundles via infer_theme, suggest_offer_type, suggest_placement, promo_confidence, expected_impact for orchestration and rendering.

### Why it matters in this project
This node turns raw affinity and intent signals into actionable promo bundles that are diverse, explainable, and ready for placement. It improves attach-rate opportunities and streamlines promo orchestration by outputting both structured data and presentation text for downstream channels.

```python
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
```


## `build_promo_graph`

- **File:** `agents/promo_agent.py` (lines 413-442)
- **Called by:** (not shown)
- **Calls:** StateGraph, add_edge, add_node, compile, set_entry_point

### Purpose
Builds and compiles a StateGraph that orchestrates the promotion workflow: retrieve → choose_anchor → load_anchor → candidates → respond → END. This turns a user query into a final promotional/recommendation response.

### Inputs / Outputs
Input is a state with keys: user_query, retrieved, anchor_product_id, anchor_card, candidates, final. Output is the same state after nodes update it, with final containing the response printed at the end.

### How it connects
Uses StateGraph to register nodes (retrieve_node, choose_anchor_node, load_anchor_node, candidates_node, respond_node), wire edges, set the entry point, and compile into an invokable app. The END sentinel cleanly terminates the run.

### Why it matters in this project
Provides a deterministic pipeline for retail promotions: retrieve items, pick an anchor product, load its details, propose candidates, and generate a response. This modular graph keeps recommendation steps consistent and easy to test or swap as the system evolves.

```python
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
```

