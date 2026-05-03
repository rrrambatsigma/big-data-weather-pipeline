from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator


BASE_DIR = Path(__file__).resolve().parents[1]

LOAD_SCRIPT_PATH = (
    BASE_DIR / "scripts" / "load" / "03_load_province_coordinates_to_postgres.py"
)

default_args = {
    "owner": "rambat",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
}


with DAG(
    dag_id="province_coordinates_staging_dag",
    description="Load province coordinates CSV to PostgreSQL schema_staging",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["province", "coordinates", "staging", "postgres"],
) as dag:

    load_province_coordinates_to_postgres = BashOperator(
        task_id="load_province_coordinates_to_postgres",
        bash_command=(
            "set -e && "
            "cd {{ params.base_dir }} && "
            "echo '=== Current directory ===' && "
            "pwd && "
            "echo '=== Check province coordinates CSV ===' && "
            "ls -lah data/metadata/province_coordinates.csv && "
            "echo '=== Load province coordinates to PostgreSQL ===' && "
            "POSTGRES_USER=ipbd_user "
            "POSTGRES_PASSWORD=ipbd_password "
            "POSTGRES_DB=ipbd_db "
            "POSTGRES_HOST=postgres "
            "POSTGRES_PORT=5432 "
            "python {{ params.load_script_path }}"
        ),
        params={
            "base_dir": str(BASE_DIR),
            "load_script_path": str(LOAD_SCRIPT_PATH),
        },
    )

    load_province_coordinates_to_postgres