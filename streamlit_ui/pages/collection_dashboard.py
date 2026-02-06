import streamlit as st
import requests
import json
from datetime import datetime
import pandas as pd
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="Collection Dashboard", page_icon="📊", layout="wide")

# Initialize API client
api = APIClient()

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
st.subheader("⚙️ Collection Settings")

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
    
    if st.button("🚀 Start Collection", type="primary", use_container_width=True):
        if selected_tickers:
            st.session_state.collection_running = True
            st.session_state.selected_tickers = selected_tickers
            st.rerun()
        else:
            st.error("Please select at least one company")

st.divider()

# Signal category selection - ALL ENABLED
st.subheader("📡 Signal Categories")

col1, col2, col3, col4 = st.columns(4)

with col1:
    tech_hiring = st.checkbox("Technology Hiring", value=True)
    st.caption("⚖️ Weight: 30%")
    if tech_hiring:
        st.caption("✓ Job postings analysis")

with col2:
    innovation = st.checkbox("Innovation Activity", value=True)
    st.caption("⚖️ Weight: 25%")
    if innovation:
        st.caption("✓ Patent filings (Google Patents)")

with col3:
    digital = st.checkbox("Digital Presence", value=True)
    st.caption("⚖️ Weight: 25%")
    if digital:
        st.caption("✓ Tech stack scraping")

with col4:
    leadership = st.checkbox("Leadership Signals", value=True)
    st.caption("⚖️ Weight: 20%")
    if leadership:
        st.caption("✓ Executive AI backgrounds")

st.divider()

