from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

import os, json, time, uuid, tempfile
import mlflow


from agents.promo_agent import build_promo_graph

app = FastAPI(title="Retail Intelligence Copilot API", version="0.2.0")

# Serve UI + static
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/")
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

class BundleItem(BaseModel):
    product_id: int
    product_name: str
    co_purchase_count: int
    reorder_rate: float
    total_units: int


class AnchorModel(BaseModel):
    product_id: int
    product_name: str
    aisle_id: int
    department_id: int
    reorder_rate: float
    total_units: int
    total_orders: int


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


class PromoResponse(BaseModel):
    query: str
    bundles: List[PromoBundle]
    result_text: str
    state: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/promo-recommendations", response_model=PromoResponse)
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

