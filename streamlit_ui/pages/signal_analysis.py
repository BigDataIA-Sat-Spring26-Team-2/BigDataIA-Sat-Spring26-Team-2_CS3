# streamlit_ui/pages/signal_analysis.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="Signal Analysis", page_icon="🔍", layout="wide")

# Initialize API client
api = APIClient()

st.title("🔍 Signal Analysis")
st.caption("Analyze AI readiness signals across portfolio companies")

st.divider()

# Fetch all companies with signals
@st.cache_data(ttl=300)
def fetch_all_companies_with_signals():
    """Fetch all companies and their signal summaries"""
    companies_result = api.get_companies(page_size=100)
    
    if not companies_result or "items" not in companies_result:
        return []
    
    companies_data = []
    for company in companies_result["items"]:
        company_id = company['id']
        
        # Fetch signal summary
        summary = api.get_signal_summary(company_id)
        
        if summary:
            companies_data.append({
                'id': company_id,
                'name': company['name'],
                'ticker': company['ticker'],
                'industry_id': company['industry_id'],
                'tech_hiring': summary.get('technology_hiring_score', 0.0),
                'innovation': summary.get('innovation_activity_score', 0.0),
                'digital': summary.get('digital_presence_score', 0.0),
                'leadership': summary.get('leadership_signals_score', 0.0),
                'composite': summary.get('composite_score', 0.0),
                'signal_count': summary.get('signal_count', 0),
            })
    
    return companies_data

# Load data
with st.spinner("Loading company data..."):
    companies_data = fetch_all_companies_with_signals()

if not companies_data:
    st.warning("⚠️ No companies with signal data found.")
    st.info("Run the Collection Dashboard to gather signals for companies.")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(companies_data)

# Filters
st.subheader("🎛️ Filters")

col1, col2, col3 = st.columns(3)

with col1:
    # Filter by name/ticker
    search_term = st.text_input("Search company name or ticker")
    if search_term:
        df = df[
            df['name'].str.contains(search_term, case=False) | 
            df['ticker'].str.contains(search_term, case=False)
        ]

with col2:
    signal_category = st.selectbox(
        "Signal Category",
        ["All Signals", "Technology Hiring", "Leadership Signals", "Innovation Activity", "Digital Presence"]
    )

with col3:
    min_score = st.slider(
        "Minimum Composite Score",
        min_value=0,
        max_value=100,
        value=0,
        step=5
    )
    df = df[df['composite'] >= min_score]

st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🏆 Rankings", "🔬 Deep Dive"])

with tab1:
    st.subheader("📊 Portfolio Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Score distribution
        fig = px.histogram(
            df,
            x='composite',
            nbins=15,
            title="AI Readiness Score Distribution",
            labels={'composite': 'Composite Score', 'count': 'Count'}
        )
        fig.update_traces(marker_color='#1f77b4')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Average scores by signal type
        avg_scores = pd.DataFrame({
            'Signal': ['Technology Hiring', 'Innovation Activity', 'Digital Presence', 'Leadership Signals'],
            'Average Score': [
                df['tech_hiring'].mean(),
                df['innovation'].mean(),
                df['digital'].mean(),
                df['leadership'].mean()
            ]
        })
        
        fig = px.bar(
            avg_scores,
            x='Average Score',
            y='Signal',
            orientation='h',
            title="Average Score by Signal Type",
            text='Average Score'
        )
        fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    
    # Key statistics
    st.subheader("📈 Key Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Companies Analyzed", len(df))
    
    with col2:
        st.metric("Avg AI Readiness", f"{df['composite'].mean():.1f}")
    
    with col3:
        st.metric("Highest Score", f"{df['composite'].max():.1f}")
    
    with col4:
        st.metric("Total Signals", df['signal_count'].sum())

with tab2:
    st.subheader("🏆 Company Rankings")
    
    # Ranking options
    rank_by = st.radio(
        "Rank by:",
        ["Composite Score", "Technology Hiring", "Innovation Activity", "Digital Presence", "Leadership Signals"],
        horizontal=True
    )
    
    # Map selection to column
    column_map = {
        "Composite Score": "composite",
        "Technology Hiring": "tech_hiring",
        "Innovation Activity": "innovation",
        "Digital Presence": "digital",
        "Leadership Signals": "leadership"
    }
    
    score_col = column_map[rank_by]
    
    # Sort data
    sorted_df = df.sort_values(score_col, ascending=False).copy()
    sorted_df['Rank'] = range(1, len(sorted_df) + 1)
    
    # Display rankings table
    display_df = sorted_df[['Rank', 'name', 'ticker', score_col]].copy()
    display_df.columns = ['Rank', 'Company', 'Ticker', 'Score']
    
    # Color code scores
    def color_score(val):
        if val >= 70:
            return 'background-color: #d4edda'
        elif val >= 60:
            return 'background-color: #fff3cd'
        else:
            return 'background-color: #f8d7da'
    
    styled_df = display_df.style.applymap(color_score, subset=['Score'])
    styled_df = styled_df.format({'Score': '{:.1f}'})
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Top 5 visualization
    st.subheader("📊 Top 5 Companies")
    
    top_5 = sorted_df.head(5)
    
    fig = px.bar(
        top_5,
        x=score_col,
        y='name',
        orientation='h',
        title=f"Top 5 by {rank_by}",
        text=score_col,
        hover_data=['ticker']
    )
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🔬 Deep Dive Analysis")
    
    # Company selector
    selected_company_name = st.selectbox(
        "Select Company for Deep Dive",
        df['name'].tolist()
    )
    
    company_row = df[df['name'] == selected_company_name].iloc[0]
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Composite Score", f"{company_row['composite']:.1f}")
    
    with col2:
        st.metric("Technology Hiring", f"{company_row['tech_hiring']:.1f}")
    
    with col3:
        st.metric("Signal Count", int(company_row['signal_count']))
    
    with col4:
        st.metric("Ticker", company_row['ticker'])
    
    # Radar chart
    st.subheader("🔡 Signal Breakdown")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=[
            company_row['tech_hiring'],
            company_row['innovation'],
            company_row['digital'],
            company_row['leadership']
        ],
        theta=['Technology Hiring', 'Innovation Activity', 'Digital Presence', 'Leadership Signals'],
        fill='toself',
        name=selected_company_name
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="AI Readiness Radar"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Comparison with portfolio average
    st.subheader("📊 Comparison with Portfolio Average")
    
    comparison_data = pd.DataFrame({
        'Signal': ['Technology Hiring', 'Innovation Activity', 'Digital Presence', 'Leadership Signals'],
        'Company': [
            company_row['tech_hiring'],
            company_row['innovation'],
            company_row['digital'],
            company_row['leadership']
        ],
        'Portfolio Avg': [
            df['tech_hiring'].mean(),
            df['innovation'].mean(),
            df['digital'].mean(),
            df['leadership'].mean()
        ]
    })
    
    fig = px.bar(
        comparison_data.melt(id_vars=['Signal'], var_name='Type', value_name='Score'),
        x='Signal',
        y='Score',
        color='Type',
        barmode='group',
        title=f"{selected_company_name} vs Portfolio Average"
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Export section
st.subheader("📥 Export Data")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Download CSV", use_container_width=True):
        csv = df.to_csv(index=False)
        st.download_button(
            label="Save CSV",
            data=csv,
            file_name=f"signal_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

with col2:
    if st.button("Generate Report", use_container_width=True):
        st.info("Report generation coming soon")

with col3:
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()