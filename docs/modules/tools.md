# `tools` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `product_semantic_search`

- **File:** `agents/tools.py` (lines 37-53)
- **Called by:** retrieve_node
- **Calls:** similarity_search

### Purpose
Run a semantic (vector) search over product RAG documents to find the most relevant products for a given query. Provides concise product context for downstream reasoning and decisioning.

### Inputs / Outputs
- Inputs: query (str), k (int, optional, default 5).
- Outputs: List of dicts: { "product_id": ..., "text": ... } for the top-k matches.

### How it connects
- Called by: retrieve_node to get product candidates.
- Calls: _vectordb.similarity_search to query the vector index.
- Returns a lightweight payload consumed by orchestrated nodes/tools.

### Why it matters in this project
Enables promotion and recommendation flows by turning natural language queries into relevant product candidates. Minimal fields (id + text) keep orchestration fast and easy to combine with downstream logic (e.g., ranking or affinity).

```python
def product_semantic_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Vector search over product RAG documents.
    """
    docs = _vectordb.similarity_search(query, k=k)

    results = []
    for d in docs:
        results.append({
            "product_id": d.metadata.get("product_id"),
            "text": d.page_content
        })

    return results


# ---------- TOOL 2: Basket affinity recommendations ----------
```


## `co_purchase_recommendations`

- **File:** `agents/tools.py` (lines 54-106)
- **Called by:** recommend_node
- **Calls:** connect, execute, fetchall, text

### Purpose
Return “bought-together” recommendations for a given product by querying basket affinity data. It treats product pairs symmetrically and ranks candidates by co-purchase frequency to power cross‑sell and bundling.

### Inputs / Outputs
Inputs: product_id (int), k (int, default 10).  
Outputs: list of dicts [{product_id, product_name, co_purchase_count}] ordered by frequency, limited to k.

### How it connects
Called by recommend_node. Uses SQLAlchemy (text, connect, execute, fetchall) against feat_basket_affinity and products to fetch names and counts. Returns a lightweight structure ready for downstream orchestration or UI.

### Why it matters in this project
Enables targeted promotions like “Customers also bought” and bundle offers at low latency using precomputed affinities. It’s a reusable building block for recommendation flows that drive basket size and conversion.

```python
def co_purchase_recommendations(
    product_id: int,
    k: int = 10
) -> List[Dict[str, Any]]:
    """
    Returns products that are most frequently purchased together with a given product.

    This function queries the basket affinity table to identify products
    that commonly co-occur with the specified product ID and ranks them
    by co-purchase frequency.

    Args:
        product_id (int): Product ID for which co-purchase recommendations are generated.
        k (int, optional): Maximum number of recommended products to return.
            Defaults to 10.

    Returns:
        List[Dict[str, Any]]: A list of recommended products containing:
            - product_id (int): Recommended product identifier
            - product_name (str): Name of the recommended product
            - co_purchase_count (int): Number of times products were bought together
    """
    sql = text("""
        WITH pairs AS (
            SELECT product_id_b AS other_id, co_purchase_count
            FROM feat_basket_affinity
            WHERE product_id_a = :pid
            UNION ALL
            SELECT product_id_a AS other_id, co_purchase_count
            FROM feat_basket_affinity
            WHERE product_id_b = :pid
        )
        SELECT p.product_id, p.product_name, pairs.co_purchase_count
        FROM pairs
        JOIN products p
          ON p.product_id = pairs.other_id
        ORDER BY pairs.co_purchase_count DESC
        LIMIT :k;
    """)

    with ENGINE.connect() as conn:
        rows = conn.execute(sql, {"pid": product_id, "k": k}).fetchall()

    return [
        {
            "product_id": r[0],
            "product_name": r[1],
            "co_purchase_count": int(r[2])
        }
        for r in rows
    ]
```


## `popular_alternatives`

- **File:** `agents/tools.py` (lines 107-132)
- **Called by:** respond_node
- **Calls:** connect, execute, fetchall, text

### Purpose
Provide fallback product recommendations when affinity pairs are unavailable. It surfaces the most popular items within a department, ranked by reorder_rate and total_units from feat_sku_velocity.

### Inputs / Outputs
- Inputs: department_id (int), k (int, default 10).
- Outputs: list of dicts [{product_id, product_name, total_units, reorder_rate}] cast to int/float as appropriate.

### How it connects
Called by respond_node as a tool in agents/tools.py. It queries the database via SQLAlchemy (text, connect, execute, fetchall) using ENGINE and returns results to the agent layer.

### Why it matters in this project
Keeps recommendation flows robust when pairwise affinity data is missing. Enables retail promotions and suggestions to highlight high-reorder, high-volume items in the same department, improving relevance and conversion.

