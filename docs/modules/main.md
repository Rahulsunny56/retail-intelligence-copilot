# `main` Module

_Auto-generated documentation. Summaries are produced by GPT-5 and cached to avoid unnecessary re-generation._

## `root`

- **File:** `api/main.py` (lines 20-34)
- **Called by:** (not shown)
- **Calls:** FileResponse

### Purpose
Serve the UI entrypoint and initialize shared promotion infrastructure. It returns the app’s index HTML, builds the LangGraph promo pipeline once, and configures MLflow tracking for experiment logging.

### Inputs / Outputs
- root(): no inputs; outputs a FileResponse serving ui/index.html.
- Module side effects: creates promo_graph at import time; sets MLflow tracking URI and experiment name.

### How it connects
The root endpoint lets the frontend load the Retail Intelligence Copilot UI. promo_graph is reused by downstream handlers to run promotion workflows without reloading embeddings/vector DB. MLflow settings ensure all promo runs log to the configured tracking server.

### Why it matters in this project
Pre-building the promo graph reduces latency and stabilizes recommendation/promotion execution. Centralized MLflow tracking adds reproducibility and observability to promotion strategies, while the root route exposes the UI that orchestrates these flows.

```python
def root():
    return FileResponse("ui/index.html")

# Build the LangGraph app once at startup (so we don't reload embeddings/vector DB every request)
promo_graph = build_promo_graph()

# ---------------------------
# MLflow Tracking config
# ---------------------------
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "promo_api")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(MLFLOW_EXPERIMENT)
```


## `BundleItem`

- **File:** `api/main.py` (lines 35-42)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Defines a typed data model for a product included in a bundle recommendation or promotion. It captures key behavioral and sales signals (co-purchase frequency, reorder propensity, volume) used to assemble and rank bundles.

### Inputs / Outputs
Represents the payload shape with:
- product_id (int), product_name (str)
- co_purchase_count (int), reorder_rate (float), total_units (int)
Used to serialize/validate bundle item details moving through the API.

### How it connects
Lives in api/main.py and is instantiated by callers (not shown) to construct bundle-related responses or requests. It standardizes how bundle item metrics are passed across the API layer.

### Why it matters in this project
Provides consistent, comparable metrics for promotion and recommendation logic—enabling sorting, filtering, and justification of bundle offers by co-purchase frequency, repeat likelihood, and sales volume. This supports reliable orchestration of retail bundle decisions.

```python
class BundleItem(BaseModel):
    product_id: int
    product_name: str
    co_purchase_count: int
    reorder_rate: float
    total_units: int
```


## `AnchorModel`

- **File:** `api/main.py` (lines 43-52)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Defines a typed “anchor product” record with identity (IDs, name) and basic demand signals (reorder_rate, totals). It serves as the canonical object passed around the API for downstream promo and recommendation logic.

### Inputs / Outputs
Inputs: product_id (int), product_name (str), aisle_id (int), department_id (int), reorder_rate (float), total_units (int), total_orders (int).  
Output: a structured, serializable object representing one product and its aggregate demand metrics.

### How it connects
Lives in api/main.py and does not call anything itself. Other API endpoints or services import it to standardize product payloads, ensuring a consistent contract across orchestration flows.

### Why it matters in this project
A single, consistent product schema minimizes integration friction and data drift. The included metrics (reorder rate and aggregates) are the essentials many ranking, promotion targeting, and recommendation steps rely on.

```python
class AnchorModel(BaseModel):
    product_id: int
    product_name: str
    aisle_id: int
    department_id: int
    reorder_rate: float
    total_units: int
    total_orders: int
```


## `PromoBundle`

- **File:** `api/main.py` (lines 53-64)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Defines a structured promotional bundle: a ranked offer built around an anchor item with add-on items, scoring, and placement hints. It’s the data contract used to move promotion bundles through recommendation and placement flows.

### Inputs / Outputs
Inputs: rank, bundle_score, theme, offer, confidence, expected_impact, placement (list of surfaces), anchor (AnchorModel), add_ons (List[BundleItem]).  
Output: a single PromoBundle object that can be serialized and passed across API boundaries.

### How it connects
Composes AnchorModel and BundleItem to represent the full bundle. It is referenced by API/orchestration code to deliver ranked bundles to clients or downstream services based on placement targets.

### Why it matters in this project
Enables consistent promotion packaging for recommendation, ranking, and placement across channels. Carries both quantitative (rank/score) and qualitative (confidence/expected_impact) signals to prioritize and explain promotional decisions.

```python
class PromoBundle(BaseModel):
    rank: int
    bundle_score: float
    theme: str
    offer: str
    confidence: str
    expected_impact: str
    placement: List[str]
    anchor: AnchorModel
    add_ons: List[BundleItem]
```


## `PromoResponse`

- **File:** `api/main.py` (lines 65-72)
- **Called by:** promo_recommendations
- **Calls:** (none)

### Purpose
Define the response schema for promotion recommendations, ensuring the API returns a consistent, typed payload for retail promo results.

### Inputs / Outputs
Outputs a structured body with: query (the original request string), bundles (List[PromoBundle] of recommended promo groupings), result_text (human-readable summary), and state (optional dict for workflow/context).

