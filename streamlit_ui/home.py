import os
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_ui.utils.api_client import APIClient

load_dotenv()

# Page config
st.set_page_config(
    page_title="PE Org-AI-R Platform",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

# Initialize session state
if "api_base" not in st.session_state:
    st.session_state.api_base = DEFAULT_API_BASE

# Initialize API client
api = APIClient()

# Sidebar
with st.sidebar:
    st.title("PE Org-AI-R")
    st.caption("AI Readiness Assessment Platform")
    
    st.divider()
    
    # Quick stats from real API
    st.subheader("Quick Stats")
    
    # Health check
    health = api.health_check()
    if health.get("status") == "healthy":
        st.success("✅ API Connected")
    else:
        st.error("❌ API Offline")
    
    # Company count
    try:
        companies = api.get_companies(page=1, page_size=1)
        if companies and "total" in companies:
            st.metric("Companies", companies["total"])
        else:
            st.metric("Companies", "N/A")
    except:
        st.metric("Companies", "N/A")
    
    st.divider()

# Main content
st.title("AI Readiness Assessment Platform")
st.subheader("Welcome to the PE Org-AI-R Platform")

st.markdown("""
This platform helps private equity firms assess the AI readiness of portfolio companies 
through comprehensive signal collection and analysis.
""")

st.divider()

# Fetch real metrics
@st.cache_data(ttl=300)
def fetch_dashboard_metrics():
    """Fetch real metrics from API"""
    metrics = {
        "total_companies": 0,
        "total_signals": 0,
        "avg_readiness": 0.0,
        "last_updated": "N/A"
    }
    
    try:
        # Get companies
        companies = api.get_companies(page_size=100)
        if companies and "items" in companies:
            metrics["total_companies"] = len(companies["items"])
            
            # Get signal summaries for all companies
            total_signals = 0
            total_composite = 0.0
            companies_with_signals = 0
            
            for company in companies["items"]:
                try:
                    summary = api.get_signal_summary(company["id"])
                    if summary:
                        total_signals += summary.get("signal_count", 0)
                        composite = summary.get("composite_score", 0.0)
                        if composite > 0:
                            total_composite += composite
                            companies_with_signals += 1
                        metrics["last_updated"] = summary.get("last_updated", "N/A")
                except:
                    continue
            
            metrics["total_signals"] = total_signals
            if companies_with_signals > 0:
                metrics["avg_readiness"] = total_composite / companies_with_signals
    
    except Exception as e:
        st.error(f"Error fetching metrics: {str(e)}")
    
    return metrics

metrics = fetch_dashboard_metrics()

# Quick metrics
st.subheader("Portfolio Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Companies Tracked",
        value=metrics["total_companies"],
        delta=None
    )

with col2:
    st.metric(
        label="Signals Collected",
        value=f"{metrics['total_signals']:,}",
        delta=None
    )

with col3:
    st.metric(
        label="Avg AI Readiness",
        value=f"{metrics['avg_readiness']:.1f}",
        delta=None
    )

st.divider()

st.subheader("Recent Activity")

@st.cache_data(ttl=60)
def fetch_recent_activity():
    """Fetch recent signals across all companies"""
    activities = []
    
    try:
        companies = api.get_companies(page_size=10)
        if companies and "items" in companies:
            for company in companies["items"][:5]:
                try:
                    signals = api.get_company_signals(company["id"], page_size=1)
                    if signals and "items" in signals and signals["items"]:
                        signal = signals["items"][0]
                        activities.append({
                            "timestamp": signal.get("signal_date", "N/A"),
                            "company": f"{company['name']} ({company['ticker']})",
                            "action": f"{signal.get('category', 'Unknown')} signals collected",
                            "status": "✅ Success",
                            "score": f"{signal.get('normalized_score', 0):.1f}"
                        })
                except:
                    continue
    except:
        pass
    
    return activities

activities = fetch_recent_activity()

if activities:
    df = pd.DataFrame(activities)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No recent activity. Run the Collection Dashboard to start gathering signals.")

st.divider()


# System status
st.subheader("System Status")

col1, col2 = st.columns(2)

with col1:
    health = api.health_check()
    api_status = health.get("status", "offline")
    if api_status in ("healthy", "degraded"):
        st.success("**API Status:** ✅ Connected")

        # Show dependency status
        deps = health.get("dependencies", {})
        if deps:
            st.caption("**Dependencies:**")
            for dep, dep_status in deps.items():
                emoji = "✅" if dep_status == "healthy" else "❌"
                st.caption(f"  {emoji} {dep.title()}: {dep_status}")
    else:
        st.error("**API Status:** ❌ Offline")

    st.caption(f"Endpoint: {st.session_state.api_base}")

with col2:
    # Database info
    deps = health.get("dependencies", {})
    if deps.get("snowflake") == "healthy":
        st.success("**Database:** ✅ Operational")
        st.caption("Snowflake connection active")
    elif api_status in ("healthy", "degraded"):
        st.warning("**Database:** ⚠️ Issues detected")
    else:
        st.error("**Database:** ❌ Cannot connect")

# Footer
st.divider()