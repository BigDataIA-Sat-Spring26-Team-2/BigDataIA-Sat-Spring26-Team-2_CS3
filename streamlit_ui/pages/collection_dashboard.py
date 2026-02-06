import streamlit as st
from datetime import datetime, timezone
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
    "CAT": {"name": "Caterpillar Inc.", "sector": "Manufacturing", "assignee": "Caterpillar Inc."},
    "DE": {"name": "Deere & Company", "sector": "Manufacturing", "assignee": "Deere & Company"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare", "assignee": "UnitedHealth Group Incorporated"},
    "HCA": {"name": "HCA Healthcare", "sector": "Healthcare", "assignee": "HCA Healthcare, Inc."},
    "ADP": {"name": "Automatic Data Processing", "sector": "Services", "assignee": "Automatic Data Processing, Inc."},
    "PAYX": {"name": "Paychex Inc.", "sector": "Services", "assignee": "Paychex Inc."},
    "WMT": {"name": "Walmart Inc.", "sector": "Retail", "assignee": "Walmart Apollo Llc"},
    "TGT": {"name": "Target Corporation", "sector": "Retail", "assignee": "Target Brands, Inc"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Financial", "assignee": "Jp Morgan Chase Bank, N.A."},
    "GS": {"name": "Goldman Sachs", "sector": "Financial", "assignee": "Goldman Sachs & Co"},
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
    
    if st.button("Start", type="primary", use_container_width=True):
        if selected_tickers:
            st.session_state.collection_running = True
            st.session_state.selected_tickers = selected_tickers
            st.rerun()
        else:
            st.error("Please select at least one company")

st.divider()

st.subheader("Signal Categories Collected")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**Technology Hiring**")
    st.caption(" Weight: 30%")
    st.caption("✓ Job postings analysis")

with col2:
    st.markdown("**Innovation Activity**")
    st.caption(" Weight: 25%")
    st.caption("✓ Patent filings (Google Patents)")

with col3:
    st.markdown("**Digital Presence**")
    st.caption(" Weight: 25%")
    st.caption("✓ Tech stack scraping")

with col4:
    st.markdown("**Leadership Signals**")
    st.caption(" Weight: 20%")
    st.caption("✓ Executive AI backgrounds")

st.divider()

# Collection progress
if st.session_state.get("collection_running"):
    st.subheader("Collection in Progress...")
    
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
    
    # All signal types are always enabled
    signal_types = ["technology_hiring", "innovation_activity", "digital_presence", "leadership_signals"]

    total_tasks = total_companies
    status_text.write(f" **Load Mode:** Fetching from database (fast!)")
    
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
            f"[{datetime.now().strftime('%H:%M:%S')}] 📍 Processing {ticker}"
        )
        
        results = {
            'status': '✅ Success',
            'signals_collected': 0,
            'scores': {},
            'data_source': 'database'
        }
        
        current_task += 1
        progress_bar.progress(int((current_task / total_tasks) * 100))
        
        with logs_container:
            st.caption(f"📊 {ticker}: Loading from database...")
        
        try:
            # ✅ Use existing GET endpoint: /signals/companies/{id}/summary
            summary = api.get_signal_summary(company_id)
            
            if summary and summary.get('signal_count', 0) > 0:
                # Data exists in COMPANY_SIGNAL_SUMMARIES table
                results['scores'] = {
                    'technology_hiring': summary.get('technology_hiring_score', 0),
                    'innovation_activity': summary.get('innovation_activity_score', 0),
                    'digital_presence': summary.get('digital_presence_score', 0),
                    'leadership_signals': summary.get('leadership_signals_score', 0)
                }
                results['composite_score'] = summary.get('composite_score', 0)
                results['signals_collected'] = summary.get('signal_count', 0)
                results['last_updated'] = summary.get('last_updated')
                
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Loaded: "
                    f"Composite {summary.get('composite_score', 0):.1f}/100 "
                    f"({summary.get('signal_count', 0)} signals in DB)"
                )
                
        except Exception as e:
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {ticker} - Database error: {str(e)[:80]}"
            )
            results['status'] = '❌ Error'
        
        
        
        try:
            # Get final summary (either cached or newly refreshed)
            # This fetches from COMPANY_SIGNAL_SUMMARIES table
            summary = api.get_signal_summary(company_id)
            
            if summary:
                # Update results with final scores
                if not results['scores']:
                    results['scores'] = {
                        'technology_hiring': summary.get('technology_hiring_score', 0),
                        'innovation_activity': summary.get('innovation_activity_score', 0),
                        'digital_presence': summary.get('digital_presence_score', 0),
                        'leadership_signals': summary.get('leadership_signals_score', 0)
                    }
                
                results['composite_score'] = summary.get('composite_score', 0)
                
                mode_text = "loaded"
                st.session_state.collection_logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {ticker} - Summary {mode_text}: {summary.get('composite_score', 0):.1f}/100"
                )
        except Exception as e:
            st.session_state.collection_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {ticker} - Summary failed: {str(e)[:50]}"
            )
        
        # Store results
        st.session_state.collection_results[ticker] = results
    
    # Final progress
    progress_bar.progress(100)
    status_text.empty()
    
    st.divider()
    
    # Results table
    st.subheader(" Collection Results")
    
    results_data = []
    for ticker, result in st.session_state.collection_results.items():
        company_info = TARGET_COMPANIES[ticker]
        scores = result.get('scores', {})
        
        status_display = f"{result['status']}"
        
        results_data.append({
            "Ticker": ticker,
            "Company": company_info['name'][:30],
            "Sector": company_info['sector'],
            "Status": status_display,
            "Tech Hiring": f"{scores.get('technology_hiring', 0):.1f}" if isinstance(scores.get('technology_hiring'), (int, float)) else 'N/A',
            "Innovation": f"{scores.get('innovation_activity', 0):.1f}" if isinstance(scores.get('innovation_activity'), (int, float)) else 'Queued',
            "Digital": f"{scores.get('digital_presence', 0):.1f}" if isinstance(scores.get('digital_presence'), (int, float)) else 'N/A',
            "Leadership": f"{scores.get('leadership_signals', 0):.1f}" if isinstance(scores.get('leadership_signals'), (int, float)) else 'N/A',
            "Composite": f"{result.get('composite_score', 0):.1f}" if result.get('composite_score') else 'Pending'
        })
    
    results_df = pd.DataFrame(results_data)
    
    # Style the dataframe
    def color_status(val):
        if '✅' in str(val):
            return 'background-color: #d4edda'
        elif '⚠️' in str(val):
            return 'background-color: #fff3cd'
        elif '❌' in str(val):
            return 'background-color: #f8d7da'
        return ''
    
    styled_df = results_df.style.applymap(color_status, subset=['Status'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Summary statistics
    st.divider()
    st.subheader("Collection Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    successful = sum(1 for r in st.session_state.collection_results.values() if '✅' in r['status'])
    total_signals = sum(r['signals_collected'] for r in st.session_state.collection_results.values())
    
    composites = [r.get('composite_score', 0) for r in st.session_state.collection_results.values() if r.get('composite_score')]
    avg_composite = sum(composites) / len(composites) if composites else 0
    
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
    with st.expander("View Collection Logs", expanded=False):
        for log in st.session_state.collection_logs:
            # Color code logs
            if '✅' in log:
                st.success(log)
            elif '⚠️' in log:
                st.warning(log)
            elif '❌' in log:
                st.error(log)
            elif '⏳' in log:
                st.info(log)
            else:
                st.text(log)
    
    # Export options
    st.divider()

    if st.button("Run Another Collection", use_container_width=True):
        # Clear state
        st.session_state.collection_running = False
        st.session_state.collection_progress = 0
        st.session_state.collection_results = {}
        st.session_state.collection_logs = []
        st.rerun()


    