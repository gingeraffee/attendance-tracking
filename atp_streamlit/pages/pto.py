"""PTO Usage Analytics page."""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import atp_core.db as db
from atp_core import repo, services
from atp_core.rules import REASON_OPTIONS

from atp_streamlit.constants import (
    BUILDINGS,
    DASHBOARD_CACHE_TTL_SECONDS,
    EMPLOYEE_CACHE_TTL_SECONDS,
    EXPORT_LABELS,
    LEDGER_HISTORY_DEFAULT_LIMIT,
    LEDGER_HISTORY_FULL_LIMIT,
)
from atp_streamlit.shared.db import (
    _db_cache_key,
    _fetchall_cached,
    _get_cached_conn,
    _load_employees_cached,
    clear_read_caches,
    exec_sql,
    fetchall,
    first_value,
    get_conn,
    is_pg,
    load_employees,
    _apply_bulk_employee_override,
    _get_history_point_total,
    _normalize_bulk_override_columns,
    _parse_bulk_override_employee_id,
    _parse_bulk_override_point_total,
    _parse_bulk_override_date,
)
from atp_streamlit.shared.formatting import (
    days_badge,
    days_until,
    divider,
    fmt_date,
    info_box,
    page_heading,
    pt_badge,
    section_header,
    section_label,
    to_csv,
    warn_box,
)
from atp_streamlit.shared.hud import render_hr_live_monitor, render_tech_hud



def _pto_metric(label: str, value: str, sub: str = "") -> None:
    sub_html = (
        f"<div style='font-size:.75rem;color:#6b8cba;margin-top:.2rem'>{_html_inline(sub)}</div>"
        if sub
        else ""
    )
    st.markdown(
        f"<div style='background:#0d1b2e;border:1px solid #1a3a5c;border-radius:10px;"
        f"padding:1rem 1.25rem;text-align:center'>"
        f"<div style='font-size:.78rem;color:#4a7fa5;text-transform:uppercase;letter-spacing:.08em'>{_html_inline(label)}</div>"
        f"<div style='font-size:1.8rem;font-weight:700;color:#e8f4fd;line-height:1.2;margin-top:.3rem'>{_html_inline(value)}</div>"
        f"{sub_html}</div>",
        unsafe_allow_html=True,
    )


def _weekday_date_range(start_val, end_val):
    """Inclusive weekday-only date range (Mon-Fri) for a PTO interval."""
    if pd.isna(start_val) or pd.isna(end_val):
        return []
    start_ts = pd.Timestamp(start_val).normalize()
    end_ts = pd.Timestamp(end_val).normalize()
    if end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts
    return pd.bdate_range(start=start_ts, end=end_ts)


