import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="H^R Calculator", page_icon="🏭", layout="wide")

api = APIClient()

# ── Constants (mirrored from backend classes, no DB imports needed) ───────────

DELTA = 0.15  # HRCalculator.DELTA

# mirrors HRCalculator.FALLBACK_HR_BASE
FALLBACK_HR_BASE = {
    "technology": 75.0,
    "financial_services": 65.0,
    "financial": 65.0,
    "healthcare": 55.0,
    "retail": 50.0,
    "business_services": 48.0,
    "professional_services": 48.0,
    "manufacturing": 45.0,
    "energy": 40.0,
    "industrials": 42.0,
    "services": 47.0,
}

# mirrors PositionFactorCalculator.SECTOR_AVG_VR (+ aliases for DB sector names)
SECTOR_AVG_VR = {
    "technology": 65.0,
    "financial_services": 55.0,
    "financial": 55.0,
    "healthcare": 52.0,
    "business_services": 50.0,
    "professional_services": 50.0,
    "retail": 48.0,
    "manufacturing": 45.0,
    "energy": 45.0,
    "industrials": 45.0,
    "services": 48.0,
}

# ── Pure-Python helpers (no Snowflake) ────────────────────────────────────────

def _sector_key(sector: str) -> str:
    """'Professional Services' → 'professional_services'"""
    return sector.lower().replace(" ", "_").replace("-", "_")


def get_sector_avg_vr(sector: str) -> float:
    return SECTOR_AVG_VR.get(_sector_key(sector), 50.0)


def get_fallback_hr_base(sector: str) -> float:
    return FALLBACK_HR_BASE.get(_sector_key(sector), 50.0)


def compute_pf(vr_score: float, sector: str, mcap_percentile: float) -> dict:
    """Pure-Python mirror of PositionFactorCalculator.calculate_position_factor()."""
    sector_avg = get_sector_avg_vr(sector)
    vr_component_raw = (vr_score - sector_avg) / 50.0
    vr_component = max(-1.0, min(1.0, vr_component_raw))
    mcap_component = (mcap_percentile - 0.5) * 2.0
    pf_raw = 0.6 * vr_component + 0.4 * mcap_component
    pf = max(-1.0, min(1.0, pf_raw))
    return {
        "sector_avg": sector_avg,
        "vr_component_raw": vr_component_raw,
        "vr_component": vr_component,
        "mcap_component": mcap_component,
        "pf_raw": pf_raw,
        "pf": pf,
        "vr_was_clamped": abs(vr_component_raw) > 1.0,
        "pf_was_clamped": abs(pf_raw) > 1.0,
    }


def compute_hr(hr_base: float, pf: float) -> dict:
    """Pure-Python mirror of HRCalculator.calculate() formula steps."""
    delta_pf = DELTA * pf
    adjustment = 1.0 + delta_pf
    hr_raw = hr_base * adjustment
    hr_final = max(0.0, min(100.0, hr_raw))
    return {
        "hr_base": hr_base,
        "pf": pf,
        "delta_pf": delta_pf,
        "adjustment": adjustment,
        "hr_raw": hr_raw,
        "hr_final": hr_final,
        "was_clamped": hr_raw != hr_final,
    }


def pf_label(pf: float) -> str:
    if pf > 0.3:
        return "🟢 Industry Leader"
    elif pf < -0.3:
        return "🔴 Industry Laggard"
    else:
        return "⚪ Average Position"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🏭 H^R Calculator")
    st.caption("Industry AI Readiness scoring with position adjustment.")
    st.divider()
    try:
        health = api.health_check()
        if health.get("status") in ("healthy", "degraded"):
            st.success("✅ API Connected")
        else:
            st.error("❌ API Offline")
    except Exception:
        st.error("❌ API Offline")
    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🏭 H^R Industry AI Readiness Calculator")
st.caption("Calculate industry-adjusted AI readiness scores for portfolio companies")
st.divider()

# ── Formula Reference ─────────────────────────────────────────────────────────

