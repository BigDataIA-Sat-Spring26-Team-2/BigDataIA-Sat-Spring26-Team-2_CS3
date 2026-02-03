# app/routers/documents.py
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException, status, Request
from fastapi.responses import FileResponse, StreamingResponse
from uuid import UUID
from typing import List, Optional
import zipfile
import io
import boto3
from botocore.exceptions import ClientError
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

# PDF generation imports
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_JUSTIFY
from io import BytesIO

from app.services import sec_edgar_service
from app.config import get_settings

router = APIRouter(prefix="/documents", tags=["Documents"])

BASE_SEC_DIR = Path("data/raw/sec").resolve()

logger = logging.getLogger(__name__)


limiter = Limiter(key_func=get_remote_address)


def create_pdf_from_text(text_content: str, title: str = "SEC Filing") -> bytes:
    """
    Convert text content to a formatted PDF.
    
    Args:
        text_content: The text to convert
        title: Title for the PDF document
        
    Returns:
        PDF file as bytes
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Justify',
        alignment=TA_JUSTIFY,
        fontSize=10,
        leading=12
    ))
    
    # Add title
    title_style = styles['Heading1']
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Split content into paragraphs and add to PDF
    # Handle very long text by chunking
    max_chunk_size = 50000  # ReportLab can struggle with huge paragraphs
    
    if len(text_content) > max_chunk_size:
        # For very large documents, split into sections
        chunks = [text_content[i:i+max_chunk_size] 
                  for i in range(0, len(text_content), max_chunk_size)]
        
        for idx, chunk in enumerate(chunks):
            # Split by double newlines to preserve some structure
            paragraphs = chunk.split('\n\n')
            
            for para_text in paragraphs:
                if para_text.strip():
                    # Clean up the text for PDF
                    cleaned_text = para_text.replace('\n', ' ').strip()
                    # Escape special characters for ReportLab
                    cleaned_text = cleaned_text.replace('&', '&amp;')
                    cleaned_text = cleaned_text.replace('<', '&lt;')
                    cleaned_text = cleaned_text.replace('>', '&gt;')
                    
                    try:
                        p = Paragraph(cleaned_text, styles['Justify'])
                        elements.append(p)
                        elements.append(Spacer(1, 0.1*inch))
                    except Exception as e:
                        # If paragraph fails, add as preformatted text
                        elements.append(Paragraph(f"[Content section {idx}]", styles['Normal']))
                        elements.append(Spacer(1, 0.1*inch))
            
            # Add page break between large chunks
            if idx < len(chunks) - 1:
                elements.append(PageBreak())
    else:
        # For smaller documents, process normally
        paragraphs = text_content.split('\n\n')
        
        for para_text in paragraphs[:1000]:  # Limit to first 1000 paragraphs for safety
            if para_text.strip():
                cleaned_text = para_text.replace('\n', ' ').strip()
                cleaned_text = cleaned_text.replace('&', '&amp;')
                cleaned_text = cleaned_text.replace('<', '&lt;')
                cleaned_text = cleaned_text.replace('>', '&gt;')
                
                try:
                    p = Paragraph(cleaned_text, styles['Justify'])
                    elements.append(p)
                    elements.append(Spacer(1, 0.1*inch))
                except:
                    # Skip problematic paragraphs
                    continue
    
    # Build PDF
    try:
        doc.build(elements)
    except Exception as e:
        # If PDF generation fails, create a simple error PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        error_elements = [
            Paragraph(f"PDF Generation Error", styles['Heading1']),
            Spacer(1, 0.2*inch),
            Paragraph(f"Could not generate PDF for this document. Error: {str(e)}", styles['Normal']),
            Spacer(1, 0.2*inch),
            Paragraph("Please use the .txt version of this file.", styles['Normal'])
        ]
        doc.build(error_elements)
    
    buffer.seek(0)
    return buffer.read()


@router.post(
    "/sec-edgar/download",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/hour")  # Rate limit - 10 downloads per hour per IP
async def download_sec_filings(
    request: Request,  # Required for rate limiting
    company_id: UUID = Query(...),
    ticker: Optional[str] = Query(None, min_length=1, max_length=10),
    cik: Optional[str] = Query(None, min_length=10, max_length=10),
    filing_types: List[str] = Query(default=["10-K", "10-Q", "8-K"]),
    after: str = Query(default="2020-01-01"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Download SEC filings for a company and store in S3 and Snowflake.
    
    Rate limit: 10 requests per hour per IP address.
    This is a resource-intensive operation (downloads, parsing, S3 uploads, DB inserts).
    """
    if not ticker and not cik:
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")
    if ticker:
        ticker = ticker.upper()

    return sec_edgar_service.run_sec_download_for_company(
        company_id=company_id,
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )


