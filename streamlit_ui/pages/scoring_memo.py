import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="Scoring & Memo", page_icon="📈", layout="wide")

api = APIClient()

# ── Target companies (shared with collection_dashboard) ──
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

DIMENSION_LABELS = {
    "data_infrastructure": "Data Infrastructure",
    "ai_governance": "AI Governance",
    "technology_stack": "Technology Stack",
    "talent": "Talent & Skills",
    "leadership": "Leadership & Vision",
    "use_case_portfolio": "Use Case Portfolio",
    "culture": "Culture & Change",
}

REC_COLORS = {
    "BUY": ("#2e7d32", "#d4edda"),
    "HOLD": ("#f57f17", "#fff3cd"),
    "PASS": ("#c62828", "#f8d7da"),
}

st.title("AI Readiness Scoring & Investment Memo")
st.caption("Calculate V^R scores and generate PE-style investment memos")

st.divider()

# ── Company selection ──
col_select, col_btn = st.columns([3, 1])

company_options = {
    f"{ticker} - {info['name']}": ticker
    for ticker, info in TARGET_COMPANIES.items()
}

with col_select:
    selected_label = st.selectbox("Select a company", list(company_options.keys()))
    selected_ticker = company_options[selected_label]

with col_btn:
    st.write("")  # spacer
    calculate_clicked = st.button("Calculate Scores", type="primary", use_container_width=True)

# ── Resolve company_id ──
if calculate_clicked:
    company = api.get_company_by_ticker(selected_ticker)
    if company:
        st.session_state["score_company_id"] = company["id"]
        st.session_state["score_ticker"] = selected_ticker
        st.session_state["score_company_name"] = company["name"]
        # Clear previous memo
        st.session_state.pop("memo_result", None)
    else:
        st.error(f"Company {selected_ticker} not found. Run Collection Dashboard first.")
        st.stop()

# ── Guard: need scores loaded ──
if "score_company_id" not in st.session_state:
    st.info("Select a company and click **Calculate Scores** to begin.")
    st.stop()

company_id = st.session_state["score_company_id"]
ticker = st.session_state["score_ticker"]
company_name = st.session_state["score_company_name"]

# ── Fetch scores (cached per session) ──
@st.cache_data(ttl=300, show_spinner="Calculating scores...")
def fetch_scores(cid: str):
    vr = api.get_vr_score(cid)
    dims = api.get_dimension_scores(cid)
    return vr, dims

vr_result, dim_result = fetch_scores(company_id)

if not vr_result or not dim_result:
    st.error("Failed to calculate scores. Check that evidence has been collected for this company.")
    st.stop()

st.divider()

# ── Tabs ──
tab_overview, tab_memo, tab_compare = st.tabs(["Score Overview", "Investment Memo", "Company Comparison"])

