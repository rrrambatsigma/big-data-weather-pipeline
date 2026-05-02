from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="commodity_etl_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:

    validate = BashOperator(
        task_id="validate_data",
        bash_command="cd /opt/airflow && python scripts/validate.py"
    )

    transform = BashOperator(
        task_id="transform_data",
        bash_command="cd /opt/airflow && python scripts/cleaning_komoditas.py"
    )

    load_staging = BashOperator(
        task_id="load_staging",
        bash_command="cd /opt/airflow && python scripts/load_staging.py"
    )

    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command="cd /opt/airflow && python scripts/load_postgres.py"
    )

    # urutan pipeline
    validate >> transform >> load_staging >> load_postgres