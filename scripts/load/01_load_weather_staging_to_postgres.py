import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]

# Membaca file .env dari root project
load_dotenv(BASE_DIR / ".env")

STAGING_DIR = BASE_DIR / "data" / "staging" / "weather_plan_b"

CITY_CSV_PATH = STAGING_DIR / "weather_yearly_city_plan_b_available_2020_2024.csv"
PROVINCE_CSV_PATH = STAGING_DIR / "weather_yearly_province_plan_b_available_2020_2024.csv"
SUMMARY_CSV_PATH = STAGING_DIR / "weather_plan_b_available_transform_summary.csv"

SCHEMA_NAME = "schema_staging"

TABLES = [
    {
        "path": CITY_CSV_PATH,
        "table_name": "weather_yearly_city_plan_b_available",
    },
    {
        "path": PROVINCE_CSV_PATH,
        "table_name": "weather_yearly_province_plan_b_available",
    },
    {
        "path": SUMMARY_CSV_PATH,
        "table_name": "weather_plan_b_available_transform_summary",
    },
]


def build_database_url() -> str:
    """
    Ambil konfigurasi database dari .env.

    Manual dari Windows:
        POSTGRES_HOST=localhost
        POSTGRES_PORT=15432

    Dari Airflow Docker:
        POSTGRES_HOST=postgres
        POSTGRES_PORT=5432

    Di Airflow nanti bisa dioverride lewat bash_command DAG.
    """

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return database_url

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "15432")
    db = os.getenv("POSTGRES_DB")

    missing_env = []

    if not user:
        missing_env.append("POSTGRES_USER")

    if not password:
        missing_env.append("POSTGRES_PASSWORD")

    if not db:
        missing_env.append("POSTGRES_DB")

    if missing_env:
        raise ValueError(
            "Environment variable berikut belum ada di .env: "
            + ", ".join(missing_env)
        )

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def validate_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"File kosong: {path}")


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace("(", "", regex=False)
        .str.replace(")", "", regex=False)
    )

    return df


def load_csv(engine, csv_path: Path, table_name: str) -> int:
    validate_file(csv_path)

    print("\nMembaca CSV:")
    print(csv_path)

    df = pd.read_csv(csv_path)
    df = clean_column_names(df)

    print(f"Load {len(df)} rows ke {SCHEMA_NAME}.{table_name}")

    if df.empty:
        raise ValueError(f"Data kosong untuk {csv_path}")

    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};"))

    df.to_sql(
        name=table_name,
        con=engine,
        schema=SCHEMA_NAME,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )

    return len(df)


def validate_table(engine, table_name: str, expected_rows: int) -> None:
    query = text(
        f"""
        SELECT COUNT(*)
        FROM {SCHEMA_NAME}.{table_name};
        """
    )

    with engine.connect() as connection:
        actual_rows = connection.execute(query).scalar()

    print(f"Validasi {SCHEMA_NAME}.{table_name}: {actual_rows} rows")

    if actual_rows != expected_rows:
        raise ValueError(
            f"Jumlah row tidak cocok untuk {table_name}. "
            f"Expected={expected_rows}, actual={actual_rows}"
        )


def main():
    database_url = build_database_url()

    print("Connect ke PostgreSQL:")
    print(database_url.split("@")[-1])

    engine = create_engine(database_url)

    for table in TABLES:
        table_name = table["table_name"]
        csv_path = table["path"]

        rows = load_csv(
            engine=engine,
            csv_path=csv_path,
            table_name=table_name,
        )

        validate_table(
            engine=engine,
            table_name=table_name,
            expected_rows=rows,
        )

    print("\nSemua weather staging berhasil diload ke PostgreSQL.")


if __name__ == "__main__":
    main()