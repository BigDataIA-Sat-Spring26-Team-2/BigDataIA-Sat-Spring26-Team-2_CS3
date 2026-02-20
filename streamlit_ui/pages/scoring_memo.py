import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
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
    "NVDA": {"name": "NVIDIA Corporation",   "sector": "Technology"},
    "DG":   {"name": "Dollar General Corp",  "sector": "Retail"},
    "GE":   {"name": "General Electric Co",  "sector": "Manufacturing"},
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


st.title("AI Readiness Scoring & Investment Memo")
st.caption("Calculate V^R scores and generate PE-style investment memos")

st.divider()

# ── Company selection ──
col_select, col_btn = st.columns([3, 1])

company_options = {
    f"{tkr} - {info['name']}": tkr
    for tkr, info in TARGET_COMPANIES.items()
}

with col_select:
    selected_label = st.selectbox("Select a company", list(company_options.keys()))
    selected_ticker = company_options[selected_label]

with col_btn:
    st.write("")  # spacer
    calculate_clicked = st.button("Calculate Scores", type="primary", use_container_width=True)

# ── Resolve company_id and fetch scores on click ──
if calculate_clicked:
    try:
        company = api.get_company_by_ticker(selected_ticker)
    except Exception:
        company = None

    if company:
        st.session_state["score_company_id"] = company["id"]
        st.session_state["score_ticker"] = selected_ticker
        st.session_state["score_company_name"] = company["name"]
        # Clear previous memo and cached scores when switching company
        st.session_state.pop("memo_result", None)
        st.session_state.pop("cached_vr", None)
        st.session_state.pop("cached_dims", None)
        st.session_state.pop("cached_org_air", None)
    else:
        st.error(f"Company **{selected_ticker}** not found in the database. Run the Collection Dashboard first to register it.")
        st.stop()

# ── Guard: need scores loaded ──
if "score_company_id" not in st.session_state:
    st.info("Select a company and click **Calculate Scores** to begin.")
    st.stop()

company_id = st.session_state["score_company_id"]
ticker = st.session_state["score_ticker"]
company_name = st.session_state["score_company_name"]

# ── Fetch scores (session-state cached, cleared on company switch) ──
if "cached_org_air" not in st.session_state or "cached_dims" not in st.session_state:
    with st.spinner("Calculating Org-AI-R scores (full pipeline)..."):
        try:
            org_air_result = api.get_org_air_score(str(company_id))
            dim_result = api.get_dimension_scores(company_id)
        except Exception as e:
            st.error(f"Connection error: {e}")
            st.stop()

    if not org_air_result or "org_air_score" not in org_air_result:
        st.error("Failed to calculate Org-AI-R score. Ensure evidence has been collected and CS1 API is running.")
        st.stop()
    if not dim_result or "dimension_scores" not in dim_result:
        st.error("Failed to calculate dimension scores. Ensure evidence has been collected for this company.")
        st.stop()

    st.session_state["cached_org_air"] = org_air_result
    st.session_state["cached_dims"] = dim_result

    # Build a vr_result-shaped dict from org-air result for backward compatibility
    st.session_state["cached_vr"] = {
        "vr_score": org_air_result.get("vr_score", 0),
        "ticker": org_air_result.get("ticker"),
        "sector": org_air_result.get("sector"),
        "dimension_scores": org_air_result.get("dimension_scores", {}),
        "vr_components": {
            "base_score": org_air_result.get("vr_weighted_mean", 0),
            "cv": org_air_result.get("vr_cv", 0),
            "cv_penalty": org_air_result.get("vr_cv", 0),
            "cv_penalty_amount": org_air_result.get("vr_cv_penalty_amount", 0),
            "talent_concentration": org_air_result.get("talent_concentration", 0),
            "talent_risk_adj": 1.0,
            "tc_penalty_amount": org_air_result.get("vr_tc_penalty_amount", 0),
        },
    }

