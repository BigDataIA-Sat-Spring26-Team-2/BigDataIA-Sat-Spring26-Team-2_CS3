FROM apache/airflow:2.8.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies
RUN pip install --no-cache-dir \
    structlog \
    pydantic>=2.0 \
    boto3 \
    snowflake-connector-python \
    sec-edgar-downloader \
    pdfplumber \
    pypdf2 \
    apache-airflow-providers-snowflake \
    apache-airflow-providers-amazon