```python
def popular_alternatives(department_id: int, k: int = 10):
    """
    Fallback recommendations when affinity pairs are missing.
    Returns popular items in the same department using feat_sku_velocity.
    """
    sql = text("""
      SELECT product_id, product_name, total_units, reorder_rate
      FROM feat_sku_velocity
      WHERE department_id = :did
      ORDER BY reorder_rate DESC, total_units DESC
      LIMIT :k;
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(sql, {"did": department_id, "k": k}).fetchall()

    return [
        {
            "product_id": r[0],
            "product_name": r[1],
            "total_units": int(r[2]),
            "reorder_rate": float(r[3]),
        }
        for r in rows
    ]
```


## `find_product_by_exact_name`

- **File:** `agents/tools.py` (lines 133-149)
- **Called by:** choose_product_node
- **Calls:** connect, execute, fetchall, text

### Purpose
Find products whose names exactly match given strings, and return up to five matches ranked by total_units. Uses a left join to include velocity data (total_units) for ordering.

### Inputs / Outputs
- Input: names (list[str]) — exact product_name values to match.
- Output: list of dicts: {product_id, product_name, total_units}, sorted by total_units desc, limited to 5.

### How it connects
Called by choose_product_node. Executes a SQLAlchemy text query via ENGINE.connect → execute → fetchall, joining products with feat_sku_velocity.

### Why it matters in this project
Promotions and recommendations need unambiguous SKU selection. This function resolves exact-name products and prioritizes higher total_units, helping the system target higher-activity items and streamline orchestration.

```python
def find_product_by_exact_name(names: list[str]):
    """
    Returns matching products for exact product_name values.
    """
    sql = text("""
      SELECT p.product_id, p.product_name, COALESCE(f.total_units,0) AS total_units
      FROM products p
      LEFT JOIN feat_sku_velocity f ON f.product_id = p.product_id
      WHERE p.product_name = ANY(:names)
      ORDER BY total_units DESC
      LIMIT 5;
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(sql, {"names": names}).fetchall()

    return [{"product_id": r[0], "product_name": r[1], "total_units": int(r[2])} for r in rows]
```


## `get_product_card`

- **File:** `agents/tools.py` (lines 150-190)
- **Called by:** load_anchor_node, respond_node
- **Calls:** connect, execute, fetchone, text

### Purpose
Fetch a normalized product card from Postgres combining catalog attributes with demand signals (velocity). Enables the agent to display and reason about a chosen SKU for ranking, recommendations, and promotions.

### Inputs / Outputs
- Input: product_id (int).
- Output: dict with product_id, product_name, aisle_id, department_id, total_units, total_orders, reorder_rate, and a human-readable text field. If not found, returns a minimal dict with a “not found” message.

### How it connects
Called by load_anchor_node and respond_node. Executes a parameterized SQL query via ENGINE.connect(), text(), execute(), fetchone(). LEFT JOINs feat_sku_velocity and COALESCEs metrics to 0 for consistent types.

### Why it matters in this project
Provides a single, clean payload the agent can rank and present, using reorder_rate and velocity to justify recommendations or promotions. Stable schema and defaults simplify downstream orchestration and user-facing responses.

```python
def get_product_card(product_id: int) -> dict:
    """
    Fetch a clean product card from Postgres (so the agent can display the chosen SKU).
    """
    sql = text("""
      SELECT
        p.product_id,
        p.product_name,
        p.aisle_id,
        p.department_id,
        COALESCE(f.total_units, 0) AS total_units,
        COALESCE(f.total_orders, 0) AS total_orders,
        COALESCE(f.reorder_rate, 0) AS reorder_rate
      FROM products p
      LEFT JOIN feat_sku_velocity f ON f.product_id = p.product_id
      WHERE p.product_id = :pid
      LIMIT 1;
    """)
    with ENGINE.connect() as conn:
        row = conn.execute(sql, {"pid": product_id}).fetchone()

    if not row:
        return {"product_id": product_id, "text": f"Product ID: {product_id} (not found)"}

    return {
        "product_id": int(row[0]),
        "product_name": row[1],
        "aisle_id": int(row[2]),
        "department_id": int(row[3]),
        "total_units": int(row[4]),
        "total_orders": int(row[5]),
        "reorder_rate": float(row[6]),
        "text": (
            f"Product ID: {int(row[0])}\n"
            f"Name: {row[1]}\n"
            f"Aisle ID: {int(row[2])} | Department ID: {int(row[3])}\n"
            f"Demand: total_units={int(row[4])}, total_orders={int(row[5])}, reorder_rate={float(row[6]):.3f}\n"
            f"Use: Retail catalog item (SKU) with demand signals for ranking and recommendations."
        )
    }
```


## `promo_candidates`

