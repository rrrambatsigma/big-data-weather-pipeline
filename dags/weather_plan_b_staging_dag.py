from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "ipbd",
    "retries": 1,
}


with DAG(
    dag_id="weather_plan_b_staging_pipeline",
    default_args=default_args,
    description="Validate, transform, and load Weather Plan B available data to PostgreSQL",
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["ipbd", "weather", "plan_b", "staging"],
) as dag:

    validate_weather_raw_available = BashOperator(
        task_id="validate_weather_raw_available",
        bash_command=(
            "cd /opt/airflow && "
            "python /opt/airflow/scripts/validate/01_validate_weather_plan_b_available.py"
        ),
    )

    transform_weather_yearly_available = BashOperator(
        task_id="transform_weather_yearly_available",
        bash_command=(
            "cd /opt/airflow && "
            "python /opt/airflow/scripts/transform/04_transform_weather_yearly_plan_b_available.py"
        ),
    )

    load_weather_staging_to_postgres = BashOperator(
        task_id="load_weather_staging_to_postgres",
        bash_command=(
            "cd /opt/airflow && "
            "POSTGRES_HOST=postgres "
            "POSTGRES_PORT=5432 "
            "POSTGRES_DB=ipbd_db "
            "POSTGRES_USER=ipbd_user "
            "POSTGRES_PASSWORD=ipbd_password "
            "python /opt/airflow/scripts/load/01_load_weather_staging_to_postgres.py"
        ),
    )

    (
        validate_weather_raw_available
        >> transform_weather_yearly_available
        >> load_weather_staging_to_postgres
    )