# streamlit_ui/pages/company_reports.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="Company Reports", page_icon="📈", layout="wide")

# Initialize API client
api = APIClient()

st.title("📈 Company AI Readiness Report")
st.caption("Detailed analysis of individual companies")

st.divider()

# Fetch real companies from API
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_companies():
    """Fetch companies from API"""
    result = api.get_companies(page_size=100)
    if result and "items" in result:
        return result["items"]
    return []

# Load companies
companies = fetch_companies()

if not companies:
    st.error("⚠️ No companies found. Please ensure the API is running and companies are created.")
    st.info("You can create companies using the Collection Dashboard or the API directly.")
    st.stop()

# Create company selection dropdown
company_names = {f"{c['name']} ({c['ticker']})": c for c in companies}
selected_company_name = st.selectbox(
    "Select Company",
    list(company_names.keys())
)

company = company_names[selected_company_name]
company_id = company['id']

# Fetch signal summary for selected company
@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_signal_summary(comp_id):
    """Fetch signal summary from API"""
    return api.get_signal_summary(comp_id)

signal_summary = fetch_signal_summary(company_id)

if not signal_summary:
    st.warning(f"⚠️ No signal data found for {company['name']}. Run collection first.")
    
    col1, col2, col3 = st.columns(3)
    with col2:
        if st.button("🔄 Collect Signals Now", use_container_width=True, type="primary"):
            with st.spinner(f"Collecting signals for {company['name']}..."):
                try:
                    result = api.collect_job_signals(
                        company_id=company_id,
                        company_name=company['name'],
                        max_results=20
                    )
                    if result:
                        st.success("✅ Signals collected successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Failed to collect signals")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    st.stop()

# Display company header
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.title(f"{company['name']}")
    st.caption(f"{company['ticker']} | {company.get('industry_id', 'Unknown Industry')}")

with col2:
    composite_score = signal_summary.get('composite_score', 0.0)
    st.metric(
        "AI Readiness Score",
        f"{composite_score:.1f}",
        delta=None
    )

with col3:
    if st.button("🔄 Refresh Signals", use_container_width=True):
        with st.spinner("Refreshing..."):
            try:
                api.refresh_signal_summary(company_id)
                st.cache_data.clear()
                st.success("✅ Refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

st.divider()

# Score breakdown
st.subheader("📊 Score Breakdown")

col1, col2, col3, col4 = st.columns(4)

tech_hiring_score = signal_summary.get('technology_hiring_score', 0.0)
innovation_score = signal_summary.get('innovation_activity_score', 0.0)
digital_score = signal_summary.get('digital_presence_score', 0.0)
leadership_score = signal_summary.get('leadership_signals_score', 0.0)

with col1:
    contribution = tech_hiring_score * 0.30
    st.metric(
        "Technology Hiring",
        f"{tech_hiring_score:.1f}",
        delta=f"→ {contribution:.1f} pts"
    )
    st.caption("Weight: 30%")

with col2:
    contribution = innovation_score * 0.25
    st.metric(
        "Innovation Activity",
        f"{innovation_score:.1f}",
        delta=f"→ {contribution:.1f} pts"
    )
    st.caption("Weight: 25%")

with col3:
    contribution = digital_score * 0.25
    st.metric(
        "Digital Presence",
        f"{digital_score:.1f}",
        delta=f"→ {contribution:.1f} pts"
    )
    st.caption("Weight: 25%")

with col4:
    contribution = leadership_score * 0.20
    st.metric(
        "Leadership Signals",
        f"{leadership_score:.1f}",
        delta=f"→ {contribution:.1f} pts"
    )
    st.caption("Weight: 20%")

st.divider()

# Radar chart and gauge
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🎯 AI Readiness Radar")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=[tech_hiring_score, innovation_score, digital_score, leadership_score],
        theta=['Technology Hiring', 'Innovation Activity', 'Digital Presence', 'Leadership Signals'],
        fill='toself',
        name=company['name'],
        line_color='#1f77b4'
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📈 Score Composition")
    
    # Score gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=composite_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Composite AI Readiness"},
        delta={'reference': 65},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 40], 'color': "lightgray"},
                {'range': [40, 70], 'color': "gray"},
                {'range': [70, 100], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 70
            }
        }
    ))
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Fetch detailed signals
@st.cache_data(ttl=60)
def fetch_signals(comp_id):
    """Fetch detailed signals"""
    return api.get_company_signals(comp_id, page_size=100)