@router.get("/file", response_class=FileResponse, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")  #  Rate limit - 100 file downloads per minute
async def download_local_file(
    request: Request,  # Required for rate limiting
    path: str = Query(...)
):
    """
    Download a local file (legacy endpoint, files are now in S3).
    
    Rate limit: 100 requests per minute per IP address.
    Simple file serving, higher limit is acceptable.
    """
    p = Path(path).resolve()

    if BASE_SEC_DIR not in p.parents and p != BASE_SEC_DIR:
        raise HTTPException(status_code=403, detail="Forbidden path")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(p), filename=p.name, media_type="text/plain")


@router.get("/sec-edgar/download-zip", response_class=StreamingResponse)
@limiter.limit("10/hour")  # Rate limit - 5 ZIP downloads per hour (stricter)
async def download_filings_as_zip(
    request: Request,  # Required for rate limiting
    ticker: str = Query(..., min_length=1, max_length=10),
    filing_types: List[str] = Query(default=["10-K", "10-Q", "8-K"]),
    include_pdf: bool = Query(default=False),
):
    """
    Download all SEC filings for a ticker as a ZIP file from S3.
    
    Rate limit: 5 requests per hour per IP address.
    This is the most resource-intensive endpoint (S3 API calls + CPU for PDF generation).
    
    Args:
        ticker: Company ticker symbol
        filing_types: List of filing types to include
        include_pdf: If True, includes PDF versions (slower). If False, only .txt files.
    
    Returns:
        ZIP file containing requested filings
        
    ZIP structure (with include_pdf=True):
    ├── 10-K/
    │   ├── 0000320193-23-000106/
    │   │   ├── full-submission.txt
    │   │   └── full-submission.pdf
    │   └── 0000320193-24-000123/
    │       ├── full-submission.txt
    │       └── full-submission.pdf
    └── 10-Q/
        └── ...
    """
    ticker = ticker.upper()
    settings = get_settings()
    
    logger.info(f"Creating ZIP for {ticker}, filing_types={filing_types}, include_pdf={include_pdf}")
    
    # Initialize S3 client
    try:
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        s3_client = session.client("s3")
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize S3 client: {str(e)}"
        )
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        files_added = 0
        pdfs_generated = 0
        
        for filing_type in filing_types:
            prefix = f"sec/{ticker}/{filing_type}/"
            
            try:
                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix)
                
                for page in pages:
                    if 'Contents' not in page:
                        continue
                        
                    for obj in page['Contents']:
                        s3_key = obj['Key']
                        
                        # Skip directories
                        if s3_key.endswith('/'):
                            continue
                        
                        try:
                            # Download file from S3
                            response = s3_client.get_object(
                                Bucket=settings.S3_BUCKET,
                                Key=s3_key
                            )
                            file_content = response['Body'].read()
                            
                         
                            txt_zip_path = s3_key.replace(f"sec/{ticker}/", "")
                            zip_file.writestr(txt_zip_path, file_content)
                            files_added += 1
                            logger.info(f"Added to ZIP: {txt_zip_path}")
                            
                          
                            if include_pdf:
                                try:
                                    # Decode to text for processing
                                    try:
                                        text_content = file_content.decode('utf-8')
                                    except UnicodeDecodeError:
                                        text_content = file_content.decode('latin-1')
                                    
                                    pdf_zip_path = txt_zip_path.replace('.txt', '.pdf')
                                    
                                    # Create a title for the PDF
                                    parts = s3_key.split('/')
                                    doc_title = f"{parts[-3]} - {parts[-2]}"
                                    
                                    # Generate PDF
                                    pdf_content = create_pdf_from_text(text_content, doc_title)
                                    zip_file.writestr(pdf_zip_path, pdf_content)
                                    files_added += 1
                                    pdfs_generated += 1
                                    logger.info(f"Generated PDF: {pdf_zip_path}")
                                    
                                except Exception as pdf_error:
                                    logger.error(f"PDF generation failed for {s3_key}: {pdf_error}")
                                    # Continue - text version is already added
                            
                        except ClientError as e:
                            logger.error(f"Failed to download {s3_key}: {str(e)}")
                            continue
                        except Exception as e:
                            logger.error(f"Failed to process {s3_key}: {str(e)}")
                            continue
                            
            except ClientError as e:
                logger.error(f"Failed to list objects for {filing_type}: {str(e)}")
                continue
        
        if files_added == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No files found for ticker {ticker} in S3"
            )
        
        logger.info(f"ZIP complete: {files_added} files added, {pdfs_generated} PDFs generated")
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={ticker}_sec_filings.zip"
        }
    )