import os 
import pandas as pd
from sqlalchemy import create_engine

PG_HOST = os.getenv("PG_HOST","localhost")
PG_PORT = int(os.getenv("PG_PORT","5433"))
PG_DB = os.getenv("PG_DB", "retail_db")
PG_USER = os.getenv("PG_USER", "retail_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "retail_pass")

ENGINE = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

OUT_PATH = "rag/docs_products.parquet"

QUERY = """
SELECT
  p.product_id,
  p.product_name,
  p.aisle_id,
  p.department_id,
  COALESCE(f.total_units, 0) AS total_units,
  COALESCE(f.total_orders, 0) AS total_orders,
  COALESCE(f.reorder_rate, 0) AS reorder_rate
FROM products p
LEFT JOIN feat_sku_velocity f
  ON p.product_id = f.product_id;
"""

def build_doc(row: pd.Series) -> str:
    # A compact, LLM-friendly “product card”
    return (
        f"Product ID: {row['product_id']}\n"
        f"Name: {row['product_name']}\n"
        f"Aisle ID: {row['aisle_id']} | Department ID: {row['department_id']}\n"
        f"Demand: total_units={row['total_units']}, total_orders={row['total_orders']}, "
        f"reorder_rate={float(row['reorder_rate']):.3f}\n"
        f"Use: Retail catalog item (SKU) with demand signals for ranking and recommendations."
    )

def main():
    df = pd.read_sql(QUERY, ENGINE)
    df["text"] = df.apply(build_doc, axis=1)
    df[["product_id", "text"]].to_parquet(OUT_PATH, index=False)
    print(f"✅ Wrote {len(df):,} product docs to {OUT_PATH}")

if __name__ == "__main__":
    main()