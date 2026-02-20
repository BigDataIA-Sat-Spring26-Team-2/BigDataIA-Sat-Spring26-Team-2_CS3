import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="V^R Calculator", page_icon="📊", layout="wide")

api = APIClient()

# ── Constants (mirrored from app/scoring/vr_calculator.py) ────────────────────

DIMENSION_LABELS = {
    "data_infrastructure": "Data Infrastructure",
    "ai_governance": "AI Governance",
    "technology_stack": "Technology Stack",
    "talent": "Talent & Skills",
    "leadership": "Leadership & Vision",
    "use_case_portfolio": "Use Case Portfolio",
    "culture": "Culture & Change",
}

# Sector weights from VRCalculator.SECTOR_WEIGHTS
SECTOR_WEIGHTS = {
    "technology": {
        "data_infrastructure": 0.25, "ai_governance": 0.15,
        "technology_stack": 0.20, "talent": 0.20,
        "leadership": 0.10, "use_case_portfolio": 0.05, "culture": 0.05,
    },
    "financial_services": {
        "data_infrastructure": 0.25, "ai_governance": 0.25,
        "technology_stack": 0.15, "talent": 0.15,
        "leadership": 0.10, "use_case_portfolio": 0.05, "culture": 0.05,
    },
    "healthcare": {
        "data_infrastructure": 0.25, "ai_governance": 0.25,
        "technology_stack": 0.15, "talent": 0.15,
        "leadership": 0.10, "use_case_portfolio": 0.05, "culture": 0.05,
    },
    "retail": {
        "data_infrastructure": 0.25, "ai_governance": 0.15,
        "technology_stack": 0.15, "talent": 0.15,
        "leadership": 0.10, "use_case_portfolio": 0.15, "culture": 0.05,
    },
    "manufacturing": {
        "data_infrastructure": 0.25, "ai_governance": 0.20,
        "technology_stack": 0.15, "talent": 0.15,
        "leadership": 0.10, "use_case_portfolio": 0.10, "culture": 0.05,
    },
    "business_services": {
        "data_infrastructure": 0.25, "ai_governance": 0.20,
        "technology_stack": 0.15, "talent": 0.15,
        "leadership": 0.10, "use_case_portfolio": 0.10, "culture": 0.05,
    },
}

DEFAULT_WEIGHTS = {
    "data_infrastructure": 0.25, "ai_governance": 0.20,
    "technology_stack": 0.15, "talent": 0.15,
    "leadership": 0.10, "use_case_portfolio": 0.10, "culture": 0.05,
}

# Sector name normalisation (mirrors VRCalculator._get_sector_weights mapping)
SECTOR_MAPPING = {
    "financial": "financial_services",
    "financials": "financial_services",
    "financial services": "financial_services",
    "financial_services": "financial_services",
    "manufacturing": "manufacturing",
    "industrials": "manufacturing",
    "healthcare": "healthcare",
    "healthcare services": "healthcare",
    "retail": "retail",
    "consumer": "retail",
    "technology": "technology",
    "tech": "technology",
    "services": "business_services",
    "business services": "business_services",
    "business_services": "business_services",
}


def _resolve_sector_key(sector: str) -> str:
    """Normalise sector name to a SECTOR_WEIGHTS key."""
    key = sector.lower().strip().replace(" ", "_").replace("-", "_")
    return SECTOR_MAPPING.get(key, SECTOR_MAPPING.get(sector.lower().strip(), ""))