signals_data = fetch_signals(company_id)

# Detailed tabs
tabs = st.tabs(["💼 Technology Hiring", "🚀 Leadership Signals", "📜 Evidence", "📊 History"])

with tabs[0]:
    st.subheader("💼 Technology Hiring Details")
    
    # Get the latest tech hiring signal
    tech_signals = []
    if signals_data and "items" in signals_data:
        tech_signals = [s for s in signals_data["items"] if s.get("category") == "technology_hiring"]
    
    if tech_signals:
        latest_signal = tech_signals[0]  # Most recent
        metadata = latest_signal.get("metadata", {})
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("AI Jobs Found", metadata.get('ai_jobs', 0))
        
        with col2:
            st.metric("Total Tech Jobs", metadata.get('total_tech_jobs', 0))
        
        with col3:
            ai_ratio = metadata.get('ai_ratio', 0.0)
            st.metric("AI Ratio", f"{ai_ratio:.1%}")
        
        with col4:
            avg_relevance = metadata.get('avg_ai_relevance', 0.0)
            st.metric("Avg Relevance", f"{avg_relevance:.3f}")
        
        # Skills breakdown
        st.subheader("🔧 Top AI Skills")
        
        top_skills = metadata.get('top_skills', [])
        if top_skills:
            skills_df = pd.DataFrame(top_skills, columns=['Skill', 'Count'])
            
            fig = px.bar(
                skills_df.head(10),
                x='Count',
                y='Skill',
                orientation='h',
                title="AI Skills Mentioned in Job Postings",
                text='Count'
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No skill data available")
        
        # Seniority distribution
        st.subheader("👔 Seniority Distribution")
        
        seniority_dist = metadata.get('seniority_distribution', {})
        if seniority_dist:
            seniority_df = pd.DataFrame(
                list(seniority_dist.items()),
                columns=['Level', 'Count']
            )
            
            fig = px.pie(
                seniority_df,
                values='Count',
                names='Level',
                title="AI Jobs by Seniority Level"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No seniority data available")
    else:
        st.info("No technology hiring signals found. Run collection to gather data.")

with tabs[1]:
    st.subheader("🚀 Leadership Signals")
    st.info("🚧 Leadership signal collection coming soon")
    
    st.write("**This will include:**")
    st.write("- Executive appointments (AI leadership)")
    st.write("- M&A activity (AI acquisitions)")
    st.write("- Strategic partnerships (AI collaborations)")
    st.write("- Compensation alignment (exec incentives)")

with tabs[2]:
    st.subheader("📜 Supporting Evidence")
    
    if signals_data and "items" in signals_data:
        for signal in signals_data["items"]:
            with st.expander(f"🔍 {signal['category']} - {signal['signal_date']}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Category:** {signal['category']}")
                    st.write(f"**Source:** {signal['source']}")
                    st.write(f"**Raw Value:** {signal['raw_value']}")
                    st.write(f"**Score:** {signal['normalized_score']:.1f}/100")
                    st.write(f"**Confidence:** {signal['confidence']:.2f}")
                
                with col2:
                    # Mini gauge
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=signal['normalized_score'],
                        domain={'x': [0, 1], 'y': [0, 1]},
                        gauge={'axis': {'range': [None, 100]}}
                    ))
                    fig.update_layout(height=150, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No evidence found")

with tabs[3]:
    st.subheader("📊 Score History")
    st.info("🚧 Historical tracking coming soon - collect data over time to see trends")
    
    st.write("Future features:")
    st.write("- Track score changes over time")
    st.write("- Compare against industry benchmarks")
    st.write("- Identify improvement trends")

st.divider()

