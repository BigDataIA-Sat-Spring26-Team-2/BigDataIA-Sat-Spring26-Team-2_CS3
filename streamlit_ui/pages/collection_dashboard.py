# pages/1_📊_Collection_Dashboard.py
import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import time

st.set_page_config(page_title="Collection Dashboard", page_icon="📊", layout="wide")

# Get API base from session state
api_base = st.session_state.get("api_base", "http://127.0.0.1:8000/api/v1")

st.title("Evidence Collection Dashboard")
st.caption("Run signal collection pipelines for target companies")

# Target companies configuration
TARGET_COMPANIES = {
    "CAT": {"name": "Caterpillar Inc.", "sector": "Manufacturing"},
    "DE": {"name": "Deere & Company", "sector": "Manufacturing"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare"},
    "HCA": {"name": "HCA Healthcare", "sector": "Healthcare"},
    "ADP": {"name": "Automatic Data Processing", "sector": "Services"},
    "PAYX": {"name": "Paychex Inc.", "sector": "Services"},
    "WMT": {"name": "Walmart Inc.", "sector": "Retail"},
    "TGT": {"name": "Target Corporation", "sector": "Retail"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Financial"},
    "GS": {"name": "Goldman Sachs", "sector": "Financial"},
}

st.divider()

# Collection controls
st.subheader("Collection Settings")

col1, col2 = st.columns([3, 1])

with col1:
    # Company selection
    company_options = ["All Companies"] + [
        f"{ticker} - {info['name']}" 
        for ticker, info in TARGET_COMPANIES.items()
    ]
    
    selected_companies = st.multiselect(
        "Select companies to collect signals for:",
        company_options,
        default=["All Companies"]
    )
    
    # Parse selected tickers
    if "All Companies" in selected_companies:
        selected_tickers = list(TARGET_COMPANIES.keys())
    else:
        selected_tickers = [opt.split(" - ")[0] for opt in selected_companies]

with col2:
    st.write("") 
    st.write("")
    
    if st.button("Start Collection", type="primary", use_container_width=True):
        if selected_tickers:
            st.session_state.collection_running = True
            st.session_state.selected_tickers = selected_tickers
            st.rerun()
        else:
            st.error("Please select at least one company")

st.divider()

# Signal category selection
st.subheader("Signal Categories")

col1, col2, col3, col4 = st.columns(4)

with col1:
    tech_hiring = st.checkbox("Technology Hiring", value=True)
    st.caption("⚖️ Weight: 30%")
    if tech_hiring:
        st.caption("✓ Job postings analysis")

with col2:
    innovation = st.checkbox("Innovation Activity", value=False)
    st.caption("⚖️ Weight: 25%")
    st.caption("🚧 Coming soon")

with col3:
    digital = st.checkbox("Digital Presence", value=False)
    st.caption("⚖️ Weight: 25%")
    st.caption("🚧 Coming soon")

with col4:
    leadership = st.checkbox("Leadership Signals", value=False)
    st.caption("⚖️ Weight: 20%")
    st.caption("🚧 Coming soon")

st.divider()


# Collection progress
if st.session_state.get("collection_running"):
    st.subheader("🔄 Collection in Progress...")
    
    # Initialize progress tracking
    if "collection_progress" not in st.session_state:
        st.session_state.collection_progress = 0
        st.session_state.collection_results = {}
        st.session_state.collection_logs = []
    
    # Progress bar
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    logs_placeholder = st.empty()
    
    selected_tickers = st.session_state.get("selected_tickers", [])
    total_companies = len(selected_tickers)
    
    for idx, ticker in enumerate(selected_tickers):
        company_info = TARGET_COMPANIES[ticker]
        
        with status_placeholder.container():
            st.write(f"**Processing {idx + 1}/{total_companies}:** {company_info['name']} ({ticker})")
        
        # Update progress
        progress = int((idx / total_companies) * 100)
        progress_placeholder.progress(progress)
        
        # Simulate collection (replace with actual API call)
        try:
            # Mock API call - replace with actual endpoint
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Starting collection for {ticker}"
            )
            
            # Simulate processing time
            time.sleep(2)
            
            # Mock results
            st.session_state.collection_results[ticker] = {
                "status": "✅ Success",
                "tech_hiring_score": 65.0 + (idx * 2),
                "ai_jobs": 10 + idx,
                "timestamp": datetime.now().isoformat()
            }
            
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Completed {ticker}: Score {st.session_state.collection_results[ticker]['tech_hiring_score']:.1f}"
            )
            
        except Exception as e:
            st.session_state.collection_results[ticker] = {
                "status": "❌ Failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Failed {ticker}: {str(e)}"
            )
    
    # Final progress
    progress_placeholder.progress(100)
    
    # Display results
    st.success("✅ Collection Complete!")
    
    # Results table
    results_data = []
    for ticker, result in st.session_state.collection_results.items():
        company_info = TARGET_COMPANIES[ticker]
        results_data.append({
            "Ticker": ticker,
            "Company": company_info['name'],
            "Sector": company_info['sector'],
            "Status": result['status'],
            "Tech Hiring Score": result.get('tech_hiring_score', 'N/A'),
            "AI Jobs": result.get('ai_jobs', 'N/A'),
        })
    
    results_df = pd.DataFrame(results_data)
    st.dataframe(results_df, use_container_width=True, hide_index=True)
    
    # Show logs
    with st.expander("📜 View Collection Logs"):
        for log in st.session_state.collection_logs:
            st.text(log)
    
    # Reset button
    if st.button("🔄 Run Another Collection"):
        st.session_state.collection_running = False
        st.session_state.collection_progress = 0
        st.session_state.collection_results = {}
        st.session_state.collection_logs = []
        st.rerun()

else:
    st.info("👆 Configure settings above and click 'Start Collection' to begin")
    
    # Show last run results if available
    if st.session_state.get("collection_results"):
        st.divider()
        st.subheader("📊 Last Collection Results")
        
        results_data = []
        for ticker, result in st.session_state.collection_results.items():
            company_info = TARGET_COMPANIES[ticker]
            results_data.append({
                "Ticker": ticker,
                "Company": company_info['name'],
                "Status": result['status'],
                "Tech Hiring Score": result.get('tech_hiring_score', 'N/A'),
                "AI Jobs": result.get('ai_jobs', 'N/A'),
            })
        
        results_df = pd.DataFrame(results_data)
        st.dataframe(results_df, use_container_width=True, hide_index=True)