vr_result = st.session_state["cached_vr"]
dim_result = st.session_state["cached_dims"]

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

    m1, m2, m3 = st.columns(3)
    m1.metric("V^R Score", f"{vr_score:.1f} / 100")
    m2.metric("CV Penalty", f"-{vr_comp.get('cv_penalty_amount', 0):.1f} pts")
    m3.metric("TC Penalty", f"-{vr_comp.get('tc_penalty_amount', 0):.1f} pts")

    # Show Org-AI-R / HR / alignment if available
    org_air_data = st.session_state.get("cached_org_air", {})
    org_air = org_air_data.get("org_air_score")
    hr = org_air_data.get("hr_score")
    alignment_val = org_air_data.get("alignment")
    board_gov = org_air_data.get("board_governance_score")
    ci_lower = org_air_data.get("ci_lower")
    ci_upper = org_air_data.get("ci_upper")

    if org_air is not None or hr is not None:
        st.divider()
        st.markdown("#### Full Org-AI-R Context")
        o1, o2, o3, o4 = st.columns(4)
        o1.metric(
            "Org-AI-R Score",
            f"{org_air:.1f} / 100" if isinstance(org_air, (int, float)) else "N/A",
        )
        o2.metric(
            "H^R (Industry Baseline)",
            f"{hr:.1f} / 100" if isinstance(hr, (int, float)) else "N/A",
        )
        if isinstance(alignment_val, (int, float)):
            o3.metric("Alignment", f"{alignment_val:.2f}")
        if isinstance(board_gov, (int, float)):
            o4.metric("Board Governance", f"{board_gov:.1f} / 100")

        # Second row: confidence interval + extra details
        if ci_lower is not None and ci_upper is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Confidence Interval",
                f"[{ci_lower:.1f}, {ci_upper:.1f}]",
            )
            synergy = org_air_data.get("synergy_score")
            if isinstance(synergy, (int, float)):
                c2.metric("Synergy Score", f"{synergy:.1f}")
            tc = org_air_data.get("talent_concentration")
            if isinstance(tc, (int, float)):
                c3.metric("Talent Concentration", f"{tc:.3f}")
            pf = org_air_data.get("position_factor")
            if isinstance(pf, (int, float)):
                c4.metric("Position Factor", f"{pf:.3f}")
    else:
        st.caption("Org-AI-R scores could not be loaded. Check that the integration service dependencies are available.")

    st.divider()

    # Row 2 — Horizontal bar chart for 7 dimensions
    dim_scores = dim_result.get("dimension_scores", {})
    vr_dim_scores = vr_result.get("dimension_scores", {})

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
        xaxis_range=[0, 100],
        yaxis=dict(categoryorder="total ascending"),
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 3 — Detailed scores table with Path A scores from VR + dimension endpoint
    st.subheader("Detailed Dimension Breakdown")

    # Get rubric details from audit trail if available
    audit = dim_result.get("audit_trail", {})
    rubric_details = audit.get("rubric_details", {})

    table_rows = []
    for dim_key, label in DIMENSION_LABELS.items():
        score_data = dim_scores.get(dim_key, {})
        vr_dim = vr_dim_scores.get(dim_key, None)

        # Path A (quantitative) score
        if isinstance(score_data, dict):
            path_a = score_data.get("score", 0)
            confidence = score_data.get("confidence", 0)
        else:
            path_a = float(score_data) if score_data else 0
            confidence = None

        # Path B (qualitative) score from rubric
        rb = rubric_details.get(dim_key, {})
        path_b = rb.get("score", None) if isinstance(rb, dict) else None

        # Combined = 0.6 * Path A + 0.4 * Path B (consistent blending)
        if path_b is not None:
            combined = round(path_a * 0.6 + path_b * 0.4, 1)
        else:
            combined = path_a

        delta = abs(path_a - path_b) if path_b is not None else None

        table_rows.append({
            "Dimension": label,
            "Path A (Quantitative)": f"{path_a:.1f}",
            "Path B (Qualitative)": f"{path_b:.1f}" if path_b is not None else "N/A",
            "Combined (0.6A+0.4B)": f"{combined:.1f}",
            "Delta": f"{delta:.1f}" if delta is not None else "N/A",
            "Confidence": f"{confidence:.2f}" if confidence is not None else "N/A",
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

    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        generate_clicked = st.button("Generate Investment Memo", type="primary", use_container_width=True)
    with btn_col2:
        regenerate_clicked = st.button("Regenerate (Fresh Claude Call)", use_container_width=True)

    if generate_clicked or regenerate_clicked:
        # If "Generate" → check S3 cache first; if "Regenerate" → skip cache
        memo_result = None
        served_from_cache = False

        if generate_clicked and not regenerate_clicked:
            with st.spinner("Checking for existing memo in S3..."):
                cached = api.get_cached_memo(ticker=ticker, company_id=str(company_id))
                if cached and "markdown" in cached:
                    memo_result = cached
                    served_from_cache = True

        if not memo_result:
            with st.spinner("Generating memo via Claude AI... this may take up to 60 seconds"):
                try:
                    memo_result = api.generate_memo(company_id)
                except Exception as e:
                    memo_result = None
                    st.error(f"Connection error while generating memo: {e}")

        if memo_result and "markdown" in memo_result:
            st.session_state["memo_result"] = memo_result
            if served_from_cache:
                st.success(f"Memo loaded from cache (generated at {memo_result.get('generated_at', 'unknown')})")
            else:
                st.success("New memo generated via Claude AI and saved to S3.")
        elif memo_result:
            st.error(f"Memo generation returned unexpected response. Check API logs.")

    if "memo_result" in st.session_state:
        memo = st.session_state["memo_result"]
        summary = memo.get("summary", {})
        markdown_text = memo.get("markdown", "")

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
        f"{tkr} - {info['name']}" for tkr, info in TARGET_COMPANIES.items()
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
        missing_tickers = []
        for tkr in compare_tickers:
            try:
                c = api.get_company_by_ticker(tkr)
            except Exception:
                c = None
            if c:
                compare_ids.append(c["id"])
            else:
                missing_tickers.append(tkr)

        if missing_tickers:
            st.warning(f"Companies not found in database: **{', '.join(missing_tickers)}**. Run Collection Dashboard first.")

        if len(compare_ids) < 2:
            st.error("Need at least 2 companies in the database to compare.")
        else:
            with st.spinner("Calculating V^R for selected companies..."):
                try:
                    comparison = api.compare_vr_scores(compare_ids)
                except Exception as e:
                    comparison = None
                    st.error(f"Comparison failed: {e}")

            if comparison and "companies" in comparison:
                companies_data = comparison["companies"]

                # Bar chart
                bar_data = []
                for tkr_key, data in companies_data.items():
                    bar_data.append({
                        "Company": f"{data['company_name']} ({tkr_key})",
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
                    xaxis_range=[0, 100],
                    height=300 + len(bar_data) * 50,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Comparison table
                st.subheader("Detailed Comparison")
                comp_rows = []
                for tkr_key, data in companies_data.items():
                    comp_rows.append({
                        "Ticker": tkr_key,
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
            elif comparison is not None:
                st.error("Comparison returned no results. Some companies may not have enough evidence data.")

    elif len(selected_compare) < 2:
        st.info("Select at least 2 companies to compare.")
