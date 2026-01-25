import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DATA_DIR = Path("data/raw/instacart")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5433"))
PG_DB = os.getenv("PG_DB", "retail_db")
PG_USER = os.getenv("PG_USER", "retail_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "retail_pass")

ENGINE = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

TABLES = {
    "aisles": "aisles.csv",
    "departments": "departments.csv",
    "products": "products.csv",
    "orders": "orders.csv",
    "order_products_prior": "order_products__prior.csv",
    "order_products_train": "order_products__train.csv",
}

def load_csv(table_name: str, csv_name: str) -> None:
    path = DATA_DIR / csv_name
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    print(f"\nLoading {csv_name} -> {table_name}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Write table
    df.to_sql(
        table_name,
        ENGINE,
        if_exists="replace",
        index=False,
        chunksize=50_000,
        method="multi",
    )
    print(f"✅ {table_name}: {len(df):,} rows loaded")

def main():
    # quick connection test
    with ENGINE.connect() as conn:
        conn.execute(text("select 1"))
    print("✅ Connected to Postgres")

    for t, f in TABLES.items():
        load_csv(t, f)

    print("\n✅ All Instacart tables loaded to Postgres")

if __name__ == "__main__":
    main()
