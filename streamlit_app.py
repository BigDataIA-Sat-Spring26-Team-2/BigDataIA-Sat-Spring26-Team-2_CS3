import os
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


# =========================
# Config
# =========================
DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


# =========================
# Helpers
# =========================
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


def api_get_file(base: str, path: str, params: dict) -> requests.Response:
    url = f"{base}{path}"
    return requests.get(url, params=params, timeout=60)


def valid_cik(v: str) -> bool:
    return v.isdigit() and len(v) == 10


# =========================
# UI
# =========================
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

if st.button("⬇️ Download SEC Filings", type="primary"):
    # ---------- Client-side validation ----------
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
        "filing_types": filing_types,  # FastAPI will accept repeated query args
    }

    # Prefer ticker if provided
    if ticker:
        params["ticker"] = ticker.upper()
    else:
        params["cik"] = cik

    with st.spinner("Downloading + parsing filings… (this can take some time)"):
        result = api_post(api_base, "/documents/sec-edgar/download", params=params, body=None)

    # ---------- Error handling ----------
    if "_error" in result:
        st.error(f"Request failed ({result.get('_status')})")
        st.code(_pretty(result["_error"]), language="json")
        st.stop()

    st.success("✅ Pipeline finished")

    # ---------- Summary ----------
    st.subheader("Summary")
    st.json({
        "downloaded_files": result.get("downloaded_files"),
        "inserted_documents": result.get("inserted_documents"),
        "inserted_chunks": result.get("inserted_chunks"),
        "skipped_duplicates": result.get("skipped_duplicates"),
    })

    # ---------- Downloaded files ----------
    files: List[dict] = result.get("files", [])
    st.subheader("Downloaded files")

    if not files:
        st.info("No file list returned. If downloaded_files>0, update backend to include `files` list in response.")
        st.code(_pretty(result), language="json")
        st.stop()

    for f in files:
        filing_type = f.get("filing_type", "")
        accession = f.get("accession_number", "")
        file_path = f.get("path", "")

        if not file_path:
            st.warning(f"Missing path for: {filing_type} | {accession}")
            continue

        # Try to fetch file from backend
        resp = api_get_file(api_base, "/documents/file", params={"path": file_path})

        if resp.status_code != 200:
            st.error(f"Could not fetch file: {filing_type} | {accession}")
            try:
                st.code(_pretty(resp.json()), language="json")
            except Exception:
                st.code(resp.text)
            continue

        # Offer actual download via Streamlit download button
        filename = Path(file_path).name
        st.markdown(f"**{filing_type}** | {accession}")
        st.download_button(
            label=f"⬇️ Download {filename}",
            data=resp.content,
            file_name=filename,
            mime="text/plain",
            use_container_width=True,
            key=f"dl-{filing_type}-{accession}",
        )
        st.write("")