with st.expander("📐 Formula Reference", expanded=False):
    fx_c1, fx_c2, fx_c3 = st.columns(3)

    with fx_c1:
        st.markdown("#### Core Formula")
        st.latex(r"H^R = H^R_{base} \times (1 + 0.15 \times PF)")
        st.markdown("""
**Where:**
- **H^R_base** — industry baseline (from `industries` table)
- **δ = 0.15** — fixed position adjustment coefficient
- **PF ∈ [−1, +1]** — company position factor

**Range at extremes:**

| PF | Multiplier | Effect on base |
|---|---|---|
| +1.0 | × 1.15 | base × 1.15 |
|  0.0 | × 1.00 | unchanged |
| −1.0 | × 0.85 | base × 0.85 |
        """)

    with fx_c2:
        st.markdown("#### H^R Base by Sector (DB Fallback Values)")
        st.dataframe(
            pd.DataFrame([
                {"Sector": "Technology",       "H^R Base": 75.0},
                {"Sector": "Financial",        "H^R Base": 65.0},
                {"Sector": "Healthcare",       "H^R Base": 55.0},
                {"Sector": "Retail",           "H^R Base": 50.0},
                {"Sector": "Prof. Services",   "H^R Base": 48.0},
                {"Sector": "Manufacturing",    "H^R Base": 45.0},
                {"Sector": "Energy",           "H^R Base": 40.0},
            ]),
            hide_index=True,
            use_container_width=True,
        )

    with fx_c3:
        st.markdown("#### Position Factor Formula")
        st.latex(r"PF = 0.6 \times VR_{comp} + 0.4 \times MCap_{comp}")
        st.markdown("""
- **VR_comp** = (V^R − sector_avg) / 50 → clamped [−1, 1]
- **MCap_comp** = (percentile − 0.5) × 2
        """)
        st.dataframe(
            pd.DataFrame([
                {"Sector": "Technology",    "Avg V^R": 65.0},
                {"Sector": "Financial",     "Avg V^R": 55.0},
                {"Sector": "Healthcare",    "Avg V^R": 52.0},
                {"Sector": "Bus. Services", "Avg V^R": 50.0},
                {"Sector": "Retail",        "Avg V^R": 48.0},
                {"Sector": "Manufacturing", "Avg V^R": 45.0},
            ]),
            hide_index=True,
            use_container_width=True,
        )

st.divider()

# ── Load API data ─────────────────────────────────────────────────────────────

with st.spinner("Loading companies and industries..."):
    try:
        co_data  = api.get_companies(page_size=100)
        companies = co_data.get("items", [])
        ind_data  = api.get_industries(page_size=100)
        industries = ind_data.get("items", [])
    except Exception as e:
        st.error(f"❌ Failed to load API data: {e}")
        st.stop()

if not companies:
    st.warning("⚠️ No companies found. Add companies via the Data Management page first.")
    st.stop()

# Build industry lookup: id → {name, sector, h_r_base}
ind_lookup: dict = {
    ind["id"]: {
        "name":     ind.get("name", "Unknown"),
        "sector":   ind.get("sector", ""),
        "h_r_base": float(ind.get("h_r_base") or 0.0),
    }
    for ind in industries
}

# ── Section 2 + 3: Two-column layout ─────────────────────────────────────────

col_left, col_right = st.columns([2, 3], gap="large")

# =============================================================================
# LEFT COLUMN — Company Selection + Info Card
# =============================================================================

