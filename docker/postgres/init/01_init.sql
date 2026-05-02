CREATE DATABASE airflow_db;
CREATE USER airflow_user WITH PASSWORD 'airflow_password';
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO airflow_user;

\c airflow_db;

GRANT ALL ON SCHEMA public TO airflow_user;
GRANT CREATE ON SCHEMA public TO airflow_user;
ALTER SCHEMA public OWNER TO airflow_user;

\c ipbd_db;

CREATE SCHEMA IF NOT EXISTS schema_raw;
CREATE SCHEMA IF NOT EXISTS schema_staging;
CREATE SCHEMA IF NOT EXISTS schema_warehouse;
CREATE SCHEMA IF NOT EXISTS schema_serving;

GRANT ALL PRIVILEGES ON SCHEMA schema_raw TO ipbd_user;
GRANT ALL PRIVILEGES ON SCHEMA schema_staging TO ipbd_user;
GRANT ALL PRIVILEGES ON SCHEMA schema_warehouse TO ipbd_user;
GRANT ALL PRIVILEGES ON SCHEMA schema_serving TO ipbd_user;