import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def build_database_url() -> str:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "15432")
    db = os.getenv("POSTGRES_DB")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def main():
    engine = create_engine(build_database_url())

    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database(), current_user;")).fetchone()

    print("Koneksi PostgreSQL berhasil.")
    print("Database:", result[0])
    print("User:", result[1])


if __name__ == "__main__":
    main()