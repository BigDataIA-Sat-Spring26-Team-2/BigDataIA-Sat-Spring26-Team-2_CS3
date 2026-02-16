from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

def print_hello():
    print("Hello from Airflow!")
    return "Success"

with DAG(
    dag_id='test_simple_dag',
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
) as dag:
    
    task = PythonOperator(
        task_id='print_hello',
        python_callable=print_hello,
    )