def _get_weights_for_sector(sector: str) -> dict:
    key = _resolve_sector_key(sector)
    return SECTOR_WEIGHTS.get(key, DEFAULT_WEIGHTS)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("📊 V^R Calculator")
    st.caption("Venture Readiness scoring using real API data.")
    st.divider()
    try:
        health = api.health_check()
        if health.get("status") in ("healthy", "degraded"):
            st.success("API Connected")
        else:
            st.error("API Offline")
    except Exception:
        st.error("API Offline")
    st.divider()
    if st.button("Refresh Data", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("vr_"):
                del st.session_state[k]
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📊 V^R Venture Readiness Calculator")
st.caption("Calculate V^R scores from real dimension data (Path A + Path B) via the scoring API")
st.divider()

# ── Formula Reference ─────────────────────────────────────────────────────────

with st.expander("📐 Formula Reference", expanded=False):
    fx_c1, fx_c2, fx_c3 = st.columns(3)

    with fx_c1:
        st.markdown("#### V^R Formula")
        st.latex(r"V^R = \bar{D}_w \times (1 - \lambda \cdot CV_D) \times TalentRiskAdj")
        st.markdown("""
**Where:**
- **D_w** — Weighted mean of 7 dimension scores
- **lambda = 0.25** — CV penalty coefficient
- **CV_D** — Coefficient of variation across dimensions
- **TalentRiskAdj** = 1 - 0.15 x max(0, TC - 0.25)
        """)

    with fx_c2:
        st.markdown("#### Sector Weights")
        weights_rows = []
        for sector_name, weights in SECTOR_WEIGHTS.items():
            row = {"Sector": sector_name.replace("_", " ").title()}
            for dim_key, label in DIMENSION_LABELS.items():
                row[label] = weights.get(dim_key, DEFAULT_WEIGHTS[dim_key])
            weights_rows.append(row)
        st.dataframe(
            pd.DataFrame(weights_rows),
            hide_index=True,
            use_container_width=True,
        )

    with fx_c3:
        st.markdown("#### CV + TC Penalties")
        st.markdown("""
**CV Penalty (non-compensatory):**
- Penalises unbalanced dimension profiles
- `cv_penalty = 1 - 0.25 * CV`
- Higher CV = more penalty (max CV ~1.0)

**TC Penalty (talent concentration risk):**
- Applies when TC > 25%
- `talent_risk_adj = 1 - 0.15 * max(0, TC - 0.25)`
- Protects against over-reliance on a few key people
        """)

st.divider()

# ── Load companies + industries ───────────────────────────────────────────────

with st.spinner("Loading companies and industries..."):
    try:
        co_data = api.get_companies(page_size=100)
        companies = co_data.get("items", [])
        ind_data = api.get_industries(page_size=100)
        industries = ind_data.get("items", [])
    except Exception as e:
        st.error(f"Failed to load API data: {e}")
        st.stop()

if not companies:
    st.warning("No companies found. Add companies via the Data Management page first.")
    st.stop()

ind_lookup: dict = {
    ind["id"]: {
        "name": ind.get("name", "Unknown"),
        "sector": ind.get("sector", ""),
        "h_r_base": float(ind.get("h_r_base") or 0.0),
    }
    for ind in industries
}

# ── Company Selection ─────────────────────────────────────────────────────────

st.subheader("Select Company")


def _co_label(c: dict) -> str:
    sec = ind_lookup.get(c.get("industry_id", ""), {}).get("sector", "") or "—"
    return f"{c['ticker']} — {c['name']} ({sec})"


col_select, col_btn = st.columns([3, 1])

with col_select:
    selected_co = st.selectbox(
        "Company",
        options=companies,
        format_func=_co_label,
        key="vr_co_select",
        label_visibility="collapsed",
    )

with col_btn:
    st.write("")  # spacer
    calc_clicked = st.button(
        "Calculate V^R",
        type="primary",
        use_container_width=True,
        key="vr_calc_btn",
    )

# ── Resolve company metadata ─────────────────────────────────────────────────

ind_id = selected_co.get("industry_id", "")
ind_info = ind_lookup.get(ind_id, {})
sector = ind_info.get("sector") or "Unknown"
ind_name = ind_info.get("name") or "Unknown"
company_id = selected_co["id"]

# ── Trigger calculation ──────────────────────────────────────────────────────

if calc_clicked:
    with st.spinner("Calculating dimension scores and V^R (this may take a minute)..."):
        try:
            dim_result = api.get_dimension_scores(company_id)
            org_air_result = api.get_org_air_score(company_id)
        except Exception as e:
            st.error(f"API connection error: {e}")
            st.stop()

    if not dim_result or "dimension_scores" not in dim_result:
        st.error("Failed to calculate dimension scores. Ensure evidence has been collected for this company.")
        st.stop()

    if not org_air_result or "vr_score" not in org_air_result:
        st.error("Failed to calculate V^R score. Check that the scoring API is running and evidence exists.")
        st.stop()

    # Build vr_result from org_air_result (same as scoring_memo.py)
    vr_result = {
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

    st.session_state["vr_dim_result"] = dim_result
    st.session_state["vr_vr_result"] = vr_result

# ── Guard: need results ──────────────────────────────────────────────────────

if "vr_vr_result" not in st.session_state:
    st.info("Select a company and click **Calculate V^R** to begin.")
    st.stop()

dim_result = st.session_state["vr_dim_result"]
vr_result = st.session_state["vr_vr_result"]

st.divider()

# =============================================================================
# 1. Company Info Card
# =============================================================================

st.subheader(f"Results for {selected_co['name']}")

meta = dim_result.get("metadata", {})
scoring_method = meta.get("scoring_method", "unknown")
signal_count = meta.get("signal_count", "N/A")

ic1, ic2, ic3, ic4 = st.columns(4)
ic1.metric("Ticker", selected_co["ticker"])
ic2.metric("Sector", sector)
#   ic3.metric("Industry", ind_name)
#ic4.metric("Signals / Method", f"{signal_count} / {scoring_method}")

st.divider()

# =============================================================================
# 2. Dimension Scores Table
# =============================================================================

st.subheader("Dimension Scores")

dim_scores = dim_result.get("dimension_scores", {})
audit = dim_result.get("audit_trail", {})
rubric_details = audit.get("rubric_details", {})
weights = _get_weights_for_sector(sector)

table_rows = []
for dim_key, label in DIMENSION_LABELS.items():
    score_data = dim_scores.get(dim_key, {})

    # Path A
    if isinstance(score_data, dict):
        path_a = score_data.get("score", 0)
    else:
        path_a = float(score_data) if score_data else 0

    # Path B from rubric
    rb = rubric_details.get(dim_key, {})
    path_b = rb.get("score", None) if isinstance(rb, dict) else None

    # Combined
    if path_b is not None:
        combined = round(path_a * 0.6 + path_b * 0.4, 1)
    else:
        combined = round(path_a, 1)

    w = weights.get(dim_key, DEFAULT_WEIGHTS.get(dim_key, 0))

    table_rows.append({
        "Dimension": label,
        "Path A (Quant)": f"{path_a:.1f}",
        "Path B (Qual)": f"{path_b:.1f}" if path_b is not None else "N/A",
        "Combined": f"{combined:.1f}",
        "Sector Weight": f"{w:.0%}",
    })

table_df = pd.DataFrame(table_rows)
st.dataframe(table_df, hide_index=True, use_container_width=True)

# =============================================================================
# 3. Dimension Bar Chart
# =============================================================================

chart_data = []
for dim_key, label in DIMENSION_LABELS.items():
    score_data = dim_scores.get(dim_key, {})
    if isinstance(score_data, dict):
        val = score_data.get("score", 0)
    else:
        val = float(score_data) if score_data else 0
    chart_data.append({"Dimension": label, "Score": val})

chart_df = pd.DataFrame(chart_data)


def _score_color(val):
    if val >= 70:
        return "#4caf50"
    elif val >= 50:
        return "#ff9800"
    elif val >= 30:
        return "#ff5722"
    return "#d32f2f"


chart_df["Color"] = chart_df["Score"].apply(_score_color)

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

# =============================================================================
# 4. V^R Calculation Breakdown
# =============================================================================

st.subheader("V^R Calculation Breakdown")

vr_score = vr_result.get("vr_score", 0)
vr_comp = vr_result.get("vr_components", {})

base_score = vr_comp.get("base_score", vr_result.get("weighted_mean", 0))
cv = vr_comp.get("cv", vr_comp.get("cv_penalty", 0))
cv_penalty = vr_comp.get("cv_penalty", 0)
cv_penalty_amount = vr_comp.get("cv_penalty_amount", 0)
tc = vr_comp.get("talent_concentration", 0)
talent_risk_adj = vr_comp.get("talent_risk_adj", 1.0)
tc_penalty_amount = vr_comp.get("tc_penalty_amount", 0)

res_left, res_right = st.columns([1, 1], gap="large")

with res_left:
    st.markdown("#### Step-by-Step")

    steps_df = pd.DataFrame([
        {
            "Step": "1. Weighted Mean (D_w)",
            "Value": f"{base_score:.2f}",
            "Detail": "Sector-weighted average of 7 dimension scores",
        },
        {
            "Step": "2. Coefficient of Variation (CV)",
            "Value": f"{cv:.4f}",
            "Detail": "Measures dimensional imbalance",
        },
        {
            "Step": "3. CV Penalty (1 - 0.25 * CV)",
            "Value": f"{cv_penalty:.4f}" if cv_penalty else f"{1 - 0.25 * cv:.4f}",
            "Detail": f"-{cv_penalty_amount:.1f} pts",
        },
        {
            "Step": "4. Talent Concentration (TC)",
            "Value": f"{tc:.4f}",
            "Detail": "Threshold = 0.25",
        },
        {
            "Step": "5. Talent Risk Adj",
            "Value": f"{talent_risk_adj:.4f}",
            "Detail": f"-{tc_penalty_amount:.1f} pts",
        },
        {
            "Step": "6. Final V^R",
            "Value": f"{vr_score:.2f}",
            "Detail": "D_w x CV_penalty x TalentRiskAdj",
        },
    ])
    st.dataframe(steps_df, hide_index=True, use_container_width=True)

    st.markdown("**Formula applied:**")
    st.code(
        f"V^R = {base_score:.2f} x {cv_penalty:.4f} x {talent_risk_adj:.4f}\n"
        f"    = {vr_score:.2f}",
        language=None,
    )

# =============================================================================
# 5. Score Visualization
# =============================================================================

with res_right:
    st.markdown("#### Score Visualization")

    st.markdown(f"**V^R Score: {vr_score:.2f} / 100**")
    st.progress(min(1.0, max(0.0, vr_score / 100.0)))
    st.markdown("")

    if vr_score >= 70:
        st.success(f"**Strong AI Readiness** ({vr_score:.1f}/100)")
        st.markdown(
            "This company demonstrates strong readiness across AI dimensions. "
            "Well-positioned for AI-driven value creation."
        )
    elif vr_score >= 50:
        st.info(f"**Moderate AI Readiness** ({vr_score:.1f}/100)")
        st.markdown(
            "Reasonable AI foundation with meaningful upside potential. "
            "Targeted investments in weaker dimensions could yield significant gains."
        )
    elif vr_score >= 30:
        st.warning(f"**Developing AI Readiness** ({vr_score:.1f}/100)")
        st.markdown(
            "Early-stage AI capabilities. Structural gaps exist across multiple dimensions "
            "that need to be addressed before AI-driven transformation."
        )
    else:
        st.error(f"**Low AI Readiness** ({vr_score:.1f}/100)")
        st.markdown(
            "Significant gaps across AI readiness dimensions. "
            "Foundational investments in data, talent, and governance needed."
        )

    st.markdown("---")

    # Penalty breakdown metrics
    st.markdown("**Penalty Breakdown**")
    p1, p2, p3 = st.columns(3)
    p1.metric("Base Score", f"{base_score:.1f}")
    p2.metric("CV Penalty", f"-{cv_penalty_amount:.1f} pts")
    p3.metric("TC Penalty", f"-{tc_penalty_amount:.1f} pts")

# =============================================================================
# 6. Summary Callout
# =============================================================================

st.divider()
st.info(f"""
**V^R Calculation Summary**

**Company:** {selected_co['name']} ({selected_co['ticker']})
**Sector:** {sector}  |  **Industry:** {ind_name}  |  **Signals:** {signal_count}  |  **Method:** {scoring_method}
**Formula:** V^R = {base_score:.2f} x (1 - 0.25 x {cv:.4f}) x {talent_risk_adj:.4f} = **{vr_score:.2f}**
**CV Penalty:** -{cv_penalty_amount:.1f} pts  |  **TC Penalty:** -{tc_penalty_amount:.1f} pts
""")
