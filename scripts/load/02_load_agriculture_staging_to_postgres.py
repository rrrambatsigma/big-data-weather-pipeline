import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]

# Membaca file .env dari root project
load_dotenv(BASE_DIR / ".env")

AGRICULTURE_CSV_PATH = (
    BASE_DIR / "data" / "staging" / "agriculture" / "produksi_komoditas_clean_long.csv"
)

SCHEMA_NAME = "schema_staging"
TABLE_NAME = "agriculture_production_staging"


def build_database_url() -> str:
    """
    Ambil konfigurasi database dari .env.

    Manual dari Windows:
        POSTGRES_HOST=localhost
        POSTGRES_PORT=15432

    Dari Airflow Docker:
        POSTGRES_HOST=postgres
        POSTGRES_PORT=5432

    Nilai ini bisa dioverride dari DAG Airflow.
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
    """
    Membersihkan nama kolom agar lebih aman digunakan di PostgreSQL.

    Contoh:
        Provinsi  -> provinsi
        Komoditas -> komoditas
        Produksi  -> produksi
    """

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


def normalize_province_name(value: str) -> str:
    """
    Menyamakan format nama provinsi pertanian dengan data cuaca.

    Contoh:
        ACEH -> Aceh
        BALI -> Bali
        BANTEN -> Banten
        JAWA BARAT -> Jawa Barat
        DKI JAKARTA -> DKI Jakarta
        DI YOGYAKARTA -> DI Yogyakarta
    """

    if pd.isna(value):
        return value

    province = str(value).strip()

    if province == "":
        return province

    upper_province = province.upper()

    special_cases = {
        "DKI JAKARTA": "DKI Jakarta",
        "DI YOGYAKARTA": "DI Yogyakarta",
    }

    if upper_province in special_cases:
        return special_cases[upper_province]

    return province.title()


def clean_agriculture_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Membersihkan data pertanian sebelum masuk PostgreSQL.

    Hasil akhir kolom:
        province
        commodity
        production

    Tujuannya agar nama kolom dan format province cocok dengan data cuaca.
    """

    df = df.copy()

    # Bersihkan nama kolom awal dari CSV
    df = clean_column_names(df)

    # Rename kolom agar sama arah dengan data cuaca
    df = df.rename(
        columns={
            "provinsi": "province",
            "komoditas": "commodity",
            "produksi": "production",
        }
    )

    required_columns = ["province", "commodity", "production"]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom wajib tidak ditemukan di CSV pertanian: "
            + ", ".join(missing_columns)
        )

    # Samakan format province dengan data cuaca
    df["province"] = df["province"].apply(normalize_province_name)

    # Bersihkan komoditas
    df["commodity"] = df["commodity"].astype(str).str.strip()

    # Pastikan production bertipe angka
    df["production"] = pd.to_numeric(df["production"], errors="coerce")

    before_drop = len(df)

    # Hapus data yang kolom pentingnya kosong/tidak valid
    df = df.dropna(subset=["province", "commodity", "production"])

    # Hapus baris jika province/commodity kosong string
    df = df[
        (df["province"].astype(str).str.strip() != "")
        & (df["commodity"].astype(str).str.strip() != "")
    ]

    after_drop = len(df)
    dropped_rows = before_drop - after_drop

    if dropped_rows > 0:
        print(f"Drop {dropped_rows} rows karena data penting kosong/tidak valid.")

    if df.empty:
        raise ValueError("Data pertanian kosong setelah cleaning.")

    return df


def load_csv_to_postgres(engine) -> int:
    validate_file(AGRICULTURE_CSV_PATH)

    print("\nMembaca CSV pertanian:")
    print(AGRICULTURE_CSV_PATH)

    df = pd.read_csv(AGRICULTURE_CSV_PATH)
    df = clean_agriculture_data(df)

    print("\nPreview data pertanian setelah cleaning:")
    print(df.head())

    print("\nKolom setelah cleaning:")
    print(df.columns.tolist())

    print("\nDaftar province unik setelah normalisasi:")
    print(sorted(df["province"].unique().tolist()))

    print(f"\nLoad {len(df)} rows ke {SCHEMA_NAME}.{TABLE_NAME}")

    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};"))

    df.to_sql(
        name=TABLE_NAME,
        con=engine,
        schema=SCHEMA_NAME,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
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

    print(f"\nValidasi {SCHEMA_NAME}.{TABLE_NAME}: {actual_rows} rows")

    if actual_rows != expected_rows:
        raise ValueError(
            f"Jumlah row tidak cocok. "
            f"Expected={expected_rows}, actual={actual_rows}"
        )


def preview_loaded_table(engine) -> None:
    query = text(
        f"""
        SELECT *
        FROM {SCHEMA_NAME}.{TABLE_NAME}
        LIMIT 10;
        """
    )

    with engine.connect() as connection:
        result = connection.execute(query)
        rows = result.fetchall()

    print(f"\nPreview table {SCHEMA_NAME}.{TABLE_NAME}:")
    for row in rows:
        print(row)


def main():
    database_url = build_database_url()

    print("Connect ke PostgreSQL:")
    print(database_url.split("@")[-1])

    engine = create_engine(database_url)

    rows = load_csv_to_postgres(engine)

    validate_table(
        engine=engine,
        expected_rows=rows,
    )

    preview_loaded_table(engine)

    print(
        f"\nData pertanian berhasil diload ke PostgreSQL: "
        f"{SCHEMA_NAME}.{TABLE_NAME}"
    )


if __name__ == "__main__":
    main()