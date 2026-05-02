from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

# fungsi yang akan dijalankan
def say_hello():
    print("Hello World")

# definisi DAG
with DAG(
    dag_id='hello_world_dag',
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,   
    catchup=False
) as dag:

    hello_task = PythonOperator(
        task_id='say_hello_task',
        python_callable=say_hello
    )

    hello_task