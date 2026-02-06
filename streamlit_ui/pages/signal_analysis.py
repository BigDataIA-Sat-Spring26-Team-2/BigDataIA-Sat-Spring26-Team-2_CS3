# streamlit_ui/pages/signal_analysis.py
import streamlit as st
import pandas as pd
import plotly.express as px
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
    st.warning("No companies with signal data found.")
    st.info("Run the Collection Dashboard to gather signals for companies.")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(companies_data)

# Tabs
st.subheader("Company Rankings")

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
st.subheader("Top 5 Companies")

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

st.divider()