with col_left:
    st.subheader("1️⃣ Select Company")

    def _co_label(c: dict) -> str:
        sec = ind_lookup.get(c.get("industry_id", ""), {}).get("sector", "") or "—"
        return f"{c['ticker']} — {c['name']} ({sec})"

    selected_co = st.selectbox(
        "Company",
        options=companies,
        format_func=_co_label,
        key="hr_co_select",
        label_visibility="collapsed",
    )

    # Resolve all company-derived variables immediately
    ind_id   = selected_co.get("industry_id", "")
    ind_info = ind_lookup.get(ind_id, {})
    sector   = ind_info.get("sector") or "Unknown"
    ind_name = ind_info.get("name")   or "Unknown"
    hr_base_db = ind_info.get("h_r_base", 0.0)

    if hr_base_db and hr_base_db > 0:
        hr_base     = hr_base_db
        base_source = "Database"
    else:
        hr_base     = get_fallback_hr_base(sector)
        base_source = "Fallback"

    hr_range_lo = hr_base * 0.85
    hr_range_hi = hr_base * 1.15

    # ── Info card ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"##### {selected_co['name']}")

    ic_r1c1, ic_r1c2 = st.columns(2)
    with ic_r1c1:
        st.metric("Ticker",  selected_co["ticker"])
        st.metric("Sector",  sector)
    with ic_r1c2:
        st.metric("Industry", ind_name)
        src_icon = "📦" if base_source == "Database" else "⚙️"
        st.metric("Base Source", f"{src_icon} {base_source}")

    st.markdown("---")

    ic_r2c1, ic_r2c2 = st.columns(2)
    with ic_r2c1:
        st.metric(
            "H^R Base",
            f"{hr_base:.1f}",
            help="Read from industries table — not manually editable here",
        )
    with ic_r2c2:
        st.metric(
            "H^R Range",
            f"{hr_range_lo:.1f} – {hr_range_hi:.1f}",
            help="Achievable H^R as PF swings from −1 to +1",
        )

    if base_source == "Fallback":
        st.caption(
            f"⚙️ No h_r_base found in DB for sector '{sector}'. "
            f"Using hardcoded fallback constant: {hr_base:.1f}"
        )
    else:
        st.caption(f"📦 H^R base loaded from industries table: {ind_name} (ID: {ind_id[:8]}…)")

# =============================================================================
# RIGHT COLUMN — Position Factor Input
# =============================================================================

with col_right:
    st.subheader("2️⃣ Position Factor (PF)")

    tab_manual, tab_auto = st.tabs([
        "🎯 Manual PF",
        "🧮 Auto-Calculate PF from V^R + Market Cap",
    ])

    # ── Tab 1: Manual PF ──────────────────────────────────────────────────────
    with tab_manual:
        pf_manual = st.slider(
            "Position Factor (PF)",
            min_value=-1.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            key="hr_pf_manual",
        )
        st.caption(pf_label(pf_manual))

        st.markdown("---")
        st.markdown(
            "**Reference benchmarks:** &nbsp;"
            "NVDA = +0.9 &nbsp;|&nbsp; JPM = +0.5 &nbsp;|&nbsp; "
            "WMT = +0.3 &nbsp;|&nbsp; GE = 0.0 &nbsp;|&nbsp; DG = −0.3",
            unsafe_allow_html=True,
        )

    # ── Tab 2: Auto-calculate PF ──────────────────────────────────────────────
    with tab_auto:
        sector_avg_vr = get_sector_avg_vr(sector)
        st.info(
            f"**Sector:** {sector}  |  "
            f"**Sector Avg V^R:** {sector_avg_vr:.1f}  |  "
            f"VR_comp formula: `(V^R − {sector_avg_vr:.1f}) / 50`"
        )

        # Clear cached VR when company changes (same logic as V^R Calculator)
        company_id = selected_co["id"]
        if st.session_state.get("hr_vr_last_company_id") != company_id:
            for _k in ("hr_vr_input", "hr_vr_fetch_status"):
                st.session_state.pop(_k, None)
            st.session_state["hr_vr_last_company_id"] = company_id

        fb_col, fs_col = st.columns([1, 2])
        with fb_col:
            fetch_vr_clicked = st.button(
                "📡 Fetch V^R from API",
                key="hr_fetch_vr_btn",
                use_container_width=True,
                help="Auto-populate V^R using the scoring API — identical to the V^R Calculator page",
            )

        if fetch_vr_clicked:
            with st.spinner("Fetching V^R score..."):
                try:
                    org_air = api.get_org_air_score(company_id)
                    if org_air and "vr_score" in org_air:
                        st.session_state["hr_vr_input"] = float(org_air["vr_score"])
                        st.session_state["hr_vr_fetch_status"] = (
                            "success",
                            f"Fetched V^R: {org_air['vr_score']:.2f}",
                        )
                    else:
                        st.session_state["hr_vr_fetch_status"] = (
                            "warning",
                            "No V^R score returned. Enter manually below.",
                        )
                except Exception as e:
                    st.session_state["hr_vr_fetch_status"] = ("warning", f"API error: {e}")

        with fs_col:
            if "hr_vr_fetch_status" in st.session_state:
                _stype, _smsg = st.session_state["hr_vr_fetch_status"]
                if _stype == "success":
                    st.success(f"✅ {_smsg}")
                else:
                    st.warning(f"⚠️ {_smsg}")

        vr_input = st.number_input(
            "V^R Score",
            min_value=0.0,
            max_value=100.0,
            value=65.0,
            step=0.5,
            key="hr_vr_input",
            help="Venture Readiness score (0–100). Click '📡 Fetch V^R from API' to auto-populate via the scoring API.",
        )
        mcap_pct = st.slider(
            "Market Cap Percentile (0 = smallest in sector, 1 = largest)",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.01,
            key="hr_mcap_pct",
        )

        # Live computation — always runs, all tabs are executed by Streamlit
        pf_auto_result = compute_pf(vr_input, sector, mcap_pct)

        st.markdown("---")
        st.markdown("**Live Calculation Preview:**")

        pv_c1, pv_c2 = st.columns(2)
        with pv_c1:
            vr_clamp_note = " *(clamped to ±1)*" if pf_auto_result["vr_was_clamped"] else ""
            st.markdown(f"""
**VR_component:**
`({vr_input:.1f} − {pf_auto_result['sector_avg']:.1f}) / 50`
= `{pf_auto_result['vr_component_raw']:.4f}`{vr_clamp_note}
→ **{pf_auto_result['vr_component']:.4f}**

**MCap_component:**
`({mcap_pct:.2f} − 0.5) × 2`
= **{pf_auto_result['mcap_component']:.4f}**
""")
        with pv_c2:
            pf_clamp_note = " *(clamped to ±1)*" if pf_auto_result["pf_was_clamped"] else ""
            st.markdown(f"""
**PF = 0.6 × VR_comp + 0.4 × MCap_comp:**
`0.6 × {pf_auto_result['vr_component']:.4f}`
`+ 0.4 × {pf_auto_result['mcap_component']:.4f}`
= `{pf_auto_result['pf_raw']:.4f}`{pf_clamp_note}
""")
            st.metric("Auto PF Result", f"{pf_auto_result['pf']:+.4f}")
            st.caption(pf_label(pf_auto_result["pf"]))