# ═══════════════════════════════════════════
#  TAB 1: Score Overview
# ═══════════════════════════════════════════
with tab_overview:
    st.subheader(f"Scores for {company_name} ({ticker})")

    # Row 1 — Key metrics
    vr_score = vr_result.get("vr_score", 0)
    vr_comp = vr_result.get("vr_components", {})

    # Determine recommendation color from score
    if vr_score >= 60:
        rec_label, rec_color = "BUY", "#2e7d32"
    elif vr_score >= 35:
        rec_label, rec_color = "HOLD", "#f57f17"
    else:
        rec_label, rec_color = "PASS", "#c62828"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("V^R Score", f"{vr_score:.1f} / 100")
    m2.markdown(
        f"**Recommendation**<br>"
        f"<span style='color:{rec_color}; font-size:1.8rem; font-weight:bold'>{rec_label}</span>",
        unsafe_allow_html=True,
    )
    m3.metric("CV Penalty", f"-{vr_comp.get('cv_penalty_amount', 0):.1f} pts")
    m4.metric("TC Penalty", f"-{vr_comp.get('tc_penalty_amount', 0):.1f} pts")

    st.divider()

    # Row 2 — Horizontal bar chart for 7 dimensions
    dim_scores = dim_result.get("dimension_scores", {})
    chart_data = []
    for dim_key, label in DIMENSION_LABELS.items():
        score_val = dim_scores.get(dim_key, {})
        if isinstance(score_val, dict):
            chart_data.append({"Dimension": label, "Score": score_val.get("score", 0)})
        else:
            chart_data.append({"Dimension": label, "Score": float(score_val) if score_val else 0})

    chart_df = pd.DataFrame(chart_data)

    def score_color(val):
        if val >= 70:
            return "#4caf50"
        elif val >= 50:
            return "#ff9800"
        elif val >= 30:
            return "#ff5722"
        return "#d32f2f"

    chart_df["Color"] = chart_df["Score"].apply(score_color)

    fig = go.Figure(
        go.Bar(
            x=chart_df["Score"],
            y=chart_df["Dimension"],
            orientation="h",
            marker_color=chart_df["Color"],
            text=chart_df["Score"].round(1),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Seven-Dimension Scores",
        xaxis_title="Score (0-100)",
        yaxis=dict(categoryorder="total ascending"),
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 3 — Detailed scores table
    st.subheader("Detailed Dimension Breakdown")

    table_rows = []
    for dim_key, label in DIMENSION_LABELS.items():
        score_data = dim_scores.get(dim_key, {})
        if isinstance(score_data, dict):
            table_rows.append({
                "Dimension": label,
                "Score": f"{score_data.get('score', 0):.1f}",
                "Confidence": f"{score_data.get('confidence', 0):.2f}",
            })
        else:
            table_rows.append({
                "Dimension": label,
                "Score": f"{float(score_data):.1f}" if score_data else "N/A",
                "Confidence": "N/A",
            })

    table_df = pd.DataFrame(table_rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # V^R components detail
    with st.expander("V^R Calculation Details"):
        detail_cols = st.columns(2)
        with detail_cols[0]:
            st.markdown(f"**Base Score (weighted mean):** {vr_comp.get('base_score', 'N/A')}")
            st.markdown(f"**Coefficient of Variation (CV):** {vr_comp.get('cv', 'N/A')}")
            st.markdown(f"**CV Penalty Factor:** {vr_comp.get('cv_penalty', 'N/A')}")
        with detail_cols[1]:
            st.markdown(f"**Talent Concentration (TC):** {vr_comp.get('talent_concentration', 'N/A')}")
            st.markdown(f"**TC Risk Adjustment:** {vr_comp.get('talent_risk_adj', 'N/A')}")
            st.markdown(f"**Sector:** {vr_result.get('sector', 'N/A')}")


# ═══════════════════════════════════════════
#  TAB 2: Investment Memo
# ═══════════════════════════════════════════
with tab_memo:
    st.subheader(f"Investment Memo — {company_name} ({ticker})")

    if st.button("Generate Investment Memo", type="primary"):
        with st.spinner("Generating memo via Claude AI... this may take up to 60 seconds"):
            memo_result = api.generate_memo(company_id)
            if memo_result:
                st.session_state["memo_result"] = memo_result
            else:
                st.error("Failed to generate memo. Check API logs for details.")

    if "memo_result" in st.session_state:
        memo = st.session_state["memo_result"]
        summary = memo.get("summary", {})
        markdown_text = memo.get("markdown", "")

        # Summary card
        rec = summary.get("recommendation", "N/A")
        text_color, bg_color = REC_COLORS.get(rec, ("#333", "#f5f5f5"))

        st.markdown(
            f"""
            <div style="background:{bg_color}; padding:1rem; border-radius:8px; margin-bottom:1rem;">
                <span style="font-size:1.4rem; font-weight:bold; color:{text_color};">
                    Recommendation: {rec}
                </span>
                &nbsp;&nbsp;|&nbsp;&nbsp;V^R: <b>{summary.get('vr_score', 'N/A')}</b>
                &nbsp;&nbsp;|&nbsp;&nbsp;Strength: <b>{summary.get('top_strength', 'N/A')}</b>
                &nbsp;&nbsp;|&nbsp;&nbsp;Weakness: <b>{summary.get('top_weakness', 'N/A')}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        discrepancies = summary.get("discrepancy_flags", [])
        if discrepancies:
            st.warning(f"Discrepancy flags: **{', '.join(discrepancies)}** (Path A vs Path B gap > 15 pts)")

        # Render memo
        st.markdown(markdown_text)

        st.divider()

        # Download buttons
        dl1, dl2 = st.columns(2)

        with dl1:
            st.download_button(
                label="Download Markdown",
                data=markdown_text,
                file_name=f"investment_memo_{ticker}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with dl2:
            # PDF generation
            try:
                from fpdf import FPDF

                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Helvetica", size=10)

                for line in markdown_text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        pdf.set_font("Helvetica", "B", 16)
                        pdf.cell(0, 10, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font("Helvetica", size=10)
                    elif stripped.startswith("## "):
                        pdf.set_font("Helvetica", "B", 13)
                        pdf.cell(0, 8, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font("Helvetica", size=10)
                    elif stripped.startswith("### "):
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.cell(0, 7, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font("Helvetica", size=10)
                    elif stripped.startswith("- "):
                        pdf.cell(5)
                        pdf.multi_cell(0, 5, stripped)
                    elif stripped.startswith("|"):
                        pdf.set_font("Courier", size=8)
                        pdf.cell(0, 4, stripped, new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font("Helvetica", size=10)
                    elif stripped == "":
                        pdf.ln(3)
                    else:
                        pdf.multi_cell(0, 5, stripped)

                pdf_bytes = pdf.output()
                st.download_button(
                    label="Download PDF",
                    data=bytes(pdf_bytes),
                    file_name=f"investment_memo_{ticker}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.info("PDF export requires `fpdf2`. Install with: `pip install fpdf2`")
            except Exception as e:
                st.warning(f"PDF generation failed: {e}. Markdown download is available above.")

    else:
        st.info("Click **Generate Investment Memo** to create a PE-style memo using Claude AI.")


# ═══════════════════════════════════════════
#  TAB 3: Company Comparison
# ═══════════════════════════════════════════
with tab_compare:
    st.subheader("Compare V^R Scores Across Companies")

    compare_options = [
        f"{ticker} - {info['name']}" for ticker, info in TARGET_COMPANIES.items()
    ]

    selected_compare = st.multiselect(
        "Select 2-4 companies to compare",
        compare_options,
        default=[compare_options[0], compare_options[1]] if len(compare_options) >= 2 else [],
        max_selections=4,
    )

    if st.button("Compare", type="primary") and len(selected_compare) >= 2:
        compare_tickers = [opt.split(" - ")[0] for opt in selected_compare]

        # Resolve company IDs
        compare_ids = []
        ticker_map = {}
        for t in compare_tickers:
            c = api.get_company_by_ticker(t)
            if c:
                compare_ids.append(c["id"])
                ticker_map[c["id"]] = t

        if len(compare_ids) < 2:
            st.error("Could not resolve enough companies. Ensure they exist in the database.")
        else:
            with st.spinner("Calculating V^R for selected companies..."):
                comparison = api.compare_vr_scores(compare_ids)

            if comparison and "companies" in comparison:
                companies_data = comparison["companies"]

                # Bar chart
                bar_data = []
                for t, data in companies_data.items():
                    bar_data.append({
                        "Company": f"{data['company_name']} ({t})",
                        "V^R Score": data["vr_score"],
                    })

                bar_df = pd.DataFrame(bar_data).sort_values("V^R Score", ascending=False)

                fig = px.bar(
                    bar_df,
                    x="V^R Score",
                    y="Company",
                    orientation="h",
                    title="V^R Score Comparison",
                    text="V^R Score",
                    color="V^R Score",
                    color_continuous_scale=["#d32f2f", "#ff9800", "#4caf50"],
                )
                fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
                fig.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    height=300 + len(bar_data) * 40,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Comparison table
                st.subheader("Detailed Comparison")
                comp_rows = []
                for t, data in companies_data.items():
                    comp_rows.append({
                        "Ticker": t,
                        "Company": data["company_name"],
                        "V^R Score": f"{data['vr_score']:.1f}",
                        "Base Score": f"{data['base_score']:.1f}",
                        "CV": f"{data['cv']:.3f}",
                        "CV Penalty": f"{data['cv_penalty']:.3f}",
                        "TC": f"{data['talent_concentration']:.3f}",
                        "Sector": data["sector"],
                    })

                comp_df = pd.DataFrame(comp_rows)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
            else:
                st.error("Comparison failed. Some companies may not have enough data.")

    elif len(selected_compare) < 2:
        st.info("Select at least 2 companies to compare.")
