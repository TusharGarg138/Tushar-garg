"""
Streamlit Web UI for exploring weather station network data quality and flags.
"""

import os
import sys
import pandas as pd
import streamlit as st

# Ensure repository root is in python path
repo_root = os.path.dirname(os.path.abspath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.pipeline import run_pipeline
from src.validation import ValidationError

st.set_page_config(
    page_title="Ridgeline Weather QA Dashboard",
    page_icon="⛅",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1a365d;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 14px;
        color: #718096;
        margin-bottom: 15px;
    }
    .metric-card {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 10px 14px;
        text-align: center;
    }
    .action-exclude { color: #c53030; font-weight: 600; }
    .action-correct { color: #dd6b20; font-weight: 600; }
    .action-keep { color: #2f855a; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("Network QA Controls")
st.sidebar.markdown("Configure data pack path and run analysis.")

default_path = os.path.abspath("ridgeline_data_pack")
data_dir_input = st.sidebar.text_input(
    "Data Pack Folder Path:",
    value=default_path if os.path.exists(default_path) else "."
)

run_button = st.sidebar.button("Run Data-Quality Checker", type="primary")

st.markdown('<div class="main-header">⛅ Ridgeline Weather Network: Data Quality Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated screening, evidence-based quality flags, and technician visit prioritization.</div>', unsafe_allow_html=True)

# Session state initialization
if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None

# If user clicked Run
if run_button:
    if not os.path.exists(data_dir_input) or not os.path.isdir(data_dir_input):
        st.sidebar.error("Error: Provided path is not an existing directory.")
    else:
        with st.spinner("Analyzing weather data, GPS sentences, and maintenance notes..."):
            try:
                res = run_pipeline(
                    data_pack_dir=data_dir_input,
                    output_dir=".",
                    generate_reports=True
                )
                st.session_state.pipeline_result = res
                st.sidebar.success(f"Success! Processed {len(res.datapack.metadata)} stations.")
            except ValidationError as ve:
                st.sidebar.error(f"Validation Error: {ve}")
            except Exception as e:
                st.sidebar.error(f"Error during analysis: {e}")

# If we have results in session state or can load existing flags.csv
res = st.session_state.pipeline_result

if res is None and os.path.exists("flags.csv"):
    # Load default data if checker was already run
    try:
        res = run_pipeline(
            data_pack_dir=default_path,
            output_dir=".",
            generate_reports=True
        )
        st.session_state.pipeline_result = res
    except Exception:
        pass

if res:
    flags = res.flags
    pack = res.datapack
    rec = res.recommendation

    # Top KPI Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Stations Processed", len(pack.metadata))
    c2.metric("Total Flags", len(flags))
    c3.metric("Exclude Flags", sum(1 for f in flags if f.action == "exclude"))
    c4.metric("Correct Flags", sum(1 for f in flags if f.action == "correct"))
    c5.metric("Keep Flags", sum(1 for f in flags if f.action == "keep"))

    tabs = st.tabs(["📋 Quality Flags", "🔧 Technician Recommendation", "📊 Station Overview", "📄 Executive Report"])

    with tabs[0]:
        st.subheader("Data-Quality Flags (Schema-Compliant)")
        st.caption("Browse, search, and filter identified findings. Exactly matches `flags.csv`.")

        # Convert flags to DataFrame
        flags_df = pd.DataFrame([f.to_csv_dict() for f in flags])

        # Filters
        f1, f2, f3, f4 = st.columns(4)
        station_filter = f1.multiselect("Filter Station:", sorted(flags_df["station_id"].unique()), default=[])
        action_filter = f2.multiselect("Filter Action:", ["exclude", "correct", "keep"], default=[])
        channel_filter = f3.multiselect("Filter Channel:", sorted(flags_df["channel"].unique()), default=[])
        issue_search = f4.text_input("Search Issue / Note:", "")

        filtered_df = flags_df.copy()
        if station_filter:
            filtered_df = filtered_df[filtered_df["station_id"].isin(station_filter)]
        if action_filter:
            filtered_df = filtered_df[filtered_df["action"].isin(action_filter)]
        if channel_filter:
            filtered_df = filtered_df[filtered_df["channel"].isin(channel_filter)]
        if issue_search:
            filtered_df = filtered_df[
                filtered_df["issue"].str.contains(issue_search, case=False) |
                filtered_df["note"].str.contains(issue_search, case=False)
            ]

        st.dataframe(filtered_df, use_container_width=True, height=350)

        # Download button
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Filtered flags.csv",
            data=csv_data,
            file_name="flags_filtered.csv",
            mime="text/csv"
        )

        # Flag detail expander
        st.markdown("#### Selected Flag Deep-Dive")
        flag_options = [f"[{row['station_id']}] {row['channel']} - {row['issue']} ({row['start_utc']})" for _, row in filtered_df.iterrows()]
        if flag_options:
            selected_flag_idx = st.selectbox("Select finding to inspect evidence:", range(len(flag_options)), format_func=lambda i: flag_options[i])
            sel = filtered_df.iloc[selected_flag_idx]
            st.info(f"**Station:** {sel['station_id']} | **Channel:** `{sel['channel']}` | **Action:** `{sel['action'].upper()}`\n\n"
                    f"**Interval:** {sel['start_utc']} to {sel['end_utc']}\n\n"
                    f"**Issue:** {sel['issue']}\n\n"
                    f"**Evidence & Rationale:** {sel['note']}")

    with tabs[1]:
        st.subheader("Technician Visit Prioritization (One-Hour Window)")
        
        col_rec1, col_rec2 = st.columns([3, 2])
        with col_rec1:
            st.success(f"### Recommended Visit: Station {rec.top_station} ({pack.metadata.get(rec.top_station).name if rec.top_station in pack.metadata else ''})")
            st.markdown(f"**Priority Score:** `{rec.top_score}` (Highest uncorrectable hardware risk)")
            st.markdown(f"**Supporting Evidence:**\n{rec.top_evidence}")
            
            st.markdown("#### One-Hour Action Protocol:")
            for step in rec.top_protocol:
                st.markdown(f"- {step}")
                
            st.markdown(f"**Expected Outcome:** {rec.top_expected_outcome}")

        with col_rec2:
            st.warning(f"### Second-Best Candidate: Station {rec.second_station} ({pack.metadata.get(rec.second_station).name if rec.second_station in pack.metadata else ''})")
            st.markdown(f"**Score:** `{rec.second_score}`")
            st.markdown(f"**Status:** {rec.second_evidence}")
            st.markdown("#### Prioritization Rationale:")
            st.markdown(rec.priority_rationale)

        st.markdown("---")
        st.markdown("#### Network Station Priority Rankings:")
        st.table(pd.DataFrame(rec.all_rankings)[["station_id", "station_name", "score", "flag_count", "is_active"]])

    with tabs[2]:
        st.subheader("Station Metadata & Time Coverage")
        meta_rows = []
        for st_id, m in pack.metadata.items():
            st_df = pack.weather_data.get(st_id)
            recs = len(st_df) if st_df is not None else 0
            t_min = st_df["timestamp_utc"].min() if st_df is not None and not st_df.empty else "N/A"
            t_max = st_df["timestamp_utc"].max() if st_df is not None and not st_df.empty else "N/A"
            meta_rows.append({
                "Station ID": m.station_id,
                "Name": m.name,
                "Latitude": m.lat,
                "Longitude": m.lon,
                "Elevation (m)": m.elevation_m,
                "Cadence": f"{m.logger_interval_min} min",
                "Total Records": recs,
                "Start UTC": t_min,
                "End UTC": t_max
            })
        st.dataframe(pd.DataFrame(meta_rows), use_container_width=True)

    with tabs[3]:
        st.subheader("Coordinator Network Health Report")
        if res.report_html_path and os.path.exists(res.report_html_path):
            with open(res.report_html_path, "r", encoding="utf-8") as f:
                html_text = f.read()
            st.components.v1.html(html_text, height=750, scrolling=True)
            
            with open(res.report_html_path, "rb") as f:
                st.download_button("📥 Download report.html", data=f.read(), file_name="report.html", mime="text/html")
            if res.report_pdf_path and os.path.exists(res.report_pdf_path):
                with open(res.report_pdf_path, "rb") as f:
                    st.download_button("📥 Download report.pdf", data=f.read(), file_name="report.pdf", mime="application/pdf")
        else:
            st.info("Report not yet generated.")

else:
    st.info("👈 Enter the data pack directory in the sidebar and click **'Run Data-Quality Checker'** to start.")
