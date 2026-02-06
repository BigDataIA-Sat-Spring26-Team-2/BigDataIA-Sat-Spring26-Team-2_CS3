# streamlit_app.py
import os
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


st.set_page_config(page_title="SEC Documents", page_icon="📄", layout="centered")

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def api_post(base: str, path: str, params: Optional[dict] = None, body: Any = None) -> Dict[str, Any]:
    url = f"{base}{path}"
    r = requests.post(url, params=params, json=body, timeout=300)
    if r.status_code >= 400:
        try:
            return {"_error": r.json(), "_status": r.status_code}
        except Exception:
            return {"_error": r.text, "_status": r.status_code}
    return r.json()


def api_get(base: str, path: str, params: dict) -> requests.Response:
    """GET request that returns raw response for binary data"""
    url = f"{base}{path}"
    return requests.get(url, params=params, timeout=120)


def valid_cik(v: str) -> bool:
    return v.isdigit() and len(v) == 10


st.set_page_config(page_title="SEC EDGAR Downloader", layout="centered")

st.title("SEC EDGAR Evidence Collector")
st.caption("Download SEC filings and store them via the FastAPI backend (Case Study 2)")

api_base = st.text_input("API Base URL", DEFAULT_API_BASE)

st.divider()

company_id = st.text_input(
    "Company UUID",
    placeholder="Paste UUID from /companies",
)

ticker = st.text_input(
    "Ticker (optional)",
    value="",
    placeholder="AAPL"
).strip()

cik = st.text_input(
    "CIK (optional, 10 digits)",
    value="",
    placeholder="0000320193"
).strip()

filing_types = st.multiselect(
    "Filing types",
    options=["10-K", "10-Q", "8-K", "DEF 14A"],
    default=["10-K"]
)

after_date = st.date_input(
    "Download filings after",
    value=date(2023, 1, 1)
)

limit = st.number_input(
    "Max filings per type",
    min_value=1,
    max_value=50,
    value=2,
    step=1
)

st.divider()

include_pdf = st.checkbox(
    "Include PDF versions (slower, may take several minutes for large filings)",
    value=False,
    help="Generate formatted PDF versions of each filing. This can significantly increase download time."
)

if st.button("⬇️ Download SEC Filings", type="primary"):
    if not company_id.strip():
        st.error("Company UUID is required.")
        st.stop()

    if not filing_types:
        st.error("Select at least one filing type.")
        st.stop()

    if not ticker and not cik:
        st.error("Provide either Ticker or CIK.")
        st.stop()

    if cik and not valid_cik(cik):
        st.error("CIK must be exactly 10 digits (including leading zeros).")
        st.stop()

    params = {
        "company_id": company_id.strip(),
        "after": after_date.isoformat(),
        "limit": int(limit),
        "filing_types": filing_types,
    }

    if ticker:
        params["ticker"] = ticker.upper()
        resolved_ticker = ticker.upper()
    else:
        params["cik"] = cik
        resolved_ticker = cik

    with st.spinner("Downloading + parsing filings… (this can take some time)"):
        result = api_post(api_base, "/documents/sec-edgar/download", params=params, body=None)

    if "_error" in result:
        st.error(f"Request failed ({result.get('_status')})")
        st.code(_pretty(result["_error"]), language="json")
        st.stop()

    st.success(" Pipeline finished")

    st.subheader("Summary")
    st.json({
        "downloaded_files": result.get("downloaded_files"),
        "inserted_documents": result.get("inserted_documents"),
        "inserted_chunks": result.get("inserted_chunks"),
        "skipped_duplicates": result.get("skipped_duplicates"),
    })

    st.subheader("Download All Files")
    
    files: List[dict] = result.get("files", [])
    
    if files and len(files) > 0:
        if include_pdf:
            st.info(f"📦 {len(files)} file(s) ready for download (includes both .txt and .pdf versions)")
        else:
            st.info(f"📦 {len(files)} file(s) ready for download (.txt only)")
        
        # Display ticker and filing types
        st.write(f"**Ticker:** {resolved_ticker}")
        st.write(f"**Filing Types:** {', '.join(filing_types)}")
        
        # Fetch ZIP file from backend IMMEDIATELY
        spinner_text = "Creating ZIP file from S3..."
        if include_pdf:
            spinner_text += " (generating PDFs, this may take a minute)..."
        
        with st.spinner(spinner_text):
            # Construct query string manually for list parameters
            query_parts = [f"ticker={resolved_ticker}"]
            for ft in filing_types:
                query_parts.append(f"filing_types={ft}")
            # ✅ ADD include_pdf PARAMETER
            query_parts.append(f"include_pdf={'true' if include_pdf else 'false'}")
            query_string = "&".join(query_parts)
            
            try:
                # Make the API call to get the ZIP
                zip_response = requests.get(
                    f"{api_base}/documents/sec-edgar/download-zip?{query_string}",
                    timeout=300  # 5 minutes max
                )
                
                if zip_response.status_code == 200:
                    # Show download button with the actual ZIP data
                    st.download_button(
                        label="⬇️ Download ZIP",
                        data=zip_response.content,
                        file_name=f"{resolved_ticker}_sec_filings.zip",
                        mime="application/zip",
                        use_container_width=False,
                    )
                    success_msg = "✅ ZIP file ready for download!"
                    if include_pdf:
                        success_msg += " Each filing includes both .txt and .pdf versions."
                    st.success(success_msg)
                else:
                    st.error(f"❌ Failed to create ZIP file (Status: {zip_response.status_code})")
                    try:
                        error_detail = zip_response.json()
                        st.code(_pretty(error_detail), language="json")
                    except:
                        st.code(zip_response.text)
            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out.")
                if include_pdf:
                    st.info("💡 Try again without PDF generation for faster results.")
                else:
                    st.info("💡 Try reducing the limit or selecting fewer filing types.")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Network error: {str(e)}")
        
        # Show file details in expander
        with st.expander("📄 View File Details"):
            if include_pdf:
                st.caption("Each filing will include both .txt (original) and .pdf (formatted) versions in the ZIP.")
            else:
                st.caption("Each filing will include .txt (original) version only.")
            st.write("")
            
            for idx, f in enumerate(files, 1):
                filing_type = f.get("filing_type", "")
                accession = f.get("accession_number", "")
                file_path = f.get("path", "")
                
                st.markdown(f"**{idx}. {filing_type}** | {accession}")
                if file_path:
                    # Show the S3 path
                    s3_base = f"s3://your-bucket/sec/{resolved_ticker}/{filing_type}/{accession}/"
                    if include_pdf:
                        st.caption(f"Files: `full-submission.txt` and `full-submission.pdf`")
                    else:
                        st.caption(f"File: `full-submission.txt`")
                    st.caption(f"S3 Location: `{s3_base}`")
                st.write("")
    else:
        st.warning("No files were downloaded. Try adjusting your search parameters.")
        st.info("Note: Files might have been skipped as duplicates if they were already processed.")