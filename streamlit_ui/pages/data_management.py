import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from streamlit_ui.utils.api_client import APIClient

st.set_page_config(page_title="Data Management", page_icon="🗄️", layout="wide")

api = APIClient()

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🗄️ Data Management")
    st.caption("Manage portfolio companies and industry reference data.")
    st.divider()
    try:
        health = api.health_check()
        status = health.get("status", "offline")
        if status in ("healthy", "degraded"):
            st.success("✅ API Connected")
        else:
            st.error("❌ API Offline")
    except Exception:
        st.error("❌ API Offline")
    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# ── Page title ────────────────────────────────────────────────────────────────

st.title("🗄️ Data Management")
st.caption("Create, view, edit and delete companies and industries in the Snowflake database.")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_co, tab_ind = st.tabs(["🏢 Companies", "🏭 Industries"])

# =============================================================================
# COMPANIES TAB
# =============================================================================

with tab_co:
    with st.spinner("Loading..."):
        try:
            co_data = api.get_companies(page_size=100)
            companies = co_data.get("items", [])
            ind_data = api.get_industries(page_size=100)
            industries = ind_data.get("items", [])
            ind_map = {i["id"]: i["name"] for i in industries}
            ind_options = {i["id"]: i["name"] for i in industries}
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()

    col_table, col_form = st.columns([2, 1], gap="large")

    # ── Left: Companies list ──────────────────────────────────────────────────

    with col_table:
        st.subheader(f"Companies ({len(companies)} total)")

        search = st.text_input(
            "🔍 Search",
            placeholder="Filter by name or ticker...",
            key="co_search",
        )

        industry_names = ["All Industries"] + sorted(set(i["name"] for i in industries))
        industry_filter = st.selectbox(
            "Filter by Industry", options=industry_names, key="co_ind_filter"
        )

        # Client-side filtering
        filtered = companies
        if search:
            s = search.lower()
            filtered = [
                c for c in filtered
                if s in c["name"].lower() or s in c["ticker"].lower()
            ]
        if industry_filter != "All Industries":
            filtered = [
                c for c in filtered
                if ind_map.get(c["industry_id"]) == industry_filter
            ]

        # Build display DataFrame
        rows = []
        for c in filtered:
            rows.append({
                "Name": c["name"],
                "Ticker": c["ticker"],
                "Industry": ind_map.get(c["industry_id"], "Unknown"),
                "Created": str(c.get("created_at", ""))[:10],
            })

        df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=["Name", "Ticker", "Industry", "Created"]
            )
        )

        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No companies match the current filters.")

        st.caption(f"Showing {len(filtered)} of {len(companies)} companies")

    # ── Right: Action panel ───────────────────────────────────────────────────

    with col_form:
        action = st.radio(
            "",
            ["➕ Add Company", "✏️ Edit Company", "🗑️ Delete Company"],
            key="co_action",
            label_visibility="collapsed",
        )
        st.divider()

        # ── Add Company ───────────────────────────────────────────────────────
        if action == "➕ Add Company":
            with st.form("add_company_form"):
                st.subheader("Add New Company")
                name = st.text_input("Company Name *")
                ticker = st.text_input(
                    "Ticker Symbol *", help="Automatically uppercased"
                )
                ind_id = st.selectbox(
                    "Industry *",
                    options=list(ind_options.keys()),
                    format_func=lambda x: ind_options[x],
                )
                submitted = st.form_submit_button(
                    "Create Company", use_container_width=True, type="primary"
                )
                if submitted:
                    if not name.strip() or not ticker.strip():
                        st.error("Name and ticker are required.")
                    else:
                        result = api.create_company(
                            name.strip(), ticker.strip().upper(), ind_id, 0.0
                        )
                        if result:
                            st.success(
                                f"✅ Created {result.get('name')} ({result.get('ticker')})"
                            )
                            st.rerun()

        # ── Edit Company ──────────────────────────────────────────────────────
        elif action == "✏️ Edit Company":
            if not companies:
                st.info("No companies to edit.")
            else:
                selected_co = st.selectbox(
                    "Select company",
                    options=companies,
                    format_func=lambda c: f"{c['name']} ({c['ticker']})",
                    key="co_edit_select",
                )

                ind_keys = list(ind_options.keys())
                current_ind_id = selected_co.get("industry_id", "")
                ind_idx = (
                    ind_keys.index(current_ind_id)
                    if current_ind_id in ind_keys
                    else 0
                )

                with st.form("edit_company_form"):
                    st.subheader("Edit Company")
                    name = st.text_input(
                        "Company Name *", value=selected_co.get("name", "")
                    )
                    ticker = st.text_input(
                        "Ticker Symbol *",
                        value=selected_co.get("ticker", ""),
                        help="Automatically uppercased",
                    )
                    ind_id = st.selectbox(
                        "Industry *",
                        options=ind_keys,
                        format_func=lambda x: ind_options[x],
                        index=ind_idx,
                    )
                    submitted = st.form_submit_button(
                        "Save Changes", use_container_width=True, type="primary"
                    )
                    if submitted:
                        if not name.strip() or not ticker.strip():
                            st.error("Name and ticker are required.")
                        else:
                            result = api.update_company(
                                selected_co["id"],
                                name.strip(),
                                ticker.strip().upper(),
                                ind_id,
                                0.0,
                            )
                            if result:
                                st.success(
                                    f"✅ Updated {result.get('name')} ({result.get('ticker')})"
                                )
                                st.rerun()

        # ── Delete Company ────────────────────────────────────────────────────
        elif action == "🗑️ Delete Company":
            if not companies:
                st.info("No companies to delete.")
            else:
                selected_del_co = st.selectbox(
                    "Select company to delete",
                    options=companies,
                    format_func=lambda c: f"{c['name']} ({c['ticker']})",
                    key="co_del_select",
                )
                st.warning(
                    f"**{selected_del_co['name']}** ({selected_del_co['ticker']})  \n"
                    f"Industry: {ind_map.get(selected_del_co['industry_id'], 'Unknown')}"
                )

                delete_mode = st.radio(
                    "Delete type",
                    ["🟡 Soft Delete", "🔴 Hard Delete"],
                    key="co_del_mode",
                )

                if delete_mode == "🟡 Soft Delete":
                    st.info(
                        "ℹ️ Soft delete hides the company from all views but "
                        "preserves the record in Snowflake. Can be recovered by "
                        "setting is_deleted = FALSE directly in the database."
                    )
                else:
                    st.error(
                        "⛔ Hard delete permanently removes the row from Snowflake. "
                        "This cannot be undone and will also orphan any signals, "
                        "assessments, or documents linked to this company."
                    )

                confirmed = st.checkbox(
                    "I confirm I want to delete this company", key="co_del_confirm"
                )
                if st.button(
                    "Delete Company",
                    disabled=not confirmed,
                    type="primary",
                    use_container_width=True,
                ):
                    if delete_mode == "🟡 Soft Delete":
                        ok = api.delete_company(selected_del_co["id"])
                    else:
                        ok = api.hard_delete_company(selected_del_co["id"])

                    if ok:
                        mode_label = (
                            "soft-deleted (hidden, record preserved)"
                            if delete_mode == "🟡 Soft Delete"
                            else "permanently deleted from Snowflake"
                        )
                        st.success(
                            f"✅ {selected_del_co['name']} has been {mode_label}."
                        )
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete company.")