# Collection progress
if st.session_state.get("collection_running"):
    st.subheader("🔄 Collection in Progress...")
    
    # Initialize progress tracking
    if "collection_progress" not in st.session_state:
        st.session_state.collection_progress = 0
        st.session_state.collection_results = {}
        st.session_state.collection_logs = []
    
    # Progress containers
    progress_bar = st.progress(0)
    status_text = st.empty()
    logs_container = st.container()
    
    selected_tickers = st.session_state.get("selected_tickers", [])
    total_companies = len(selected_tickers)
    
    # Count selected signal types
    signal_types = []
    if tech_hiring:
        signal_types.append("technology_hiring")
    if innovation:
        signal_types.append("innovation_activity")
    if digital:
        signal_types.append("digital_presence")
    if leadership:
        signal_types.append("leadership_signals")
    
    total_tasks = total_companies * len(signal_types)
    current_task = 0
    
    for idx, ticker in enumerate(selected_tickers):
        company_info = TARGET_COMPANIES[ticker]
        
        status_text.write(f"**Processing {idx + 1}/{total_companies}:** {company_info['name']} ({ticker})")
        
        # Get or create company
        company_id = api.get_or_create_company(
            ticker=ticker,
            name=company_info['name'],
            sector=company_info['sector']
        )
        
        if not company_id:
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Failed to get company_id for {ticker}"
            )
            continue
        
        st.session_state.collection_logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 📍 Starting collection for {ticker}"
        )
        
        results = {
            'status': '✅ Success',
            'signals_collected': 0,
            'scores': {}
        }
        
        # ========================================
        # 1. Technology Hiring Signals
        # ========================================
        if tech_hiring:
            current_task += 1
            progress_bar.progress(int((current_task / total_tasks) * 100))
            
            with logs_container:
                st.caption(f"🔍 {ticker}: Collecting job postings...")
            
            try:
                response = requests.post(
                    f"{api.base_url}/signals/collect-job-signals",
                    params={
                        "company_id": company_id,
                        "company_name": company_info['name'],
                        "max_results": 20
                    },
                    timeout=180
                )
                
                if response.status_code == 201:
                    signal_data = response.json()
                    results['scores']['technology_hiring'] = signal_data.get('normalized_score', 0)
                    results['signals_collected'] += 1
                    
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Job signals: {signal_data.get('normalized_score', 0):.1f}"
                    )
                else:
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Job signals failed: {response.status_code}"
                    )
            
            except Exception as e:
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {ticker} - Job signals error: {str(e)[:50]}"
                )
        
        # ========================================
        # 2. Innovation Activity (Patents)
        # ========================================
        if innovation:
            current_task += 1
            progress_bar.progress(int((current_task / total_tasks) * 100))
            
            with logs_container:
                st.caption(f"🔬 {ticker}: Collecting patent signals...")
            
            try:
                # Get assignee from company info or use name
                assignee = company_info.get('assignee', company_info['name'])
                
                response = requests.post(
                    f"{api.base_url}/signals/collect-patent-signals",
                    params={
                        "company_id": company_id,
                        "assignee": assignee,
                        "years": 5
                    },
                    timeout=300  # Patents can take a while
                )
                
                if response.status_code in [200, 201, 202]:
                    # Patent collection might be queued
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ {ticker} - Patent signals queued"
                    )
                    results['signals_collected'] += 1
                    results['scores']['innovation_activity'] = 'Queued'
                else:
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Patent signals failed: {response.status_code}"
                    )
            
            except Exception as e:
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {ticker} - Patent error: {str(e)[:50]}"
                )
        
        # ========================================
        # 3. Digital Presence (Tech Stack)
        # ========================================
        if digital:
            current_task += 1
            progress_bar.progress(int((current_task / total_tasks) * 100))
            
            with logs_container:
                st.caption(f"💻 {ticker}: Analyzing tech stack...")
            
            try:
                response = requests.post(
                    f"{api.base_url}/signals/collect-tech-signals",
                    params={
                        "company_id": company_id,
                        "company_name": company_info['name'],
                        "ticker": ticker
                    },
                    timeout=120
                )
                
                if response.status_code == 201:
                    signal_data = response.json()
                    results['scores']['digital_presence'] = signal_data.get('normalized_score', 0)
                    results['signals_collected'] += 1
                    
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Tech stack: {signal_data.get('normalized_score', 0):.1f}"
                    )
                else:
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Tech stack failed: {response.status_code}"
                    )
            
            except Exception as e:
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {ticker} - Tech stack error: {str(e)[:50]}"
                )
        
        # ========================================
        # 4. Leadership Signals
        # ========================================
        if leadership:
            current_task += 1
            progress_bar.progress(int((current_task / total_tasks) * 100))
            
            with logs_container:
                st.caption(f"👔 {ticker}: Analyzing leadership...")
            
            try:
                response = requests.post(
                    f"{api.base_url}/signals/collect-leadership-signals",
                    params={
                        "company_id": company_id,
                        "ticker": ticker,
                        "company_name": company_info['name']
                    },
                    timeout=120
                )
                
                if response.status_code == 201:
                    signal_data = response.json()
                    results['scores']['leadership_signals'] = signal_data.get('normalized_score', 0)
                    results['signals_collected'] += 1
                    
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Leadership: {signal_data.get('normalized_score', 0):.1f}"
                    )
                else:
                    st.session_state.collection_logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Leadership failed: {response.status_code}"
                    )
            
            except Exception as e:
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {ticker} - Leadership error: {str(e)[:50]}"
                )
        
        # ========================================
        # 5. Refresh Summary
        # ========================================
        with logs_container:
            st.caption(f"🔄 {ticker}: Refreshing summary...")
        
        try:
            api.refresh_signal_summary(company_id)
            
            # Get updated summary
            summary = api.get_signal_summary(company_id)
            
            if summary:
                results['composite_score'] = summary.get('composite_score', 0)
                
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Composite score: {summary.get('composite_score', 0):.1f}"
                )
        except Exception as e:
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Summary refresh failed"
            )
        
        # Store results
        st.session_state.collection_results[ticker] = results
    
    # Final progress
    progress_bar.progress(100)
    status_text.empty()
    
    # Display results
    st.success("✅ Collection Complete!")
    
    st.divider()
    
    # Results table
    st.subheader("📊 Collection Results")
    
    results_data = []
    for ticker, result in st.session_state.collection_results.items():
        company_info = TARGET_COMPANIES[ticker]
        
        scores = result.get('scores', {})
        
        results_data.append({
            "Ticker": ticker,
            "Company": company_info['name'][:30],
            "Sector": company_info['sector'],
            "Status": result['status'],
            "Signals": f"{result['signals_collected']}/{len(signal_types)}",
            "Tech Hiring": f"{scores.get('technology_hiring', 0):.1f}" if isinstance(scores.get('technology_hiring'), (int, float)) else 'N/A',
            "Innovation": f"{scores.get('innovation_activity', 0):.1f}" if isinstance(scores.get('innovation_activity'), (int, float)) else 'Queued',
            "Digital": f"{scores.get('digital_presence', 0):.1f}" if isinstance(scores.get('digital_presence'), (int, float)) else 'N/A',
            "Leadership": f"{scores.get('leadership_signals', 0):.1f}" if isinstance(scores.get('leadership_signals'), (int, float)) else 'N/A',
            "Composite": f"{result.get('composite_score', 0):.1f}" if result.get('composite_score') else 'Pending'
        })
    
    results_df = pd.DataFrame(results_data)
    
    # Style the dataframe
    def color_status(val):
        if '✅' in val:
            return 'background-color: #d4edda'
        elif '⚠️' in val:
            return 'background-color: #fff3cd'
        elif '❌' in val:
            return 'background-color: #f8d7da'
        return ''
    
    styled_df = results_df.style.applymap(color_status, subset=['Status'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Summary statistics
    st.divider()
    st.subheader("📈 Collection Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    successful = sum(1 for r in st.session_state.collection_results.values() if '✅' in r['status'])
    total_signals = sum(r['signals_collected'] for r in st.session_state.collection_results.values())
    avg_composite = sum(r.get('composite_score', 0) for r in st.session_state.collection_results.values() if r.get('composite_score')) / max(successful, 1)
    
    with col1:
        st.metric("Companies Processed", f"{successful}/{total_companies}")
    
    with col2:
        st.metric("Total Signals", total_signals)
    
    with col3:
        st.metric("Avg Composite Score", f"{avg_composite:.1f}")
    
    with col4:
        success_rate = (successful / total_companies * 100) if total_companies > 0 else 0
        st.metric("Success Rate", f"{success_rate:.0f}%")
    
    # Show logs
    st.divider()
    with st.expander("📜 View Collection Logs", expanded=False):
        for log in st.session_state.collection_logs:
            # Color code logs
            if '✅' in log:
                st.success(log)
            elif '⚠️' in log:
                st.warning(log)
            elif '❌' in log:
                st.error(log)
            else:
                st.info(log)
    
    # Export options
    st.divider()

    if st.button("🔄 Run Another Collection", use_container_width=True):
        # Clear state
        st.session_state.collection_running = False
        st.session_state.collection_progress = 0
        st.session_state.collection_results = {}
        st.session_state.collection_logs = []
        st.rerun()

else:
    st.info("👆 Configure settings above and click 'Start Collection' to begin")
    
    # Show instructions
    st.divider()
    st.subheader("📖 How It Works")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Signal Collection Process:**
        
        1. **Technology Hiring** (30% weight)
           - Scrapes LinkedIn, Indeed, Glassdoor
           - Analyzes job titles and descriptions
           - Calculates AI relevance scores
           - Time: ~2-3 minutes per company
        
        2. **Innovation Activity** (25% weight)
           - Searches Google Patents
           - Filters by CPC codes (G06N family)
           - Analyzes patent categories
           - Time: ~3-5 minutes per company (queued)
        """)
    
    with col2:
        st.markdown("""
        3. **Digital Presence** (25% weight)
           - Scrapes company websites
           - Analyzes GitHub repositories
           - Detects AI technologies in use
           - Time: ~1-2 minutes per company
        
        4. **Leadership Signals** (20% weight)
           - Scrapes executive pages
           - Detects AI-relevant roles
           - Analyzes backgrounds
           - Time: ~1-2 minutes per company
        """)
    
    st.divider()
    st.info("⏱️ **Total Time:** Approximately 8-12 minutes per company for full collection")
    
    # Show last run results if available
    if st.session_state.get("collection_results"):
        st.divider()
        st.subheader("📊 Last Collection Results")
        
        results_data = []
        for ticker, result in st.session_state.collection_results.items():
            company_info = TARGET_COMPANIES[ticker]
            scores = result.get('scores', {})
            
            results_data.append({
                "Ticker": ticker,
                "Company": company_info['name'][:30],
                "Status": result['status'],
                "Signals": f"{result['signals_collected']}/{len(signal_types)}",
                "Composite": f"{result.get('composite_score', 0):.1f}" if result.get('composite_score') else 'N/A'
            })
        
        results_df = pd.DataFrame(results_data)
        st.dataframe(results_df, use_container_width=True, hide_index=True)
        
        if st.button("🔄 Run Again"):
            st.session_state.collection_running = False
            st.session_state.collection_results = {}
            st.session_state.collection_logs = []
            st.rerun()