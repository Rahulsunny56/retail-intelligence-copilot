# tools

_Auto-generated from repo index. Run `python -m agents.repo_bot.docgen` to refresh._

### `product_semantic_search`

- **File:** `agents/tools.py` (lines 37-53)
- **Called by:** retrieve_node
- **Calls:** similarity_search

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


### `co_purchase_recommendations`

- **File:** `agents/tools.py` (lines 54-106)
- **Called by:** recommend_node
- **Calls:** connect, execute, fetchall, text

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


### `popular_alternatives`

- **File:** `agents/tools.py` (lines 107-132)
- **Called by:** respond_node
- **Calls:** connect, execute, fetchall, text

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


### `find_product_by_exact_name`

- **File:** `agents/tools.py` (lines 133-149)
- **Called by:** choose_product_node
- **Calls:** connect, execute, fetchall, text

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


### `get_product_card`

- **File:** `agents/tools.py` (lines 150-190)
- **Called by:** load_anchor_node, respond_node
- **Calls:** connect, execute, fetchone, text

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


### `promo_candidates`

- **File:** `agents/tools.py` (lines 191-235)
- **Called by:** candidates_node
- **Calls:** connect, execute, mappings, text

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


### `search_products_by_name`

- **File:** `agents/tools.py` (lines 236-270)
- **Called by:** choose_anchor_node
- **Calls:** connect, execute, fetchall, strip, text

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

