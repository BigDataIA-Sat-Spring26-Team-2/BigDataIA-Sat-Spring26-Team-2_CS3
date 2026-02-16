# Airflow Orchestration - SEC EDGAR Pipeline

## Quick Start (5 Minutes)

### Prerequisites
- Docker Desktop installed and running
- Snowflake account credentials
- AWS S3 credentials

### Step 1: Configure Credentials
```bash
cd airflow
cp .env.example .env
```

Edit `.env` and add your credentials:
- `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ACCOUNT`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET`

**Important:** URL-encode special characters in passwords!
- `@` → `%40`
- `#` → `%23`

### Step 2: Start Airflow
```bash
# Initialize database (first time only)
docker-compose -f docker-compose-airflow.yml up airflow-init

# Start services
docker-compose -f docker-compose-airflow.yml up -d

# Wait 30 seconds for startup
```

### Step 3: Access Airflow UI

1. Open: http://localhost:8080
2. Login:
   - Username: `admin`
   - Password: `admin123` (from your .env)

### Step 4: Trigger Pipeline

1. Find `sec_edgar_pipeline` in DAG list
2. Click ▶️ play button
3. Watch tasks execute in Graph view

### Step 5: Verify Results

**Snowflake:**
```sql
SELECT * FROM PE_ORGAIR.PUBLIC.DOCUMENTS 
WHERE ticker = 'WMT' 
ORDER BY created_at DESC;
```

**S3:**
```bash
aws s3 ls s3://your-bucket/sec/WMT/ --recursive
```

## Stopping Airflow
```bash
docker-compose -f docker-compose-airflow.yml down
```

## Troubleshooting

**Port 8080 in use:**
Change port in docker-compose-airflow.yml:
```yaml
ports:
  - "8081:8080"  # Use 8081 instead
```

**Port 5432 in use (PostgreSQL):**
Already configured to use 5433 externally.

**DAG not appearing:**
```bash
# Check logs
docker-compose -f docker-compose-airflow.yml logs airflow-scheduler

# List DAGs
docker-compose -f docker-compose-airflow.yml exec airflow-scheduler airflow dags list
```

**Task failing:**
- Click task in Graph view
- Click "Log" to see error
- Common issues: Missing company in Snowflake, incorrect credentials

## Architecture
```
SEC EDGAR → Download → Parse → Dedup → S3 Upload → Snowflake Load → Validate
```

**Schedule:** Daily at 9:00 AM UTC

**Default ticker:** WMT (change in sec_edgar_dag.py line 68)

## Files

- `docker-compose-airflow.yml` - Infrastructure setup
- `Dockerfile` - Custom image with dependencies
- `.env.example` - Configuration template
- `.airflowignore` - Prevents scanning project folder
- `dags/sec_edgar_dag.py` - Pipeline orchestration

## Support

For issues, check:
1. Container logs: `docker-compose -f docker-compose-airflow.yml logs`
2. Airflow UI task logs
3. Verify credentials in `.env`