# =============================================================================
# INDUSTRIES TAB
# =============================================================================

with tab_ind:
    with st.spinner("Loading..."):
        try:
            ind_data = api.get_industries(page_size=100)
            industries = ind_data.get("items", [])
            co_data = api.get_companies(page_size=100)
            companies = co_data.get("items", [])
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()

    col_table, col_form = st.columns([2, 1], gap="large")

    # ── Left: Industries list ─────────────────────────────────────────────────

    with col_table:
        st.subheader(f"Industries ({len(industries)} total)")

        ind_search = st.text_input(
            "🔍 Search",
            placeholder="Filter by name or sector...",
            key="ind_search",
        )

        filtered_ind = industries
        if ind_search:
            s = ind_search.lower()
            filtered_ind = [
                i for i in filtered_ind
                if s in i["name"].lower() or s in i.get("sector", "").lower()
            ]

        # Build display DataFrame
        ind_rows = []
        for ind in filtered_ind:
            count = sum(1 for c in companies if c.get("industry_id") == ind["id"])
            ind_rows.append({
                "Name": ind["name"],
                "Sector": ind.get("sector", ""),
                "H^R Base": f"{float(ind.get('h_r_base', 50.0)):.1f}",
                "Companies Using": count,
                "Created": str(ind.get("created_at", ""))[:10],
            })

        ind_df = (
            pd.DataFrame(ind_rows)
            if ind_rows
            else pd.DataFrame(
                columns=["Name", "Sector", "H^R Base", "Companies Using", "Created"]
            )
        )

        def style_hr(val):
            v = float(val)
            if v >= 70:
                return "background-color: #d4edda; color: #155724"
            if v >= 50:
                return "background-color: #fff3cd; color: #856404"
            return "background-color: #f8d7da; color: #721c24"

        if not ind_df.empty:
            styled_ind = ind_df.style.applymap(style_hr, subset=["H^R Base"])
            st.dataframe(styled_ind, use_container_width=True, hide_index=True)
        else:
            st.info("No industries match the current search.")

        st.caption(f"Showing {len(filtered_ind)} of {len(industries)} industries")

    # ── Right: Action panel ───────────────────────────────────────────────────

    with col_form:
        action = st.radio(
            "",
            ["➕ Add Industry", "🗑️ Delete Industry"],
            key="ind_action",
            label_visibility="collapsed",
        )
        st.divider()

        SECTORS = [
            "Healthcare",
            "Financial",
            "Technology",
            "Energy",
            "Retail",
            "Professional Services",
            "Manufacturing",
            "Industrials",
            "Services",
        ]

        # ── Add Industry ──────────────────────────────────────────────────────
        if action == "➕ Add Industry":
            with st.form("add_industry_form"):
                st.subheader("Add New Industry")
                name = st.text_input(
                    "Industry Name *", placeholder="e.g. Enterprise Software"
                )
                sector = st.selectbox("Sector *", SECTORS)
                h_r_base = st.number_input(
                    "H^R Base Score *",
                    0.0,
                    100.0,
                    50.0,
                    0.5,
                    help=(
                        "Industry baseline AI readiness (0–100). "
                        "Used in H^R = base × (1 + 0.15 × PF)"
                    ),
                )
                st.info(f"""
**Preview**
- **Name:** {name or '—'}
- **Sector:** {sector}
- **H^R Base:** {h_r_base:.1f} / 100
- **HR range at PF ±1:** {h_r_base * 0.85:.1f} – {h_r_base * 1.15:.1f}
""")
                submitted = st.form_submit_button(
                    "Create Industry", use_container_width=True, type="primary"
                )
                if submitted:
                    if not name.strip():
                        st.error("Industry name is required.")
                    else:
                        result = api.create_industry(name.strip(), sector, h_r_base)
                        if result:
                            st.success(
                                f"✅ Created industry: {result.get('name')}"
                            )
                            st.rerun()

        # ── Delete Industry ───────────────────────────────────────────────────
        elif action == "🗑️ Delete Industry":
            if not industries:
                st.info("No industries to delete.")
            else:
                del_ind_options = {
                    i["id"]: f"{i['name']} — {i.get('sector', '')}"
                    for i in industries
                }
                del_ind_id = st.selectbox(
                    "Select industry to delete",
                    options=list(del_ind_options.keys()),
                    format_func=lambda x: del_ind_options[x],
                    key="ind_del_select",
                )
                selected_ind = next(
                    (i for i in industries if i["id"] == del_ind_id), None
                )

                if selected_ind:
                    users = [
                        c for c in companies
                        if c.get("industry_id") == del_ind_id
                    ]

                    if len(users) > 0:
                        names = ", ".join(c["name"] for c in users[:5])
                        st.error(
                            f"❌ Cannot delete — {len(users)} company/companies "
                            f"depend on this industry: {names}"
                        )
                    else:
                        st.warning(
                            f"**{selected_ind['name']}**  \n"
                            f"Sector: {selected_ind.get('sector', '—')}  \n"
                            f"H^R Base: {float(selected_ind.get('h_r_base', 50.0)):.1f}"
                        )
                        st.warning(
                            "⚠️ This will permanently delete the industry "
                            "from the database."
                        )
                        confirmed = st.checkbox(
                            "I confirm I want to delete this industry",
                            key="ind_del_confirm",
                        )
                        if st.button(
                            "Delete Industry",
                            disabled=not confirmed,
                            type="primary",
                            use_container_width=True,
                        ):
                            ok = api.delete_industry(del_ind_id)
                            if ok:
                                st.success(
                                    f"✅ Deleted industry: {selected_ind['name']}"
                                )
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete industry.")