### How it connects
Returned by promo_recommendations in api/main.py. It doesn’t call anything; it’s used by FastAPI/Pydantic to serialize the recommendation result back to clients.

### Why it matters in this project
Provides a stable contract for delivering promo bundles and a summary, enabling UIs and channels to render offers reliably. The optional state field carries orchestration context across steps, improving end-to-end recommendation workflows.

```python
class PromoResponse(BaseModel):
    query: str
    bundles: List[PromoBundle]
    result_text: str
    state: Optional[Dict[str, Any]] = None


@app.get("/health")
```


## `health`

- **File:** `api/main.py` (lines 73-77)
- **Called by:** (not shown)
- **Calls:** (none)

### Purpose
Expose a minimal health indicator so orchestration and monitoring can verify the API process is alive without touching business logic.

### Inputs / Outputs
- Inputs: none.
- Outputs: JSON object {"status": "ok"} indicating the service is healthy.

### How it connects
Polled by external probes (e.g., load balancers or schedulers) to decide if this service can receive traffic, including promo recommendation requests. It has no dependencies, so it’s safe for liveness/readiness checks.

### Why it matters in this project
Reliable health signaling keeps the promo-recommendations API available, enabling fast failure detection, automated recovery, and stable delivery of retail promotion recommendations under load.

```python
def health():
    return {"status": "ok"}


@app.get("/promo-recommendations", response_model=PromoResponse)
```


## `promo_recommendations`

- **File:** `api/main.py` (lines 78-158)
- **Called by:** (not shown)
- **Calls:** PromoResponse, Query, TemporaryDirectory, dump, invoke, log_artifact, log_metric, log_param, open, set_tag, start_run, time, uuid4

### Purpose
Serve a promotion-recommendation request by orchestrating a LangGraph run that turns a user product query into promotion bundles and a final summary. Adds robust telemetry for each request to support monitoring and iteration.

### Inputs / Outputs
- Inputs: query (string, required), debug (bool).
- Outputs: PromoResponse with bundles (list), result_text (string), original query, and optional full state when debug is true. Errors from the graph are re-raised.

### How it connects
Initializes a LangGraph state (user_query, retrieved, anchor, candidates, bundles, final) and calls promo_graph.invoke. Logs one MLflow run per request: params/tags (query, endpoint, debug, status, anchor info), metrics (latency_ms, bundle_count), and a JSON artifact of the response.

### Why it matters in this project
Returns concrete promotion bundles and narrative copy that drive retail recommendations. The MLflow logs enable tracking quality and latency, diagnosing failures, and analyzing anchor/bundle behavior to tune promotion strategies at scale.

```python
def promo_recommendations(
    query: str = Query(..., min_length=1, description="Product search query, e.g., avocado, eggs, yogurt"),
    debug: bool = Query(False, description="If true, include full agent state"),
):
    t0 = time.time()

    # LangGraph state payload (must match your PromoState keys)
    state = {
        "user_query": query,
        "retrieved": [],
        "anchor_product_id": None,
        "anchor_card": None,
        "candidates": [],
        "bundles": [],
        "final": "",
    }

    out = None
    err = None

    try:
        out = promo_graph.invoke(state)
    except Exception as e:
        err = str(e)
        # still let it fail visibly for now (or return a friendly message)
        raise
    finally:
        # ---- MLflow logging (do not crash API if MLflow is down) ----
        try:
            latency_ms = (time.time() - t0) * 1000.0

            # Create one run per request
            run_name = f"promo_api_{uuid.uuid4().hex[:8]}"
            with mlflow.start_run(run_name=run_name):
                # Parameters / tags (good for filtering)
                mlflow.log_param("query", query)
                mlflow.set_tag("endpoint", "/promo-recommendations")
                mlflow.set_tag("debug", str(debug))
                mlflow.set_tag("status", "error" if err else "ok")

                # Metrics (trend over time)
                mlflow.log_metric("latency_ms", latency_ms)

                if out:
                    # Useful summary metrics
                    bundles = out.get("bundles", [])
                    mlflow.log_metric("bundle_count", float(len(bundles)))

                    # Anchor info if present
                    anchor = out.get("anchor_card") or {}
                    if anchor.get("product_id") is not None:
                        mlflow.log_param("anchor_product_id", int(anchor["product_id"]))
                        mlflow.set_tag("anchor_name", str(anchor.get("product_name", ""))[:200])

                    # Artifact: save the structured response JSON
                    payload = {
                        "query": query,
                        "bundles": bundles,
                        "result_text": out.get("final", ""),
                    }

                    with tempfile.TemporaryDirectory() as td:
                        path = os.path.join(td, "promo_response.json")
                        with open(path, "w") as f:
                            json.dump(payload, f, indent=2)
                        mlflow.log_artifact(path, artifact_path="responses")

                if err:
                    mlflow.set_tag("error_message", err[:500])

        except Exception:
            # Never allow MLflow issues to break the API response
            pass

    return PromoResponse(
        query=query,
        bundles=out.get("bundles", []) if out else [],
        result_text=out.get("final", "") if out else "",
        state=out if (debug and out) else None,
    )
```

