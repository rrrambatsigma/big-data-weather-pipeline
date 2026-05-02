import pandas as pd
from sqlalchemy import create_engine

CSV_PATH = "data/staging/produksi_staging.csv"

DB_URL = "postgresql+psycopg2://airflow:airflow@postgres:5432/airflow"

TABLE_NAME = "commodity_production"

df = pd.read_csv(CSV_PATH)

engine = create_engine(DB_URL)

df.to_sql(
    TABLE_NAME,
    engine,
    if_exists="replace",
    index=False
)

print(f"[OK] Loaded {len(df)} rows to table {TABLE_NAME}")