# =============================================================================
# PF SOURCE SELECTOR + CALCULATE BUTTON
# =============================================================================

st.divider()

pf_source = st.radio(
    "Use Position Factor from:",
    options=["🎯 Manual PF", "🧮 Auto-Calculated PF"],
    horizontal=True,
    key="hr_pf_source",
)

if pf_source == "🎯 Manual PF":
    active_pf = float(st.session_state.get("hr_pf_manual", 0.0))
else:
    active_pf = float(pf_auto_result["pf"])

st.markdown(f"**Active PF: `{active_pf:+.4f}`** — {pf_label(active_pf)}")

st.divider()

calc_clicked = st.button(
    "🧮 Calculate H^R",
    type="primary",
    use_container_width=True,
    key="hr_calc_btn",
)

# =============================================================================
# RESULTS
# =============================================================================

if calc_clicked:
    result = compute_hr(hr_base, active_pf)
    score  = result["hr_final"]

    st.divider()
    st.subheader("📊 H^R Calculation Results")

    # ── Top metrics row ───────────────────────────────────────────────────────
    rm1, rm2, rm3, rm4 = st.columns(4)
    with rm1:
        st.metric(
            "H^R Base",
            f"{result['hr_base']:.2f}",
            help=f"From {base_source} — {ind_name}",
        )
    with rm2:
        st.metric(
            "Position Factor",
            f"{result['pf']:+.4f}",
            help=pf_label(result["pf"]),
        )
    with rm3:
        adj_pct = (result["adjustment"] - 1.0) * 100
        st.metric(
            "Adjustment (1 + δ·PF)",
            f"{result['adjustment']:.4f}",
            delta=f"{adj_pct:+.1f}%",
        )
    with rm4:
        delta_vs_base = score - result["hr_base"]
        st.metric(
            "H^R Score",
            f"{score:.2f}",
            delta=f"{delta_vs_base:+.2f} vs base",
        )
        if result["was_clamped"]:
            st.caption("⚠️ Raw value was clamped to [0, 100]")

    st.divider()

    # ── Step breakdown + visualization ────────────────────────────────────────
    res_left, res_right = st.columns([1, 1], gap="large")

    with res_left:
        st.markdown("#### 📋 Step-by-Step Breakdown")
        steps_df = pd.DataFrame([
            {
                "Step": "1. H^R Base",
                "Value": f"{result['hr_base']:.4f}",
                "Detail": f"Source: {base_source}",
            },
            {
                "Step": "2. Position Factor (PF)",
                "Value": f"{result['pf']:+.4f}",
                "Detail": pf_label(result["pf"]),
            },
            {
                "Step": "3.  δ × PF",
                "Value": f"{result['delta_pf']:.4f}",
                "Detail": f"0.15 × {result['pf']:+.4f}",
            },
            {
                "Step": "4.  Adjustment = 1 + δ·PF",
                "Value": f"{result['adjustment']:.4f}",
                "Detail": f"1 + {result['delta_pf']:.4f}",
            },
            {
                "Step": "5.  H^R Raw = Base × Adj",
                "Value": f"{result['hr_raw']:.4f}",
                "Detail": f"{result['hr_base']:.4f} × {result['adjustment']:.4f}",
            },
            {
                "Step": "6.  H^R Final (clamped [0,100])",
                "Value": f"{score:.2f}",
                "Detail": "✅ Final score",
            },
        ])
        st.dataframe(steps_df, hide_index=True, use_container_width=True)

        st.markdown("**Formula applied:**")
        st.code(
            f"H^R = {result['hr_base']:.2f} × (1 + 0.15 × {result['pf']:+.4f})\n"
            f"    = {result['hr_base']:.2f} × {result['adjustment']:.4f}\n"
            f"    = {result['hr_final']:.2f}",
            language=None,
        )

    with res_right:
        st.markdown("#### 📈 Score Visualization")

        # Gauge bar — position within 0–100
        st.markdown(f"**H^R Score: {score:.2f} / 100**")
        st.progress(score / 100.0)
        st.markdown("")

        # Colour-coded interpretation band
        if score >= 70:
            st.success(f"✅ **Strong Industry AI Readiness** ({score:.1f}/100)")
            st.markdown(
                "The sector is a strong enabler of AI adoption. "
                "This company's position amplifies the baseline advantage."
            )
        elif score >= 55:
            st.info(f"ℹ️ **Moderate Industry AI Readiness** ({score:.1f}/100)")
            st.markdown(
                "Reasonable sector momentum with meaningful upside potential "
                "for AI initiatives."
            )
        elif score >= 40:
            st.warning(f"⚠️ **Developing Industry AI Readiness** ({score:.1f}/100)")
            st.markdown(
                "Early-stage AI adoption in this sector. "
                "Structural headwinds may slow transformation timelines."
            )
        else:
            st.error(f"❌ **Low Industry AI Readiness** ({score:.1f}/100)")
            st.markdown(
                "Significant structural barriers to AI adoption at the sector level."
            )

        st.markdown("---")

        # Achievable range bar
        st.markdown(f"**Achievable range for {sector} (PF from −1 to +1):**")
        rng_c1, rng_c2, rng_c3 = st.columns(3)
        with rng_c1:
            st.metric("Min (PF=−1)", f"{hr_range_lo:.1f}")
        with rng_c2:
            st.metric("Base (PF=0)", f"{hr_base:.1f}", help="Unweighted sector baseline")
        with rng_c3:
            st.metric("Max (PF=+1)", f"{hr_range_hi:.1f}")

        range_span = hr_range_hi - hr_range_lo
        position_in_range = (score - hr_range_lo) / range_span if range_span > 0 else 0.5
        st.progress(max(0.0, min(1.0, position_in_range)))
        st.caption(
            f"Score {score:.2f} sits at the "
            f"**{position_in_range * 100:.0f}th percentile** of the "
            f"achievable [{hr_range_lo:.1f}, {hr_range_hi:.1f}] range for {sector}."
        )

    # ── Summary callout ───────────────────────────────────────────────────────
    st.divider()
    st.info(f"""
**Calculation Summary**

**Company:** {selected_co['name']} ({selected_co['ticker']})
**Sector:** {sector}  |  **Industry:** {ind_name}
**Formula:** H^R = {result['hr_base']:.2f} × (1 + 0.15 × {result['pf']:+.4f}) = **{score:.2f}**
**PF source:** {pf_source}  |  **H^R base source:** {base_source}
    """)