- **File:** `agents/tools.py` (lines 191-235)
- **Called by:** candidates_node
- **Calls:** connect, execute, mappings, text

### Purpose
Generate candidate products for a promotion or recommendation by combining basket affinity (co-purchase) with demand signals (velocity and reorder rate). Produces a ready-to-score bundle per seed product.

### Inputs / Outputs
- Inputs: product_id (int), k (int, default 12).
- Output: list of dicts [{product_id, product_name, department_id, co_purchase_count, total_units, reorder_rate}], sorted by co_purchase_count and limited to k, with explicit int/float types.

### How it connects
Called by candidates_node. Executes a SQLAlchemy text query via ENGINE.connect(). Pulls pairs from feat_basket_affinity (both directions), enriches with products and feat_sku_velocity, and returns column-mapped results using mappings().

### Why it matters in this project
Provides the shortlist that downstream scorers and planners use to assemble promo bundles and cross-sell recommendations. By merging affinity with demand, it improves targeting quality and system orchestration reliability with consistent, typed payloads.

```python
def promo_candidates(product_id: int, k: int = 12):
    """
    Bundle candidates for promotions: affinity + demand signals for scoring.
    """
    sql = text("""
      WITH pairs AS (
        SELECT product_id_b AS other_id, co_purchase_count
        FROM feat_basket_affinity
        WHERE product_id_a = :pid
        UNION ALL
        SELECT product_id_a AS other_id, co_purchase_count
        FROM feat_basket_affinity
        WHERE product_id_b = :pid
      )
      SELECT
        p.product_id                    AS product_id,
        p.product_name                  AS product_name,
        p.department_id                 AS department_id,
        pairs.co_purchase_count         AS co_purchase_count,
        COALESCE(f.total_units, 0)      AS total_units,
        COALESCE(f.reorder_rate, 0)     AS reorder_rate
      FROM pairs
      JOIN products p ON p.product_id = pairs.other_id
      LEFT JOIN feat_sku_velocity f ON f.product_id = p.product_id
      ORDER BY pairs.co_purchase_count DESC
      LIMIT :k;
    """)

    with ENGINE.connect() as conn:
        # Use mappings() so we access columns by name
        rows = conn.execute(sql, {"pid": product_id, "k": k}).mappings().all()

    return [
        {
            "product_id": int(r["product_id"]),
            "product_name": r["product_name"],
            "department_id": int(r["department_id"]),
            "co_purchase_count": int(r["co_purchase_count"]),
            "total_units": int(r["total_units"]),
            "reorder_rate": float(r["reorder_rate"]),
        }
        for r in rows
    ]
```


## `search_products_by_name`

- **File:** `agents/tools.py` (lines 236-270)
- **Called by:** choose_anchor_node
- **Calls:** connect, execute, fetchall, strip, text

### Purpose
Search products by name and return candidate anchor SKUs enriched with demand signals. Results are ranked by total units and reorder rate to support strong anchor selection.

### Inputs / Outputs
- Inputs: query (str, product name substring), limit (int, default 15).
- Outputs: list of dicts with product_id (int), product_name (str), total_units (int), reorder_rate (float). Returns [] if the query is empty.

### How it connects
Called by choose_anchor_node to propose anchor SKUs. Uses ENGINE.connect/execute/fetchall with a SQL text query, ILIKE pattern matching, and a LEFT JOIN to feat_sku_velocity so missing signals default to zero.

### Why it matters in this project
Anchor SKU choice steers promotions and recommendations. By ranking matches using demand metrics, this tool prioritizes high-velocity products, improving campaign impact and downstream orchestration decisions.

```python
def search_products_by_name(query: str, limit: int = 15):
    """
    Find likely anchor SKUs by name using ILIKE (case-insensitive).
    Returns candidates with demand signals to choose the best anchor.
    """
    q = query.strip()
    if not q:
        return []

    sql = text("""
      SELECT
        p.product_id,
        p.product_name,
        COALESCE(f.total_units, 0) AS total_units,
        COALESCE(f.reorder_rate, 0) AS reorder_rate
      FROM products p
      LEFT JOIN feat_sku_velocity f ON f.product_id = p.product_id
      WHERE p.product_name ILIKE :pattern
      ORDER BY COALESCE(f.total_units, 0) DESC, COALESCE(f.reorder_rate, 0) DESC
      LIMIT :limit;
    """)
    pattern = f"%{q}%"

    with ENGINE.connect() as conn:
        rows = conn.execute(sql, {"pattern": pattern, "limit": limit}).fetchall()

    return [
        {
            "product_id": int(r[0]),
            "product_name": r[1],
            "total_units": int(r[2]),
            "reorder_rate": float(r[3]),
        }
        for r in rows
    ]
```

