import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

CSV_PATH = BASE_DIR / "data" / "metadata" / "province_coordinates.csv"

SCHEMA_NAME = "schema_staging"
TABLE_NAME = "province_coordinates"


def build_database_url() -> str:
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
    )

    return df


def validate_dataframe(df: pd.DataFrame) -> None:
    required_columns = ["province", "latitude", "longitude"]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            "Kolom wajib tidak ditemukan di CSV: "
            + ", ".join(missing_columns)
        )

    if df.empty:
        raise ValueError("Data province coordinates kosong.")

    if df["province"].isna().any():
        raise ValueError("Ada province yang kosong.")

    if df["latitude"].isna().any():
        raise ValueError("Ada latitude yang kosong.")

    if df["longitude"].isna().any():
        raise ValueError("Ada longitude yang kosong.")

    df["latitude"] = pd.to_numeric(df["latitude"], errors="raise")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="raise")


def load_to_postgres(engine, df: pd.DataFrame) -> int:
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};"))

    df.to_sql(
        name=TABLE_NAME,
        con=engine,
        schema=SCHEMA_NAME,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )

    return len(df)


def validate_table(engine, expected_rows: int) -> None:
    query = text(
        f"""
        SELECT COUNT(*)
        FROM {SCHEMA_NAME}.{TABLE_NAME};
        """
    )

    with engine.connect() as connection:
        actual_rows = connection.execute(query).scalar()

    print(f"Validasi {SCHEMA_NAME}.{TABLE_NAME}: {actual_rows} rows")

    if actual_rows != expected_rows:
        raise ValueError(
            f"Jumlah row tidak cocok. Expected={expected_rows}, actual={actual_rows}"
        )


def main():
    validate_file(CSV_PATH)

    print("Membaca CSV province coordinates:")
    print(CSV_PATH)

    df = pd.read_csv(CSV_PATH)
    df = clean_column_names(df)
    validate_dataframe(df)

    database_url = build_database_url()

    print("Connect ke PostgreSQL:")
    print(database_url.split("@")[-1])

    engine = create_engine(database_url)

    rows = load_to_postgres(engine, df)
    validate_table(engine, rows)

    print(f"\nBerhasil load {rows} rows ke {SCHEMA_NAME}.{TABLE_NAME}")


if __name__ == "__main__":
    main()