import os
import json
from datetime import date
from typing import Any, Dict, Optional, List

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


def api_get(base: str, path: str, params: Optional[dict] = None) -> Dict[str, Any]:
    url = f"{base}{path}"
    r = requests.get(url, params=params, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} failed ({r.status_code}): {r.text}")
    return r.json()


def api_post(base: str, path: str, params: Optional[dict] = None, body: Any = None) -> Dict[str, Any]:
    url = f"{base}{path}"
    r = requests.post(url, params=params, json=body, timeout=300)
    if r.status_code >= 400:
        # Try to show FastAPI's JSON error
        try:
            j = r.json()
            raise RuntimeError(_pretty(j))
        except Exception:
            raise RuntimeError(f"POST {path} failed ({r.status_code}): {r.text}")
    return r.json()


def normalize_filing_types(selected: List[str]) -> List[str]:
    # Keep them exactly as library expects (10-K, 10-Q, 8-K, etc.)
    return selected


# =========================
# UI
# =========================
st.set_page_config(page_title="PE Org-AI-R | SEC EDGAR", layout="wide")

st.title("SEC EDGAR Evidence Collector (Case Study 2)")
st.caption("Uses CS1 Company UUID + downloads filings by Ticker or CIK. Stores metadata/chunks via your FastAPI backend.")

with st.sidebar:
    st.header("Backend")
    api_base = st.text_input("API_BASE_URL", DEFAULT_API_BASE, help="Example: http://127.0.0.1:8000/api/v1")
    st.markdown("Make sure FastAPI is running: `poetry run uvicorn app.main:app --reload`")

tab1, tab2 = st.tabs(["SEC EDGAR Download", "Companies Helper"])

# =========================
# Tab 1: SEC EDGAR
# =========================
with tab1:
    st.subheader("Download filings for a company (UUID) using Ticker OR CIK")

    colA, colB = st.columns(2)

    with colA:
        company_id = st.text_input(
            "Company UUID (from /companies)",
            value="",
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000",
            help="This must be the UUID primary key from your companies table (CS1)."
        )

        ticker = st.text_input(
            "Ticker (optional)",
            value="AAPL",
            help="Use ticker OR CIK. If both provided, ticker will be used."
        ).strip()

        cik = st.text_input(
            "CIK (optional, 10 digits)",
            value="",
            placeholder="0000320193",
            help="Use CIK if you don’t want to use ticker. Must be exactly 10 digits with leading zeros."
        ).strip()

        after_date = st.date_input(
            "Download filings after",
            value=date(2023, 1, 1)
        )

        filing_types = st.multiselect(
            "Filing types",
            options=["10-K", "10-Q", "8-K", "DEF 14A"],
            default=["10-K", "8-K"]
        )

        limit = st.number_input(
            "Max filings per type",
            min_value=1,
            max_value=50,
            value=2,
            step=1
        )

        st.divider()
        st.markdown("### Validation rules")
        st.write("- Company UUID is required.")
        st.write("- Provide either ticker or CIK.")
        st.write("- CIK must be 10 digits (e.g., 0000320193).")

    with colB:
        st.markdown("### What happens when you click Download")
        st.write("1) FastAPI validates `company_id` is a UUID and exists in Snowflake.")
        st.write("2) SEC EDGAR pipeline downloads filings (library handles rate limiting).")
        st.write("3) Backend parses + hashes + dedupes + chunks.")
        st.write("4) Inserts rows into `documents` and `document_chunks` tables.")
        st.write("5) Response shows counts (downloaded / inserted / skipped).")

        st.info("If you get a UUID parsing error: you probably pasted CIK into Company UUID.")

    # Button row
    st.divider()
    run = st.button("⬇️ Download Filings", type="primary")

    if run:
        # ---- client-side validation
        if not company_id.strip():
            st.error("Company UUID is required.")
            st.stop()

        if not filing_types:
            st.error("Select at least one filing type.")
            st.stop()

        if not ticker and not cik:
            st.error("Provide either ticker or CIK.")
            st.stop()

        if cik:
            if len(cik) != 10 or not cik.isdigit():
                st.error("CIK must be exactly 10 digits (e.g., 0000320193).")
                st.stop()

        params = {
            "after": after_date.isoformat(),
            "limit": int(limit),
            "filing_types": normalize_filing_types(filing_types),
        }

        # Prefer ticker if provided
        if ticker:
            params["ticker"] = ticker.upper()
        else:
            params["cik"] = cik

        path = f"/companies/{company_id}/sec-edgar/download"

        with st.spinner("Downloading + parsing filings… (can take 30–120 seconds)"):
            try:
                result = api_post(api_base, path, params=params, body=None)
                st.success("✅ Download pipeline finished")
                st.code(_pretty(result), language="json")
            except Exception as e:
                st.error("❌ Download failed")
                st.code(str(e))

    st.divider()
    st.markdown("### Quick tips if nothing inserts")
    st.write("- First run should show `inserted_documents > 0`.")
    st.write("- Second run often shows `skipped_duplicates > 0` if you dedupe via content_hash.")
    st.write("- Verify tables exist: `documents`, `document_chunks` in Snowflake.")
    st.write("- Verify DB/schema in Snowsight is set to `PE_ORGAIR.PUBLIC` (or your configured values).")


# =========================
# Tab 2: Companies Helper
# =========================
with tab2:
    st.subheader("Companies helper (so you can copy a UUID)")
    st.caption("This calls your CS1 endpoint `GET /companies` and displays IDs you can paste into the SEC pipeline.")

    col1, col2, col3 = st.columns(3)
    with col1:
        page = st.number_input("page", min_value=1, value=1, step=1, key="c_page")
    with col2:
        page_size = st.number_input("page_size", min_value=1, max_value=100, value=20, step=1, key="c_ps")
    with col3:
        industry_id = st.text_input("industry_id filter (optional)", value="", key="c_ind")

    if st.button("Refresh Companies"):
        try:
            params = {"page": int(page), "page_size": int(page_size)}
            if industry_id.strip():
                params["industry_id"] = industry_id.strip()

            data = api_get(api_base, "/companies", params=params)

            st.caption(f"total={data.get('total')} | total_pages={data.get('total_pages')}")
            items = data.get("items", [])
            if not items:
                st.warning("No companies found.")
            else:
                st.dataframe(items, use_container_width=True)
                st.markdown("Copy the `id` field from a row and paste it into the SEC tab.")
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.subheader("Health check")
    if st.button("Check /health"):
        try:
            h = api_get(api_base, "/health")
            st.success("API reachable")
            st.code(_pretty(h), language="json")
        except Exception as e:
            st.error(str(e))