def pto_page(conn, building: str) -> None:
    page_heading("PTO Usage Analytics", "Upload a CSV export to analyze PTO patterns by type, building, and employee.")

    # ── Active employee roster from DB (active_only=True by default) ────────
    active_db = load_employees(conn, building="All")
    active_ids: set[int] = {int(e["employee_id"]) for e in active_db}
    active_names: set[str] = {
        f"{e['last_name'].strip().lower()}, {e['first_name'].strip().lower()}"
        for e in active_db
    }
    # For utilization denominator: active headcount scoped to the building filter
    if building != "All":
        active_count_in_scope = sum(1 for e in active_db if (e.get("location") or "") == building)
    else:
        active_count_in_scope = len(active_db)

    # ── Load persisted PTO data from DB into session state if not already loaded ──
    def _set_session_pto_df(rows: list[dict]) -> bool:
        if not rows:
            return False
        _df = pd.DataFrame([dict(r) for r in rows])
        _df["start_date"] = pd.to_datetime(_df["start_date"], errors="coerce")
        _df["end_date"] = pd.to_datetime(_df["end_date"], errors="coerce")
        _df["hours"] = pd.to_numeric(_df["hours"], errors="coerce").fillna(0)
        _df["building"] = _df["building"].astype(str).str.strip()
        _df["pto_type"] = _df["pto_type"].astype(str).str.strip()
        _df["employee"] = _df["last_name"].str.strip() + ", " + _df["first_name"].str.strip()
        _df["days"] = (_df["hours"] / 8).round(2)
        st.session_state["pto_df"] = _df
        return True

    if "pto_df" not in st.session_state:
        try:
            _set_session_pto_df(repo.load_pto_data(conn))
        except Exception:
            pass  # No persisted data or schema not yet migrated

    # ── CSV upload ──────────────────────────────────────────────────────────
    with st.expander("Upload PTO Data", expanded="pto_df" not in st.session_state):
        st.markdown(
            "Upload a completed template to upload employee PTO data and see trends and analytics."
        )
        col_up, col_dl = st.columns([3, 1])
        with col_up:
            uploaded = st.file_uploader("Choose CSV file", type="csv", label_visibility="collapsed")
        with col_dl:
            st.download_button(
                "Download template",
                data=_PTO_SAMPLE_CSV,
                file_name="pto_template.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if uploaded is not None:
            try:
                raw = pd.read_csv(uploaded, encoding="utf-8-sig")
                raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]
                cols = set(raw.columns)

                def _normalize_and_filter(df: pd.DataFrame) -> pd.DataFrame:
                    """Shared cleanup + DB active-employee filter applied after parsing."""
                    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
                    df["building"] = df["building"].astype(str).str.strip()
                    df["pto_type"] = df["pto_type"].astype(str).str.strip()
                    df["employee"] = df["last_name"].str.strip() + ", " + df["first_name"].str.strip()
                    df["days"] = (df["hours"] / 8).round(2)

                    # Build name→id lookup from DB for reliable export
                    _name_to_id: dict = {
                        f"{e['last_name'].strip().lower()}, {e['first_name'].strip().lower()}": int(e["employee_id"])
                        for e in active_db
                    }

                    # Match against active DB employees
                    def _is_active(row):
                        if "employee_id" in df.columns:
                            try:
                                if int(row["employee_id"]) in active_ids:
                                    return True
                            except (ValueError, TypeError):
                                pass
                        name_key = f"{str(row['last_name']).strip().lower()}, {str(row['first_name']).strip().lower()}"
                        return name_key in active_names

                    mask = df.apply(_is_active, axis=1)
                    excluded = (~mask).sum()
                    if excluded:
                        removed_names = sorted(df.loc[~mask, "employee"].unique())
                        st.warning(
                            f"{excluded} row(s) excluded — employee(s) not found in the active database: "
                            + ", ".join(removed_names)
                        )
                    df = df[mask].copy()

                    # Always resolve a canonical employee_id from the DB (covers CSVs without it)
                    def _resolve_id(row):
                        name_key = f"{str(row['last_name']).strip().lower()}, {str(row['first_name']).strip().lower()}"
                        if name_key in _name_to_id:
                            return _name_to_id[name_key]
                        try:
                            return int(row["employee_id"])
                        except (KeyError, ValueError, TypeError):
                            return None

                    df["employee_id"] = df.apply(_resolve_id, axis=1)
                    return df

                # Detect format: range (start_date/end_date) or legacy (date)
                if "start_date" in cols and "end_date" in cols:
                    required = {"last_name", "first_name", "building", "pto_type", "start_date", "end_date", "hours"}
                    missing = required - cols
                    if missing:
                        st.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")
                    else:
                        raw["start_date"] = pd.to_datetime(raw["start_date"], errors="coerce")
                        raw["end_date"] = pd.to_datetime(raw["end_date"], errors="coerce")
                        raw = raw.dropna(subset=["start_date", "end_date"])
                        raw = _normalize_and_filter(raw)
                        try:
                            with db.tx(conn):
                                stats = repo.save_pto_data(conn, raw.to_dict("records"))
                            _set_session_pto_df(repo.load_pto_data(conn))
                            st.session_state.pop("pto_type_toggles", None)
                            st.success(
                                f"Imported {stats['inserted']:,} new PTO record(s), skipped {stats['duplicate']:,} exact duplicate(s). "
                                f"Total stored: {stats['total']:,}."
                            )
                        except Exception as _save_err:
                            st.warning(f"PTO data parsed but could not be saved to database: {_save_err}")
                elif "date" in cols:
                    # Legacy single-day format — convert to range format
                    required = {"last_name", "first_name", "building", "pto_type", "date", "hours"}
                    missing = required - cols
                    if missing:
                        st.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")
                    else:
                        raw["start_date"] = pd.to_datetime(raw["date"], errors="coerce")
                        raw["end_date"] = raw["start_date"]
                        raw = raw.dropna(subset=["start_date"])
                        raw = _normalize_and_filter(raw)
                        try:
                            with db.tx(conn):
                                stats = repo.save_pto_data(conn, raw.to_dict("records"))
                            _set_session_pto_df(repo.load_pto_data(conn))
                            st.session_state.pop("pto_type_toggles", None)
                            st.success(
                                f"Imported {stats['inserted']:,} new PTO record(s), skipped {stats['duplicate']:,} exact duplicate(s). "
                                f"Total stored: {stats['total']:,} (legacy format upload)."
                            )
                        except Exception as _save_err:
                            st.warning(f"PTO data parsed but could not be saved to database: {_save_err}")
                else:
                    st.error("CSV must contain either `start_date`/`end_date` columns or a `date` column.")
            except Exception as exc:
                st.error(f"Could not parse CSV: {exc}")

    if "pto_df" not in st.session_state:
        st.info("Upload a PTO CSV above to begin analysis.")
        return

    df_all: pd.DataFrame = st.session_state["pto_df"].copy()

    # ── 30-day PTO utilization for the At a Glance bar ───────────────────────
    _now = date.today()
    _since_30 = pd.Timestamp(_now - timedelta(days=30))
    _df_30 = df_all[
        (df_all["start_date"] >= _since_30) | (df_all["end_date"] >= _since_30)
    ]
    if building != "All":
        _scope_count = sum(1 for e in active_db if (e.get("location") or e.get("Location") or "") == building)
        _df_30 = _df_30[_df_30["building"] == building] if "building" in _df_30.columns else _df_30
    else:
        _scope_count = len(active_db)
    _emps_30 = _df_30["employee"].nunique() if not _df_30.empty else 0
    _util_30 = (_emps_30 / max(_scope_count, 1)) * 100.0

    render_hr_live_monitor(
        points_24h=0,
        points_7d=0,
        rolloffs_due_7d=0,
        perfect_due_7d=0,
        label="At a glance — PTO (Last 30 Days)",
        pto_utilization_pct=_util_30,
    )

    # ── Filters ─────────────────────────────────────────────────────────────
    import re as _re
    divider()
    section_label("Filters")
    fc1, fc2, fc3 = st.columns(3)

    date_min = df_all["start_date"].min().date()
    date_max = df_all["end_date"].max().date()
    with fc1:
        date_start = st.date_input("From", value=date_min, min_value=date_min, max_value=date_max, key="pto_from")
    with fc2:
        date_end = st.date_input("To", value=date_max, min_value=date_min, max_value=date_max, key="pto_to")

    all_buildings = sorted(df_all["building"].dropna().unique())
    bldg_opts = ["All"] + all_buildings
    default_bldg = building if building in all_buildings else "All"
    with fc3:
        sel_building = st.selectbox("Building", bldg_opts, index=bldg_opts.index(default_bldg), key="pto_bldg")

    all_types = sorted(df_all["pto_type"].dropna().unique())

    # ── PTO type toggle chips ────────────────────────────────────────────────
    def _tkey(t: str) -> str:
        return "pto_toggle_" + _re.sub(r"[^a-z0-9]", "_", t.lower())

    # Reset toggle state if the type list has changed (new CSV loaded)
    if set(st.session_state.get("pto_type_toggles", {}).keys()) != set(all_types):
        st.session_state["pto_type_toggles"] = {t: True for t in all_types}
    toggles: dict = st.session_state["pto_type_toggles"]

    active_sel   = [f".st-key-{_tkey(t)} button" for t in all_types if     toggles.get(t, True)]
    inactive_sel = [f".st-key-{_tkey(t)} button" for t in all_types if not toggles.get(t, True)]

    # Inject pill CSS globally (applies in sidebar too)
    st.markdown(
        f"""<style>
        div[class*="st-key-pto_toggle_"] button {{
            padding: 0.12rem 0.5rem !important;
            font-size: 0.6rem !important;
            border-radius: 999px !important;
            font-family: 'SF Mono','Fira Code',monospace !important;
            letter-spacing: 0.04em !important;
            text-transform: uppercase !important;
            min-height: 26px !important;
            line-height: 1.15 !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }}
        {(', '.join(active_sel) or '.pto-na') + ' { background: rgba(0,212,255,.1) !important; border: 1px solid rgba(0,212,255,.7) !important; color: #00d4ff !important; box-shadow: 0 0 10px rgba(0,212,255,.2), inset 0 0 6px rgba(0,212,255,.05) !important; }'}
        {(', '.join(inactive_sel) or '.pto-na') + ' { background: rgba(6,13,31,.6) !important; border: 1px solid #1a3050 !important; color: #2d4a6a !important; box-shadow: none !important; }'}
        </style>""",
        unsafe_allow_html=True,
    )

    # Render type filter pills in the sidebar
    with st.sidebar:
        st.markdown("<span class='sidebar-nav-label'>PTO Type Filter</span>", unsafe_allow_html=True)
        for _pt in all_types:
            if st.button(_pt, key=_tkey(_pt), use_container_width=True):
                new_state = not toggles.get(_pt, True)
                st.session_state["pto_type_toggles"][_pt] = new_state
                st.toast(f"{_pt}: {'shown' if new_state else 'hidden'}")
                st.rerun()

    sel_types = [t for t in all_types if st.session_state["pto_type_toggles"].get(t, True)]

    # Apply filters — include any PTO event that overlaps the selected date range
    df = df_all[
        (df_all["start_date"].dt.date <= date_end)
        & (df_all["end_date"].dt.date >= date_start)
    ]
    if sel_building != "All":
        df = df[df["building"] == sel_building]
    if sel_types:
        df = df[df["pto_type"].isin(sel_types)]

    if df.empty:
        info_box("No PTO records match the current filters.")
        return

    # ── KPI tiles ───────────────────────────────────────────────────────────
    divider()
    section_header("Summary")
    k1, k2, k3, k4 = st.columns(4)
    total_hours = df["hours"].sum()
    # Count distinct weekday dates (Mon-Fri) where ANY employee had PTO.
    # Expand every record's start_date..end_date into business days,
    # union across all employees, then count unique dates.
    _pto_date_set: set = set()
    for _sd, _ed in zip(df["start_date"], df["end_date"]):
        for _d in _weekday_date_range(_sd, _ed):
            _pto_date_set.add(pd.Timestamp(_d).normalize())
    total_dates_impacted = len(_pto_date_set)
    unique_emps = df["employee"].nunique()
    # Denominator is active DB headcount for the selected building — not the CSV
    denom = active_count_in_scope if sel_building == building else (
        sum(1 for e in active_db if (e.get("location") or "") == sel_building)
        if sel_building != "All" else len(active_db)
    )
    utilization_pct = (unique_emps / denom * 100) if denom else 0
    top_type = df.groupby("pto_type")["hours"].sum().idxmax() if not df.empty else "—"
    avg_hours = total_hours / unique_emps if unique_emps else 0

    with k1:
        _pto_metric("Days Impacted", f"{total_dates_impacted:,}", f"{total_hours:,.0f} total hours")
    with k2:
        _pto_metric("Employees Used PTO", str(unique_emps), f"{utilization_pct:.0f}% utilization")
    with k3:
        _pto_metric("Top PTO Type", top_type)
    with k4:
        _pto_metric("Avg Days / Employee", f"{avg_hours / 8:.1f}", f"{avg_hours:.0f} hrs avg")

    # ── Donut chart + Monthly trend ─────────────────────────────────────────
    divider()
    chart_col, trend_col = st.columns(2)

    type_totals = df.groupby("pto_type")["hours"].sum().sort_values(ascending=False)
    type_colors = {t: _PTO_TYPE_COLORS.get(t, _PTO_PALETTE[i % len(_PTO_PALETTE)]) for i, t in enumerate(type_totals.index)}

    # Top-5 + "Other" for the donut
    _top5 = type_totals.head(5)
    _other_sum = type_totals.iloc[5:].sum()
    if _other_sum > 0:
        import pandas as _pd
        donut_totals = _pd.concat([_top5, _pd.Series({"Other": _other_sum})])
        _top5_types = set(_top5.index)
    else:
        donut_totals = _top5
        _top5_types = set(_top5.index)
    donut_colors = [type_colors.get(t, "#4a5568") for t in donut_totals.index]

    with chart_col:
        section_header("PTO by Type")
        donut_fig = go.Figure(go.Pie(
            labels=donut_totals.index.tolist(),
            values=donut_totals.values.tolist(),
            hole=0.52,
            marker=dict(colors=donut_colors, line=dict(color="#060d1f", width=2)),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:.0f} hrs (%{percent})<extra></extra>",
        ))
        donut_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            # Required: makes single clicks on pie slices fire selection events
            clickmode="event+select",
        )
        donut_event = st.plotly_chart(
            donut_fig,
            use_container_width=True,
            on_select="rerun",
            key="pto_donut",
        )

    with trend_col:
        section_header("Monthly PTO Trend (hours)")
        df_trend = df.copy()
        df_trend["month"] = df_trend["start_date"].dt.to_period("M").dt.to_timestamp()
        monthly = df_trend.groupby(["month", "pto_type"])["hours"].sum().reset_index()
        trend_fig = go.Figure()
        for pto_type in monthly["pto_type"].unique():
            sub = monthly[monthly["pto_type"] == pto_type]
            trend_fig.add_trace(go.Scatter(
                x=sub["month"], y=sub["hours"], name=pto_type, mode="lines+markers",
                line=dict(color=type_colors.get(pto_type, "#00d4ff"), width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{pto_type}</b><br>%{{x|%b %Y}}: %{{y:.0f}} hrs<extra></extra>",
            ))
        trend_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#4a7fa5")),
            margin=dict(t=10, b=10, l=10, r=10),
            hovermode="x unified",
        )
        st.plotly_chart(trend_fig, use_container_width=True, key="pto_trend")

    # ── Donut drill-down ────────────────────────────────────────────────────
    selected_points = donut_event.selection.get("points", []) if donut_event.selection else []
    if selected_points:
        sel_type = selected_points[0].get("label")
        if sel_type:
            divider()
            section_label(f"Employees — {sel_type}")
            if sel_type == "Other":
                drill_src = df[~df["pto_type"].isin(_top5_types)].copy()
            else:
                drill_src = df[df["pto_type"] == sel_type].copy()

            # Aggregate per employee + PTO type:
            #   Hours Used   = sum of all hours for that employee+type
            #   Days Impacted = unique weekdays touched by PTO ranges (Mon-Fri only)
            hours_agg = (
                drill_src.groupby(["employee", "pto_type", "building"])["hours"]
                .sum()
                .reset_index(name="hours_used")
            )
            days_src = drill_src[["employee", "pto_type", "building", "start_date", "end_date"]].copy()
            days_src["impact_date"] = days_src.apply(
                lambda r: _weekday_date_range(r["start_date"], r["end_date"]),
                axis=1,
            )
            days_src = days_src.explode("impact_date")
            days_agg = (
                days_src.groupby(["employee", "pto_type", "building"])["impact_date"]
                .nunique()
                .reset_index(name="days_impacted")
            )

            drill = (
                hours_agg.merge(days_agg, on=["employee", "pto_type", "building"], how="left")
                .fillna({"days_impacted": 0})
                .sort_values("hours_used", ascending=False)
                .rename(columns={
                    "employee":      "Employee",
                    "pto_type":      "PTO Type",
                    "building":      "Building",
                    "hours_used":    "Hours Used",
                    "days_impacted": "Days Impacted",
                })
            )
            drill["Hours Used"] = drill["Hours Used"].round(1)
            drill["Days Impacted"] = drill["Days Impacted"].astype(int)

            col_order = ["Employee", "PTO Type", "Hours Used", "Days Impacted", "Building"]
            st.dataframe(drill[col_order], use_container_width=True, hide_index=True)

    # ── Building comparison ─────────────────────────────────────────────────
    divider()
    bc1, bc2 = st.columns(2)

    with bc1:
        section_header("PTO Hours by Location")
        bldg_totals = df.groupby("building")["hours"].sum().sort_values(ascending=False).reset_index()
        bar_fig = go.Figure(go.Bar(
            x=bldg_totals["building"],
            y=bldg_totals["hours"],
            marker=dict(color=_PTO_PALETTE[:len(bldg_totals)], line=dict(color="#060d1f", width=1)),
            hovertemplate="<b>%{x}</b>: %{y:.0f} hrs<extra></extra>",
            text=(bldg_totals["hours"] / 8).round(1).astype(str) + "d",
            textposition="outside",
        ))
        bar_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(bar_fig, use_container_width=True, key="pto_bldg_bar")

    with bc2:
        section_header("Day of the Week PTO Trends")
        dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        df_dow = df.copy()
        df_dow["dow"] = df_dow["start_date"].dt.dayofweek
        df_dow["dow_label"] = df_dow["dow"].map(dow_map)
        dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        _DOW_FOCUS = {"Personal", "Vacation", "Absence"}
        _DOW_COLORS = {"Vacation": "#00d4ff", "Personal": "#7b61ff", "Absence": "#ff6b6b", "Other": "#6b7280"}
        df_dow_filtered = df_dow[df_dow["dow_label"].isin(dow_order)].copy()
        df_dow_filtered["dow_category"] = df_dow_filtered["pto_type"].apply(
            lambda t: t if t in _DOW_FOCUS else "Other"
        )
        dow_pivot = (
            df_dow_filtered
            .groupby(["dow_label", "dow_category"])["hours"]
            .sum()
            .reset_index()
        )
        dow_cat_order = ["Vacation", "Personal", "Absence", "Other"]
        dow_cat_order = [c for c in dow_cat_order if c in dow_pivot["dow_category"].unique()]
        dow_traces = []
        for pt in dow_cat_order:
            subset = (
                dow_pivot[dow_pivot["dow_category"] == pt]
                .set_index("dow_label")
                .reindex(dow_order)["hours"]
                .fillna(0)
            )
            dow_traces.append(go.Bar(
                name=pt,
                x=dow_order,
                y=subset.values,
                marker=dict(color=_DOW_COLORS.get(pt, "#7b61ff"), line=dict(color="#060d1f", width=1)),
                hovertemplate=f"<b>%{{x}}</b> — {pt}: %{{y:.0f}} hrs<extra></extra>",
            ))
        dow_fig = go.Figure(data=dow_traces)
        dow_fig.update_layout(
            barmode="stack",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color="#4a7fa5")),
            margin=dict(t=30, b=10, l=10, r=10),
        )
        st.plotly_chart(dow_fig, use_container_width=True, key="pto_dow_bar")

    # ── Top PTO users ───────────────────────────────────────────────────────
    divider()
    tu1, tu2 = st.columns([3, 2])

    with tu1:
        section_header("Top PTO Users")
        top_users = (
            df.groupby(["employee", "building"])["hours"]
            .sum()
            .reset_index()
            .sort_values("hours", ascending=False)
            .head(15)
        )
        top_users["Days"] = (top_users["hours"] / 8).round(1)
        top_users = top_users.rename(columns={"employee": "Employee", "building": "Building", "hours": "Hours"})
        top_users["Hours"] = top_users["Hours"].round(1)
        st.dataframe(top_users[["Employee", "Building", "Days", "Hours"]], use_container_width=True, hide_index=True)

    with tu2:
        section_header("Zero PTO — No Usage Recorded")
        emps_with_pto = set(df["employee"].unique())
        # Use the DB roster as the reference — not the CSV
        scoped_active = [
            e for e in active_db
            if sel_building == "All" or (e.get("location") or "") == sel_building
        ]
        all_active_names = {
            f"{e['last_name'].strip()}, {e['first_name'].strip()}"
            for e in scoped_active
        }
        no_pto = sorted(all_active_names - emps_with_pto)
        if no_pto:
            no_pto_df = pd.DataFrame({"Employee": no_pto})
            st.dataframe(no_pto_df, use_container_width=True, hide_index=True)
        else:
            info_box("All active employees have PTO recorded in this period.")

    # ── Module 1: Planned vs Unplanned ──────────────────────────────────────
    divider()
    section_header("Planned vs Unplanned PTO")

    _PLANNED_TYPES   = {"vacation", "floating holiday", "reward pto"}
    _UNPLANNED_TYPES = {"personal", "absence", "absence (sick)", "absence (covid)", "long term sick leave"}
    _PROTECTED_TYPES = {"jury duty", "bereavement", "fmla"}

    def _classify_pto(t: str) -> str:
        tl = t.strip().lower()
        if tl in _PLANNED_TYPES:   return "Planned"
        if tl in _UNPLANNED_TYPES: return "Unplanned"
        if tl in _PROTECTED_TYPES: return "Protected / Neutral"
        return "Other"

    def _drill_table(source_df: pd.DataFrame, label: str) -> None:
        section_label(f"Employees — {label}")
        d = source_df.copy()
        d["start_date"] = d["start_date"].dt.strftime("%Y-%m-%d")
        d["end_date"]   = d["end_date"].dt.strftime("%Y-%m-%d")
        d["Hours"] = d["hours"].round(1)
        d["Days"]  = (d["hours"] / 8).round(1)
        d = (
            d.rename(columns={"employee": "Employee", "building": "Building",
                               "pto_type": "PTO Type", "start_date": "Start", "end_date": "End"})
            [["Employee", "Building", "PTO Type", "Start", "End", "Hours", "Days"]]
            .sort_values(["Employee", "Start"])
        )
        st.dataframe(d, use_container_width=True, hide_index=True)

    df_cls = df.copy()
    df_cls["category"] = df_cls["pto_type"].apply(_classify_pto)
    cat_hrs = df_cls.groupby("category")["hours"].sum()
    total_cls_h = cat_hrs.sum()
    plan_h = cat_hrs.get("Planned", 0)
    unpl_h = cat_hrs.get("Unplanned", 0)
    prot_h = cat_hrs.get("Protected / Neutral", 0)

    pv1, pv2, pv3, pv4 = st.columns(4)
    _pct = lambda h: f"{h / total_cls_h * 100:.0f}%" if total_cls_h else "—"
    with pv1:
        _pto_metric("Planned", _pct(plan_h), f"{plan_h / 8:.1f} days")
    with pv2:
        _pto_metric("Unplanned", _pct(unpl_h), f"{unpl_h / 8:.1f} days")
    with pv3:
        _pto_metric("Protected / Neutral", _pct(prot_h), f"{prot_h / 8:.1f} days")
    with pv4:
        ratio_str = f"{plan_h / unpl_h:.1f}×" if unpl_h else "N/A"
        _pto_metric("Plan : Unplan Ratio", ratio_str, "higher = more predictable")

    df_cls["month"] = df_cls["start_date"].dt.to_period("M").dt.to_timestamp()
    mcat = (
        df_cls[df_cls["category"].isin(["Planned", "Unplanned"])]
        .groupby(["month", "category"])["hours"].sum().reset_index()
    )
    pv_l, pv_r = st.columns([2, 1])
    pu_event = None
    _pu_trace_cats: list[str] = []
    with pv_l:
        if not mcat.empty:
            _CAT_CLR = {"Planned": "#2684F0", "Unplanned": "#26F0DA"}
            pu_fig = go.Figure()
            for cat in ["Planned", "Unplanned"]:
                sub = mcat[mcat["category"] == cat]
                if not sub.empty:
                    _pu_trace_cats.append(cat)
                    pu_fig.add_trace(go.Bar(
                        x=sub["month"], y=sub["hours"], name=cat,
                        marker=dict(color=_CAT_CLR[cat], line=dict(color="#060d1f", width=1)),
                        hovertemplate=f"<b>{cat}</b><br>%{{x|%b %Y}}: %{{y:.0f}} hrs<extra></extra>",
                    ))
            pu_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
                xaxis=dict(showgrid=False, color="#4a7fa5"),
                yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#4a7fa5")),
                margin=dict(t=10, b=10, l=10, r=10),
                barmode="group",
            )
            pu_event = st.plotly_chart(pu_fig, use_container_width=True, on_select="rerun", key="pto_pu_trend")
        else:
            info_box("Not enough monthly data for trend.")
    with pv_r:
        section_label("Type \u2192 Category Map")
        cls_tbl = (
            df_cls.groupby(["pto_type", "category"])["hours"].sum()
            .reset_index()
            .rename(columns={"pto_type": "Type", "category": "Category", "hours": "Hours"})
            .sort_values("Hours", ascending=False)
        )
        cls_tbl["Hours"] = cls_tbl["Hours"].round(1)
        st.dataframe(cls_tbl, use_container_width=True, hide_index=True, height=300)

    # Trend drilldown — rendered outside columns at full width
    pu_pts = pu_event.selection.get("points", []) if (pu_event and pu_event.selection) else []
    if pu_pts:
        pt = pu_pts[0]
        cn = pt.get("curve_number", 0)
        sel_cat = _pu_trace_cats[cn] if cn < len(_pu_trace_cats) else None
        x_raw = pt.get("x") or pt.get("label") or ""
        if sel_cat and x_raw:
            try:
                sel_period = pd.to_datetime(x_raw).to_period("M")
                drill_pu = df_cls[
                    (df_cls["category"] == sel_cat) &
                    (df_cls["start_date"].dt.to_period("M") == sel_period)
                ]
                if not drill_pu.empty:
                    divider()
                    _drill_table(drill_pu, f"{sel_cat} \u2014 {sel_period.strftime('%b %Y')}")
            except Exception:
                pass

    # ── Module 2: Concentration ──────────────────────────────────────
    divider()
    section_header("PTO Concentration \u2014 Who's Driving Usage?")

    emp_hrs = df.groupby("employee")["hours"].sum().sort_values(ascending=False).reset_index()
    n_total_emp = len(emp_hrs)
    top10_n = max(1, round(n_total_emp * 0.10))
    total_emp_hrs = emp_hrs["hours"].sum()
    top10_pct_hrs = emp_hrs.head(top10_n)["hours"].sum() / total_emp_hrs * 100 if total_emp_hrs else 0
    concentration_label = "High" if top10_pct_hrs > 50 else ("Moderate" if top10_pct_hrs > 33 else "Even")

    cn1, cn2, cn3 = st.columns(3)
    with cn1:
        _pto_metric("Employees using PTO", str(n_total_emp), "in selected period")
    with cn2:
        _pto_metric(f"Top 10% ({top10_n} people)", f"{top10_pct_hrs:.0f}% of hours", "concentration signal")
    with cn3:
        _pto_metric("Distribution", concentration_label, "of PTO across team")

    # Pre-compute histogram bins before column block so they're accessible for drilldown
    import numpy as _np
    _max_h = max(float(emp_hrs["hours"].max()), 1.0)
    _bin_edges = list(_np.linspace(0, _max_h, 11))
    _bin_labels = [f"{int(_bin_edges[i])}\u2013{int(_bin_edges[i+1])}h" for i in range(10)]
    _emp_hrs_b = emp_hrs.copy()
    _emp_hrs_b["bin"] = pd.cut(_emp_hrs_b["hours"], bins=_bin_edges, labels=_bin_labels, include_lowest=True)
    _bin_counts = _emp_hrs_b.groupby("bin", observed=False)["hours"].count().reindex(_bin_labels).fillna(0)

    top10_hrs_sum = emp_hrs.head(10)["hours"].sum()
    rest_hrs_sum = emp_hrs.iloc[10:]["hours"].sum() if n_total_emp > 10 else 0

    conc_event = None
    hist_event = None
    cc1, cc2 = st.columns(2)
    with cc1:
        conc_fig = go.Figure(go.Bar(
            y=["Top 10 Users", "Rest of Team"],
            x=[top10_hrs_sum, rest_hrs_sum],
            orientation="h",
            marker=dict(color=["#00d4ff", "#1a3a5c"], line=dict(color="#060d1f", width=1)),
            text=[f"{top10_hrs_sum / 8:.0f}d", f"{rest_hrs_sum / 8:.0f}d"],
            textposition="inside",
            textfont=dict(color="#e8f4fd"),
            hovertemplate="<b>%{y}</b>: %{x:.0f} hrs<extra></extra>",
        ))
        conc_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            yaxis=dict(showgrid=False, color="#4a7fa5"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=180,
        )
        conc_event = st.plotly_chart(conc_fig, use_container_width=True, on_select="rerun", key="pto_conc_bar")
    with cc2:
        hist_fig = go.Figure(go.Bar(
            x=_bin_labels,
            y=_bin_counts.values,
            marker=dict(color="#7b61ff", line=dict(color="#060d1f", width=1)),
            hovertemplate="<b>%{x}</b>: %{y} employees<extra></extra>",
        ))
        hist_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5", title="Total Hours Used", tickangle=-30),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="# Employees"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=180,
            bargap=0.05,
        )
        hist_event = st.plotly_chart(hist_fig, use_container_width=True, on_select="rerun", key="pto_dist_hist")

    # Concentration drilldowns — rendered outside columns at full width
    conc_pts = conc_event.selection.get("points", []) if (conc_event and conc_event.selection) else []
    if conc_pts:
        bar_label = conc_pts[0].get("y") or conc_pts[0].get("label") or ""
        if bar_label in ("Top 10 Users", "Rest of Team"):
            _group = emp_hrs.head(10) if bar_label == "Top 10 Users" else emp_hrs.iloc[10:]
            _grp_names = set(_group["employee"])
            _grp_df = df[df["employee"].isin(_grp_names)]

            if {"first_name", "last_name"}.issubset(_grp_df.columns):
                _grp_df = _grp_df.copy()
                _grp_df["First Name"] = _grp_df["first_name"].astype(str).str.strip()
                _grp_df["Last Name"] = _grp_df["last_name"].astype(str).str.strip()
            else:
                _grp_df = _grp_df.copy()
                _name_split = _grp_df["employee"].astype(str).str.split(",", n=1, expand=True)
                _grp_df["Last Name"] = _name_split[0].fillna("").str.strip()
                _grp_df["First Name"] = _name_split[1].fillna("").str.strip()

            _hours_agg = (
                _grp_df.groupby(["First Name", "Last Name", "pto_type"], as_index=False)["hours"]
                .sum()
                .rename(columns={"pto_type": "PTO Type", "hours": "Total Hours"})
            )

            _days_df = _grp_df[["First Name", "Last Name", "pto_type", "start_date", "end_date"]].copy()
            _days_df["impact_date"] = _days_df.apply(
                lambda r: _weekday_date_range(r["start_date"], r["end_date"]),
                axis=1,
            )
            _days_df = _days_df.explode("impact_date")
            _days_agg = (
                _days_df.groupby(["First Name", "Last Name", "pto_type"])["impact_date"]
                .nunique()
                .reset_index(name="Days Impacted")
                .rename(columns={"pto_type": "PTO Type"})
            )

            _grp_agg = _hours_agg.merge(
                _days_agg,
                on=["First Name", "Last Name", "PTO Type"],
                how="left",
            )
            _grp_agg["Total Hours"] = _grp_agg["Total Hours"].round(1)
            _grp_agg["Days Impacted"] = _grp_agg["Days Impacted"].fillna(0).astype(int)
            _grp_agg = _grp_agg.sort_values(
                ["Total Hours", "Last Name", "First Name", "PTO Type"],
                ascending=[False, True, True, True],
            )
            divider()
            section_label(f"PTO Breakdown - {bar_label}")
            st.dataframe(
                _grp_agg[["First Name", "Last Name", "PTO Type", "Total Hours", "Days Impacted"]],
                use_container_width=True,
                hide_index=True,
            )

    hist_pts = hist_event.selection.get("points", []) if (hist_event and hist_event.selection) else []
    if hist_pts:
        bin_sel = hist_pts[0].get("x") or hist_pts[0].get("label") or ""
        if bin_sel in _bin_labels:
            bi = _bin_labels.index(bin_sel)
            lo, hi = _bin_edges[bi], _bin_edges[bi + 1]
            names_in_bin = set(_emp_hrs_b[(_emp_hrs_b["hours"] >= lo) & (_emp_hrs_b["hours"] <= hi)]["employee"])
            if names_in_bin:
                _hist_df = df[df["employee"].isin(names_in_bin)]
                _hist_agg = (
                    _hist_df.groupby(["employee", "building", "pto_type"])["hours"].sum()
                    .reset_index()
                    .rename(columns={"employee": "Employee", "building": "Building",
                                     "pto_type": "PTO Type", "hours": "Hours"})
                    .sort_values(["Employee", "Hours"], ascending=[True, False])
                )
                _hist_agg["Hours"] = _hist_agg["Hours"].round(1)
                _hist_agg["Days"] = (_hist_agg["Hours"] / 8).round(1)
                divider()
                section_label(f"Employees Using {bin_sel} — by PTO Type")
                st.dataframe(_hist_agg, use_container_width=True, hide_index=True)

    # ── Module 3: Burnout & Retention Risk ──────────────────────────────────
    divider()
    section_header("Burnout & Retention Risk")

    low10_n = max(1, round(n_total_emp * 0.10))
    low_users = emp_hrs.tail(low10_n).copy() if n_total_emp >= 5 else pd.DataFrame()
    low_avg_days = low_users["hours"].mean() / 8 if not low_users.empty else 0
    no_pto_count = len(no_pto)
    no_pto_rate = no_pto_count / max(1, len(all_active_names)) * 100

    br1, br2, br3 = st.columns(3)
    with br1:
        _pto_metric("No PTO Recorded", str(no_pto_count), "employees — 0 hrs")
    with br2:
        _pto_metric("Zero-PTO Rate", f"{no_pto_rate:.0f}%", "of active headcount")
    with br3:
        _pto_metric("Lowest 10% Avg", f"{low_avg_days:.1f} days", "potential burnout flag")

    brl, brr = st.columns(2)

    with brl:
        section_label("No PTO Usage — Burnout Risk")
        if no_pto:
            st.dataframe(pd.DataFrame({"Employee": no_pto}), use_container_width=True, hide_index=True)
        else:
            info_box("All active employees have PTO recorded. ✓")
    with brr:
        section_label(f"Bottom 10% of Users({low10_n} employees)")
        if not low_users.empty:
            low_users["Days"] = (low_users["hours"] / 8).round(1)
            low_users = low_users.rename(columns={"employee": "Employee", "hours": "Hours"})
            low_users["Hours"] = low_users["Hours"].round(1)
            st.dataframe(low_users[["Employee", "Hours", "Days"]], use_container_width=True, hide_index=True)
        else:
            info_box("Not enough data for bottom 10% analysis.")

    # ── Module 4: Pace & Seasonality ────────────────────────────────────────
    divider()
    section_header("PTO Pace & Seasonality")

    from datetime import timedelta as _td
    period_days = max(1, (date_end - date_start).days + 1)
    total_days = total_hours / 8
    annualized_total = total_days / period_days * 365
    annualized_per_emp = avg_hours / 8 / period_days * 365 if unique_emps else 0

    mid = date_start + _td(days=period_days // 2)
    fh_hrs = df[df["start_date"].dt.date < mid]["hours"].sum()
    sh_hrs = df[df["start_date"].dt.date >= mid]["hours"].sum()
    fh_rate = fh_hrs / max(1, period_days // 2)
    sh_rate = sh_hrs / max(1, period_days - period_days // 2)
    delta_pct = (sh_rate - fh_rate) / fh_rate * 100 if fh_rate else 0
    trend_arrow = "▲" if delta_pct > 5 else ("▼" if delta_pct < -5 else "→")

    ps1, ps2, ps3 = st.columns(3)
    with ps1:
        _pto_metric("Annualized PTO Days", f"{annualized_total:,.0f}", "at current pace — total")
    with ps2:
        _pto_metric("Days / Employee (ann.)", f"{annualized_per_emp:.1f}", "per active employee")
    with ps3:
        _pto_metric("Usage Trend", f"{trend_arrow} {abs(delta_pct):.0f}%", "2nd vs 1st half of period")

    _MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    df_season = df_all.copy()
    if sel_building != "All":
        df_season = df_season[df_season["building"] == sel_building]
    df_season["cal_month"] = df_season["start_date"].dt.month
    season = (
        df_season.groupby("cal_month")["hours"].sum()
        .reindex(range(1, 13)).fillna(0).reset_index()
    )
    season["label"] = [_MONTH_LABELS[m - 1] for m in season["cal_month"]]
    season_fig = go.Figure(go.Bar(
        x=season["label"],
        y=season["hours"],
        marker=dict(
            color=season["hours"],
            colorscale=[[0, "#0d1b2e"], [0.5, "#7b61ff"], [1, "#00d4ff"]],
            line=dict(color="#060d1f", width=1),
        ),
        text=(season["hours"] / 8).round(0).astype(int).astype(str) + "d",
        textposition="outside",
        hovertemplate="<b>%{x}</b>: %{y:.0f} total hrs<extra></extra>",
    ))
    season_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
        xaxis=dict(showgrid=False, color="#4a7fa5"),
        yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Total Hours"),
        margin=dict(t=30, b=10, l=10, r=10),
    )
    season_event = st.plotly_chart(season_fig, use_container_width=True, on_select="rerun", key="pto_seasonality")
    season_pts = season_event.selection.get("points", []) if (season_event and season_event.selection) else []
    if season_pts:
        sel_mon_label = season_pts[0].get("x") or season_pts[0].get("label") or ""
        if sel_mon_label in _MONTH_LABELS:
            sel_mon_num = _MONTH_LABELS.index(sel_mon_label) + 1
            df_mon = df.copy()
            df_mon["cal_month"] = df_mon["start_date"].dt.month
            drill_mon = df_mon[df_mon["cal_month"] == sel_mon_num]
            if not drill_mon.empty:
                divider()
                _drill_table(drill_mon, f"PTO in {sel_mon_label}")

    # ── Export ──────────────────────────────────────────────────────────────
    divider()
    section_label("Export Filtered Data")
    exp_cols = ["employee_id", "employee", "building", "pto_type", "start_date", "end_date", "hours", "days"]
    exp_df = df[[c for c in exp_cols if c in df.columns]].copy()
    exp_df["start_date"] = exp_df["start_date"].dt.strftime("%Y-%m-%d")
    exp_df["end_date"] = exp_df["end_date"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "Download filtered PTO as CSV",
        data=to_csv(exp_df),
        file_name=f"pto_export_{date_start}_{date_end}.csv",
        mime="text/csv",
    )
    def _clear_pto_data() -> None:
        st.session_state.pop("pto_df", None)
        st.session_state.pop("pto_type_toggles", None)
        try:
            with db.tx(conn):
                repo.clear_pto_data(conn)
        except Exception:
            pass
        st.toast("PTO data cleared.")
        st.rerun()

    # ── Clear data ──────────────────────────────────────────────────────────
    divider()
    st.markdown(
        "<p style='color:#6a8ab8;font-size:.8rem;margin-bottom:.4rem'>"
        "Clear the loaded CSV data to start over with a new file.</p>",
        unsafe_allow_html=True,
    )
    pto_clear_confirmed = st.checkbox("I confirm \u2014 clear all PTO data", key="pto_clear_confirm")
    if st.button("Clear PTO Data", key="pto_clear_btn_footer", disabled=not pto_clear_confirmed):
        _clear_pto_data()

