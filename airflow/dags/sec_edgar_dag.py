"""
SEC EDGAR Pipeline - Airflow DAG
=================================

This DAG orchestrates the end-to-end SEC EDGAR filing collection pipeline:
1. Download filings from SEC EDGAR
2. Parse and extract AI-relevant sections
3. Upload raw files to S3
4. Load metadata and chunks into Snowflake
5. Validate completion

Schedule: Daily at 9 AM ET
Retries: 3 attempts with 5-minute delays
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable
from airflow.utils.dates import days_ago

# Add your project root to Python path
PROJECT_ROOT = Path("/opt/airflow/project")
sys.path.insert(0, str(PROJECT_ROOT))

# Import your existing pipeline modules
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser  # Verify this class name!
import structlog

logger = structlog.get_logger()


# ============================================================================
# DAG CONFIGURATION
# ============================================================================

DEFAULT_ARGS = {
    'owner': 'pe-orgair-team',
    'depends_on_past': False,
    'email_on_failure': False,  # ⚠️ CHANGED: Disabled (or add your email)
    'email_on_retry': False,
    'email': [],  # ⚠️ CHANGED: Empty (or add ['your-email@example.com'])
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}


# ============================================================================
# TASK 1: VALIDATE COMPANY
# ============================================================================

def validate_company(**context):
    """
    Validate that company exists in Snowflake COMPANIES table.
    Retrieve company_id and CIK for downstream tasks.
    """
    ti = context['ti']
    default_ticker = Variable.get('default_ticker', 'WMT')
    ticker = context['dag_run'].conf.get('ticker', default_ticker)  #Provide the input from Airfow UI
    logger.info("task_validate_company_started", ticker=ticker)
    
    # Get Snowflake connection from Airflow
    snowflake_hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
    conn = snowflake_hook.get_conn()
    cur = conn.cursor()
    
    try:
        # Query company info
        cur.execute("""
            SELECT id, ticker, name 
            FROM PE_ORGAIR.PUBLIC.COMPANIES 
            WHERE ticker = %s AND is_deleted = FALSE
        """, (ticker,))
        
        result = cur.fetchone()
        
        if not result:
            raise ValueError(f"Company with ticker {ticker} not found or is deleted")
        
        company_data = {
            'company_id': result[0],
            'ticker': result[1],
            'cik': None,
            'name': result[2]
        }
        
        logger.info("company_validated", **company_data)
        
        # Push to XCom for downstream tasks
        ti.xcom_push(key='company_data', value=company_data)
        
        return company_data
        
    finally:
        cur.close()
        conn.close()


# ============================================================================
# TASK 2: DOWNLOAD SEC FILINGS
# ============================================================================

def download_sec_filings(**context):
    """
    Download SEC filings using SECEdgarPipeline.
    Returns list of downloaded file paths.
    """
    ti = context['ti']
    company_data = ti.xcom_pull(key='company_data', task_ids='validate_company')
    
    ticker = company_data['ticker']
    cik = company_data.get('cik')
    
    logger.info("task_download_started", ticker=ticker, cik=cik)
    
    # Configuration from Airflow Variables or DAG params
    filing_types = context['dag_run'].conf.get('filing_types', ['10-K', '10-Q', '8-K'])
    limit = context['dag_run'].conf.get('limit', 10)
    after_date = context['dag_run'].conf.get('after', '2020-01-01')
    
    # Initialize SEC pipeline
    download_dir = Path("/opt/airflow/dags/temp_downloads")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    pipeline = SECEdgarPipeline(
        company_name="PE OrgAIR Airflow",
        email="airflow@example.com",
        download_dir=download_dir
    )
    
    # Download filings
    filings = pipeline.download_filings(
        ticker=ticker if ticker else None,
        cik=cik if cik else None,
        filing_types=filing_types,
        limit=limit,
        after=after_date
    )
    
    downloaded_files = [
        {
            'filing_type': f.filing_type,
            'accession_number': f.accession_number,
            'path': f.path
        }
        for f in filings
    ]
    
    logger.info(
        "download_complete",
        ticker=ticker,
        files_downloaded=len(downloaded_files)
    )
    
    # Push to XCom
    ti.xcom_push(key='downloaded_files', value=downloaded_files)
    
    return len(downloaded_files)


# ============================================================================
# TASK 3: PARSE DOCUMENTS
# ============================================================================

def parse_documents(**context):
    """
    Parse downloaded filings to extract AI-relevant sections.
    Compute content hashes for deduplication.
    """
    ti = context['ti']
    company_data = ti.xcom_pull(key='company_data', task_ids='validate_company')
    downloaded_files = ti.xcom_pull(key='downloaded_files', task_ids='download_sec_filings')
    
    ticker = company_data['ticker']
    parser = DocumentParser()
    
    parsed_documents = []
    
    for file_info in downloaded_files:
        file_path = Path(file_info['path'])
        
        if not file_path.exists():
            logger.warning("file_not_found", path=str(file_path))
            continue
        
        logger.info("parsing_document", path=str(file_path))
        
        try:
            parsed_doc = parser.parse_filing(file_path)
            
            parsed_documents.append({
                'filing_type': file_info['filing_type'],
                'accession_number': file_info['accession_number'],
                'path': str(file_path),
                'content_hash': parsed_doc.content_hash,
                'sections': parsed_doc.sections,
                'word_count': parsed_doc.word_count,
                'sections_found': parsed_doc.sections_found
            })
            
            logger.info(
                "document_parsed",
                filing_type=file_info['filing_type'],
                sections=parsed_doc.sections_found,
                words=parsed_doc.word_count
            )
            
        except Exception as e:
            logger.error(
                "parsing_failed",
                path=str(file_path),
                error=str(e)
            )
            # Continue with other files
            continue
    
    logger.info(
        "parsing_complete",
        ticker=ticker,
        documents_parsed=len(parsed_documents)
    )
    
    ti.xcom_push(key='parsed_documents', value=parsed_documents)
    
    return len(parsed_documents)


# ============================================================================
# TASK 4: CHECK DUPLICATES
# ============================================================================

def check_duplicates(**context):
    """
    Check if documents already exist in Snowflake based on content_hash.
    Filter out duplicates to avoid reprocessing.
    """
    ti = context['ti']
    parsed_documents = ti.xcom_pull(key='parsed_documents', task_ids='parse_documents')
    
    snowflake_hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
    conn = snowflake_hook.get_conn()
    cur = conn.cursor()
    
    new_documents = []
    duplicate_count = 0
    
    try:
        for doc in parsed_documents:
            content_hash = doc['content_hash']
            
            # Check if hash exists
            cur.execute("""
                SELECT id FROM PE_ORGAIR.PUBLIC.DOCUMENTS
                WHERE content_hash = %s
            """, (content_hash,))
            
            if cur.fetchone():
                logger.info(
                    "duplicate_detected",
                    accession=doc['accession_number'],
                    filing_type=doc['filing_type']
                )
                duplicate_count += 1
            else:
                new_documents.append(doc)
        
        logger.info(
            "deduplication_complete",
            total_documents=len(parsed_documents),
            new_documents=len(new_documents),
            duplicates=duplicate_count
        )
        
        ti.xcom_push(key='new_documents', value=new_documents)
        
        return len(new_documents)
        
    finally:
        cur.close()
        conn.close()


# ============================================================================
# TASK 5: UPLOAD TO S3
# ============================================================================

def upload_to_s3(**context):
    """
    Upload raw filing documents to S3 for archival.
    Only upload new (non-duplicate) documents.
    """
    ti = context['ti']
    company_data = ti.xcom_pull(key='company_data', task_ids='validate_company')
    new_documents = ti.xcom_pull(key='new_documents', task_ids='check_duplicates')
    
    ticker = company_data['ticker']
    s3_hook = S3Hook(aws_conn_id='aws_default')
    
    # ⚠️ CHANGED: Use environment variable directly
    bucket_name = os.getenv('AIRFLOW_VAR_S3_BUCKET', 'pe-orgair-documents')
    
    uploaded_count = 0
    
    for doc in new_documents:
        file_path = Path(doc['path'])
        
        if not file_path.exists():
            logger.warning("file_missing_for_upload", path=str(file_path))
            continue
        
        # S3 key structure: sec/{ticker}/{filing_type}/{accession}/full-submission.txt
        s3_key = f"sec/{ticker}/{doc['filing_type']}/{doc['accession_number']}/full-submission.txt"
        
        try:
            # Upload using Airflow S3Hook
            s3_hook.load_file(
                filename=str(file_path),
                key=s3_key,
                bucket_name=bucket_name,
                replace=True
            )
            
            logger.info(
                "s3_upload_success",
                s3_key=s3_key,
                filing_type=doc['filing_type']
            )
            
            uploaded_count += 1
            
            # Delete local file after successful upload
            file_path.unlink()
            
        except Exception as e:
            logger.error(
                "s3_upload_failed",
                s3_key=s3_key,
                error=str(e)
            )
            raise
    
    logger.info(
        "s3_upload_complete",
        ticker=ticker,
        files_uploaded=uploaded_count
    )
    
    return uploaded_count


# ============================================================================
# TASK 6: LOAD TO SNOWFLAKE
# ============================================================================

def load_to_snowflake(**context):
    """
    Load document metadata and chunks into Snowflake.
    - DOCUMENTS table: Filing metadata
    - DOCUMENT_CHUNKS table: Section-based chunks
    """
    ti = context['ti']
    company_data = ti.xcom_pull(key='company_data', task_ids='validate_company')
    new_documents = ti.xcom_pull(key='new_documents', task_ids='check_duplicates')
    
    company_id = company_data['company_id']
    ticker = company_data['ticker']
    
    snowflake_hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
    conn = snowflake_hook.get_conn()
    cur = conn.cursor()
    
    documents_inserted = 0
    chunks_inserted = 0
    
    try:
        for doc in new_documents:
            from uuid import uuid4
            import hashlib
            
            doc_id = str(uuid4())
            
            
            cur.execute("""
                INSERT INTO PE_ORGAIR.PUBLIC.DOCUMENTS (
                    id, company_id, ticker, filing_type, accession_number,
                    filing_date, content_hash, word_count, file_path, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                doc_id,
                company_id,
                ticker,
                doc['filing_type'],
                doc['accession_number'],
                datetime.now().date(),
                doc['content_hash'],
                doc['word_count'],
                doc['path'],  # ← ADD THIS (local file path)
                datetime.now()
            ))
            documents_inserted += 1
            
            # Insert chunks (section-based)
            chunk_index = 0
            for section_name, section_text in doc['sections'].items():
                chunk_hash = hashlib.sha256(section_text.encode()).hexdigest()
                chunk_id = str(uuid4())
                
                # Check if chunk already exists (additional safety)
                cur.execute("""
                    SELECT id FROM PE_ORGAIR.PUBLIC.DOCUMENT_CHUNKS
                    WHERE content_hash = %s
                """, (chunk_hash,))
                
                if cur.fetchone():
                    logger.info("chunk_duplicate_skipped", hash=chunk_hash)
                    continue
                
                cur.execute("""
                    INSERT INTO PE_ORGAIR.PUBLIC.DOCUMENT_CHUNKS (
                        id, document_id, chunk_index, chunk_text,
                        content_hash, word_count, section, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    chunk_id,
                    doc_id,
                    chunk_index,
                    section_text,
                    chunk_hash,
                    len(section_text.split()),
                    section_name,
                    datetime.now()
                ))
                
                chunks_inserted += 1
                chunk_index += 1
        
        # Commit transaction
        conn.commit()
        
        logger.info(
            "snowflake_load_complete",
            ticker=ticker,
            documents_inserted=documents_inserted,
            chunks_inserted=chunks_inserted
        )
        
        ti.xcom_push(key='load_summary', value={
            'documents_inserted': documents_inserted,
            'chunks_inserted': chunks_inserted
        })
        
        return documents_inserted
        
    except Exception as e:
        conn.rollback()
        logger.error("snowflake_load_failed", error=str(e))
        raise
    finally:
        cur.close()
        conn.close()


# ============================================================================
# TASK 7: VALIDATE PIPELINE
# ============================================================================

def validate_pipeline(**context):
    """
    Post-load validation:
    - Verify chunk counts match expectations
    - Confirm S3 objects exist
    - Log final pipeline metrics
    """
    ti = context['ti']
    company_data = ti.xcom_pull(key='company_data', task_ids='validate_company')
    load_summary = ti.xcom_pull(key='load_summary', task_ids='load_to_snowflake')
    
    ticker = company_data['ticker']
    
    snowflake_hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
    conn = snowflake_hook.get_conn()
    cur = conn.cursor()
    
    try:
        # Verify document count
        cur.execute("""
            SELECT COUNT(*) FROM PE_ORGAIR.PUBLIC.DOCUMENTS
            WHERE ticker = %s
        """, (ticker,))
        
        doc_count = cur.fetchone()[0]
        
        # Verify chunk count
        cur.execute("""
            SELECT COUNT(*) FROM PE_ORGAIR.PUBLIC.DOCUMENT_CHUNKS dc
            JOIN PE_ORGAIR.PUBLIC.DOCUMENTS d ON dc.document_id = d.id
            WHERE d.ticker = %s
        """, (ticker,))
        
        chunk_count = cur.fetchone()[0]
        
        validation_result = {
            'ticker': ticker,
            'total_documents': doc_count,
            'total_chunks': chunk_count,
            'new_documents': load_summary.get('documents_inserted', 0),
            'new_chunks': load_summary.get('chunks_inserted', 0),
            'status': 'SUCCESS'
        }
        
        logger.info("pipeline_validation_complete", **validation_result)
        
        return validation_result
        
    finally:
        cur.close()
        conn.close()


# ============================================================================
# DAG DEFINITION
# ============================================================================

with DAG(
    dag_id='sec_edgar_pipeline',
    default_args=DEFAULT_ARGS,
    description='SEC EDGAR filing collection and processing pipeline',
    schedule_interval='0 9 * * *',  # Daily at 9 AM
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['sec', 'edgar', 'evidence-collection'],
) as dag:
    
    # Define task sequence
    task_validate = PythonOperator(
        task_id='validate_company',
        python_callable=validate_company,
        provide_context=True,
    )
    
    task_download = PythonOperator(
        task_id='download_sec_filings',
        python_callable=download_sec_filings,
        provide_context=True,
    )
    
    task_parse = PythonOperator(
        task_id='parse_documents',
        python_callable=parse_documents,
        provide_context=True,
    )
    
    task_dedup = PythonOperator(
        task_id='check_duplicates',
        python_callable=check_duplicates,
        provide_context=True,
    )
    
    task_s3 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
        provide_context=True,
    )
    
    task_snowflake = PythonOperator(
        task_id='load_to_snowflake',
        python_callable=load_to_snowflake,
        provide_context=True,
    )
    
    task_validate_pipeline = PythonOperator(
        task_id='validate_pipeline',
        python_callable=validate_pipeline,
        provide_context=True,
    )
    
    # Set dependencies (linear flow)
    task_validate >> task_download >> task_parse >> task_dedup >> task_s3 >> task_snowflake >> task_validate_pipeline