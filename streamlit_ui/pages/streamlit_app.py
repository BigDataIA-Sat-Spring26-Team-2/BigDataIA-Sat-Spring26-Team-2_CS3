# streamlit_app.py
import os
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


st.set_page_config(page_title="SEC Documents", page_icon="📄", layout="centered")

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

# ── Airflow connection settings ───────────────────────────────────────────────
AIRFLOW_BASE = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASS = os.getenv("AIRFLOW_PASS", "admin123")
DAG_ID = "sec_edgar_pipeline"


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def api_get(base: str, path: str, params: dict) -> requests.Response:
    """GET request that returns raw response for binary data"""
    url = f"{base}{path}"
    return requests.get(url, params=params, timeout=120)


def valid_cik(v: str) -> bool:
    return v.isdigit() and len(v) == 10


# ── Airflow helpers ───────────────────────────────────────────────────────────

def trigger_airflow_dag(conf: dict) -> dict:
    """Trigger the sec_edgar_pipeline DAG with the given conf dict."""
    url = f"{AIRFLOW_BASE}/api/v1/dags/{DAG_ID}/dagRuns"
    try:
        resp = requests.post(
            url,
            json={"conf": conf},
            auth=(AIRFLOW_USER, AIRFLOW_PASS),
            timeout=30,
        )
        if resp.status_code >= 400:
            return {"_error": resp.text, "_status": resp.status_code}
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"_error": str(e), "_status": 0}


def get_dag_run_status(run_id: str) -> dict:
    """Fetch current state of a DAG run."""
    url = f"{AIRFLOW_BASE}/api/v1/dags/{DAG_ID}/dagRuns/{run_id}"
    try:
        resp = requests.get(url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=15)
        if resp.status_code >= 400:
            return {"_error": resp.text, "_status": resp.status_code}
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"_error": str(e)}


def get_task_instances(run_id: str) -> list:
    """Fetch task-level status for a DAG run."""
    url = f"{AIRFLOW_BASE}/api/v1/dags/{DAG_ID}/dagRuns/{run_id}/taskInstances"
    try:
        resp = requests.get(url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("task_instances", [])
    except Exception:
        pass
    return []


# ── UI ────────────────────────────────────────────────────────────────────────

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

    resolved_ticker = ticker.upper() if ticker else cik

    # Build DAG conf — same params the UI collected
    dag_conf = {
        "company_id": company_id.strip(),
        "filing_types": filing_types,
        "after": after_date.isoformat(),
        "limit": int(limit),
        "include_pdf": include_pdf,
    }
    if ticker:
        dag_conf["ticker"] = ticker.upper()
    if cik:
        dag_conf["cik"] = cik

    # ── Step 1: Trigger the Airflow DAG ──────────────────────────────────────
    with st.spinner("Triggering Airflow pipeline..."):
        trigger_result = trigger_airflow_dag(dag_conf)

    if "_error" in trigger_result:
        st.error(f"Failed to trigger DAG ({trigger_result.get('_status')})")
        st.code(trigger_result["_error"])
        st.stop()

    run_id = trigger_result.get("dag_run_id")
    st.success(f"Airflow DAG triggered — Run ID: `{run_id}`")
    st.caption(f"Monitor in Airflow UI: {AIRFLOW_BASE}/dags/{DAG_ID}/grid")

    # ── Step 2: Poll for completion ───────────────────────────────────────────
    POLL_INTERVAL = 10   # seconds between polls
    MAX_WAIT = 600        # 10 minutes max

    status_box = st.empty()
    task_box = st.empty()

    final_state = None
    elapsed = 0

    TASK_STATE_ICONS = {
        "success": "✅",
        "running": "⏳",
        "failed": "❌",
        "upstream_failed": "⛔",
        "skipped": "⏭️",
        "queued": "🔵",
        "none": "⬜",
    }

    while elapsed < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        run_info = get_dag_run_status(run_id)
        state = run_info.get("state", "unknown")

        status_box.info(f"Pipeline state: **{state.upper()}** ({elapsed}s elapsed)")

        # Show per-task status
        tasks = get_task_instances(run_id)
        if tasks:
            task_rows = []
            for t in tasks:
                icon = TASK_STATE_ICONS.get(t.get("state", "none"), "⬜")
                task_rows.append({
                    "Task": t.get("task_id"),
                    "State": f"{icon} {t.get('state', 'none')}",
                    "Duration": f"{t.get('duration') or 0:.0f}s" if t.get("duration") else "-",
                })
            import pandas as pd
            task_box.dataframe(pd.DataFrame(task_rows), hide_index=True, use_container_width=True)

        if state in ("success", "failed", "upstream_failed"):
            final_state = state
            break

    status_box.empty()

    # ── Step 3: Show result ───────────────────────────────────────────────────
    if final_state == "success":
        st.success("Pipeline finished successfully!")

        st.subheader("Download All Files")
        spinner_text = "Creating ZIP file from S3..."
        if include_pdf:
            spinner_text += " (includes PDFs)..."

        with st.spinner(spinner_text):
            query_parts = [f"ticker={resolved_ticker}"]
            for ft in filing_types:
                query_parts.append(f"filing_types={ft}")
            query_parts.append(f"include_pdf={'true' if include_pdf else 'false'}")
            query_string = "&".join(query_parts)

            try:
                zip_response = requests.get(
                    f"{api_base}/documents/sec-edgar/download-zip?{query_string}",
                    timeout=300,
                )
                if zip_response.status_code == 200:
                    st.download_button(
                        label="Download ZIP",
                        data=zip_response.content,
                        file_name=f"{resolved_ticker}_sec_filings.zip",
                        mime="application/zip",
                        use_container_width=False,
                    )
                    success_msg = "ZIP file ready for download!"
                    if include_pdf:
                        success_msg += " Each filing includes both .txt and .pdf versions."
                    st.success(success_msg)
                else:
                    st.error(f"Failed to create ZIP file (Status: {zip_response.status_code})")
                    try:
                        st.code(_pretty(zip_response.json()), language="json")
                    except Exception:
                        st.code(zip_response.text)
            except requests.exceptions.Timeout:
                st.error("ZIP request timed out.")
                st.info("Try reducing the limit or selecting fewer filing types.")
            except requests.exceptions.RequestException as e:
                st.error(f"Network error: {str(e)}")

    elif final_state is not None:
        st.error(f"Pipeline ended with state: **{final_state}**")
        st.info(f"Check the Airflow UI for task logs: {AIRFLOW_BASE}/dags/{DAG_ID}/grid")
    else:
        st.warning(f"Pipeline still running after {MAX_WAIT}s. Check Airflow UI for status.")
        st.info(f"{AIRFLOW_BASE}/dags/{DAG_ID}/grid")
