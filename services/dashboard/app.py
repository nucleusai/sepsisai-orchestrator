"""
SepsisAI — Clinical Monitoring Dashboard (Streamlit).

Provides real-time visualization of patient data, clinical scores,
and AI-predicted sepsis risk.  Auto-refreshes every 10 seconds.

Supports two data sources:
  - MongoDB (CDA-processed records)
  - CSV file (semicolon-separated, with Patient_ID column)
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "SepsisTraining")
AI_HOST = os.getenv("AI_SERVICE_HOST", "localhost")
AI_PORT = os.getenv("AI_SERVICE_PORT", "8000")
CSV_DATA_DIR = os.getenv("CSV_DATA_DIR", "/csv_data")

AI_URL = f"http://{AI_HOST}:{AI_PORT}"

# Standard patient-id column used internally
PATIENT_COL = "Paciente"

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SepsisAI Monitor",
    page_icon=":hospital:",
    layout="wide",
)

st_autorefresh(interval=10_000, key="refresh")

# ---------------------------------------------------------------------------
# MongoDB connection (cached)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_mongo_collection():
    client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    return client[MONGO_DB]["NewDataComplet"]


# ---------------------------------------------------------------------------
# CSV loader (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_csv(path: str) -> pd.DataFrame:
    """Load a semicolon- or comma-separated CSV and normalise columns."""
    p = Path(path)
    if not p.is_file():
        return pd.DataFrame()

    # Auto-detect separator
    first_line = p.read_text(encoding="utf-8").split("\n", 1)[0]
    sep = ";" if ";" in first_line else ","

    df = pd.read_csv(p, sep=sep)

    # Normalise the patient-id column
    if "Patient_ID" in df.columns and PATIENT_COL not in df.columns:
        df.rename(columns={"Patient_ID": PATIENT_COL}, inplace=True)

    # Add a zero-based Hora column per patient if missing
    if "Hora" not in df.columns:
        df["Hora"] = df.groupby(PATIENT_COL).cumcount()

    return df


def discover_csv_files(directory: str) -> list[str]:
    """Return CSV/TSV files found in *directory*."""
    d = Path(directory)
    if not d.is_dir():
        return []
    return sorted(
        str(f) for f in d.iterdir()
        if f.suffix.lower() in (".csv", ".tsv")
    )


# ═══════════════════════════════════════════════════════════════════════════
# HEADER & DATA-SOURCE SELECTOR
# ═══════════════════════════════════════════════════════════════════════════
st.title("SepsisAI-Orchestrator - Clinical Dashboard")
st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

# --- Data source picker (sidebar) ----------------------------------------
with st.sidebar:
    st.header("Data Source")
    source = st.radio("Load patient data from:", ["MongoDB", "CSV file"], key="ds")

    csv_path_selected: str | None = None

    if source == "CSV file":
        csv_files = discover_csv_files(CSV_DATA_DIR)

        if csv_files:
            csv_path_selected = st.selectbox(
                "Available CSV files",
                csv_files,
                format_func=lambda p: Path(p).name,
            )
        else:
            st.info(f"No CSV files found in `{CSV_DATA_DIR}`.")

        uploaded = st.file_uploader("Or upload a CSV", type=["csv", "tsv"])
        if uploaded is not None:
            # Save to a temp location so load_csv() can read it
            tmp_path = Path("/tmp") / uploaded.name
            tmp_path.write_bytes(uploaded.getvalue())
            csv_path_selected = str(tmp_path)

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA  (unified: df_full has ALL patients, same column names)
# ═══════════════════════════════════════════════════════════════════════════
using_mongo = source == "MongoDB"

if using_mongo:
    collection = get_mongo_collection()
    patient_ids = sorted(collection.distinct(PATIENT_COL))
else:
    collection = None  # not used
    if csv_path_selected:
        df_full_csv = load_csv(csv_path_selected)
    else:
        df_full_csv = pd.DataFrame()

    if df_full_csv.empty:
        st.warning("No data loaded. Select a CSV or switch to MongoDB.")
        st.stop()

    patient_ids = sorted(df_full_csv[PATIENT_COL].unique())


# --- helpers to fetch data uniformly --------------------------------------
def get_patient_df(pid: str) -> pd.DataFrame:
    """Return a DataFrame of all rows for *pid*, with -9999 → NaN."""
    if using_mongo:
        rows = list(collection.find({PATIENT_COL: pid}, {"_id": 0}))
        return pd.DataFrame(rows).replace(-9999, np.nan)
    else:
        return df_full_csv.loc[df_full_csv[PATIENT_COL] == pid].copy().replace(-9999, np.nan)


def get_all_values(column: str) -> pd.DataFrame:
    """Return a single-column DataFrame with *column* across all patients."""
    if using_mongo:
        rows = list(collection.find({}, {"_id": 0, column: 1}))
        return pd.DataFrame(rows)
    else:
        return df_full_csv[[column]].copy()


# ═══════════════════════════════════════════════════════════════════════════
# PATIENT SELECTOR
# ═══════════════════════════════════════════════════════════════════════════
if not patient_ids:
    st.warning(
        "No patient data found. "
        "Run the CDA preprocessing service (`make seed`) or load a CSV file."
    )
    st.stop()

selected_patient = st.selectbox("Select a patient", patient_ids)
df = get_patient_df(selected_patient)

# Available time columns for this dataset
time_columns = [c for c in ["ICULOS", "Hora"] if c in df.columns]
if not time_columns:
    time_columns = ["ICULOS"]

# ---------------------------------------------------------------------------
# Sepsis alert banner
# ---------------------------------------------------------------------------
if not df.empty and "SepsisLabel" in df.columns:
    time_col_for_alert = time_columns[0]
    sepsis_rows = df.loc[df["SepsisLabel"] == 1, time_col_for_alert]
    if not sepsis_rows.empty:
        onset = int(sepsis_rows.min())
        st.error(
            f"SEPSIS DETECTED — Patient **{selected_patient}** has a positive "
            f"sepsis label starting at {time_col_for_alert} **{onset}**."
        )
    else:
        st.success(f"No sepsis label recorded for patient **{selected_patient}**.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "Monitoring Overview",
    "Clinical Variables",
    "Laboratory Data",
    "Prediction Scores",
    "AI Model Query",
])

# ── Tab 0: Monitoring Overview ────────────────────────────────────────────
with tab0:
    st.subheader("Complete Clinical Variable Monitoring")
    st.markdown(f"**Patient:** {selected_patient}")

    time_axis = st.selectbox("Time axis", time_columns, key="t0_time")

    if not df.empty:
        df_sorted = df.sort_values(by=time_axis)

        # Rows: SepsisLabel on top, then each vital sign
        panel_rows = [
            ("SepsisLabel", "Sepsis Label"),
            ("HR",          "Heart Rate (bpm)"),
            ("O2Sat",       "O\u2082 Sat (%)"),
            ("Temp",        "Temp (\u00b0C)"),
            ("MAP",         "MAP (mmHg)"),
            ("SBP",         "Systolic BP (mmHg)"),
            ("DBP",         "Diastolic BP (mmHg)"),
            ("Resp",        "Resp Rate (/min)"),
        ]

        row_heights = [0.4] + [1.0] * (len(panel_rows) - 1)

        fig = make_subplots(
            rows=len(panel_rows), cols=1,
            shared_xaxes=True, vertical_spacing=0.025,
            subplot_titles=[label for _, label in panel_rows],
            row_heights=row_heights,
        )

        for i, (var, label) in enumerate(panel_rows, start=1):
            y = pd.to_numeric(df_sorted.get(var), errors="coerce") if var in df_sorted.columns else pd.Series(dtype=float)

            if var == "SepsisLabel":
                colours = ["crimson" if v == 1 else "seagreen" for v in y.fillna(0)]
                fig.add_trace(
                    go.Bar(x=df_sorted[time_axis], y=y.fillna(0),
                           marker_color=colours, name=label, showlegend=False),
                    row=i, col=1,
                )
                fig.update_yaxes(title_text="Sepsis", tickvals=[0, 1],
                                 ticktext=["No", "Yes"], range=[-0.1, 1.3],
                                 row=i, col=1)
            else:
                fig.add_trace(
                    go.Scatter(x=df_sorted[time_axis], y=y,
                               mode="lines+markers", name=label,
                               line=dict(width=1.5), marker=dict(size=4),
                               showlegend=False),
                    row=i, col=1,
                )
                fig.update_yaxes(title_text=var, row=i, col=1)

        # Vertical line at sepsis onset
        if "SepsisLabel" in df_sorted.columns:
            onset_vals = df_sorted.loc[df_sorted["SepsisLabel"] == 1, time_axis]
            if not onset_vals.empty:
                onset_x = onset_vals.min()
                for i in range(1, len(panel_rows) + 1):
                    fig.add_vline(x=onset_x, line_dash="dash", line_color="red",
                                  line_width=1.5, row=i, col=1)

        fig.update_xaxes(title_text=time_axis, row=len(panel_rows), col=1)
        fig.update_layout(
            height=150 + 160 * (len(panel_rows) - 1),
            title_text=f"Vital Signs — Patient {selected_patient}",
            title_x=0.5, margin=dict(l=60, r=20, t=60, b=40),
        )
        st.plotly_chart(fig, use_container_width=True, key="overview_chart")
    else:
        st.warning("No data available for this patient.")

# ── Tab 1: Clinical Variables (multi-patient comparison) ──────────────────
with tab1:
    st.subheader("Clinical Variable Comparison")

    compare_patients = st.multiselect(
        "Compare with other patients", patient_ids, default=[selected_patient],
    )

    vital_options = ["HR", "O2Sat", "Temp", "MAP", "SBP", "DBP", "Resp"]
    selected_var = st.selectbox("Variable", vital_options)
    time_axis_1 = st.selectbox("Time axis", time_columns, key="t1_time")

    df_combined = pd.DataFrame()
    for pid in compare_patients:
        dfp = get_patient_df(pid)
        if selected_var in dfp.columns and time_axis_1 in dfp.columns:
            dfp = dfp.sort_values(by=time_axis_1)
            dfp[PATIENT_COL] = pid
            df_combined = pd.concat([df_combined, dfp], ignore_index=True)

    if not df_combined.empty:
        fig1 = px.line(
            df_combined, x=time_axis_1, y=selected_var,
            color=PATIENT_COL, markers=True,
            title=f"{selected_var} — Patient Comparison",
        )
        st.plotly_chart(fig1, use_container_width=True, key="comparison_chart")
    else:
        st.warning("No valid data for the selected patients.")

    # Distribution histogram
    st.markdown("### Global Distribution")
    df_all = get_all_values(selected_var).replace(-9999, np.nan).dropna()

    if not df_all.empty:
        fig_dist = px.histogram(
            df_all, x=selected_var, nbins=50, marginal="box",
            opacity=0.7, histnorm="probability density",
            title=f"Distribution of {selected_var} across all patients",
        )
        for pid in compare_patients:
            dfp = df_combined[df_combined[PATIENT_COL] == pid]
            vals = dfp[selected_var].dropna().values
            if len(vals) > 0:
                fig_dist.add_vline(
                    x=vals[-1], line_dash="dash", line_color="red",
                    annotation_text=f"{pid}: {vals[-1]:.2f}",
                    annotation_position="top",
                )
        st.plotly_chart(fig_dist, use_container_width=True, key="dist_chart")

# ── Tab 2: Laboratory Data ────────────────────────────────────────────────
with tab2:
    st.subheader("Laboratory Data")

    lab_options = ["WBC", "Bilirubin_total", "FiO2", "BUN"]
    selected_lab = st.selectbox("Lab variable", lab_options)
    time_axis_2 = st.selectbox("Time axis", time_columns, key="t2_time")

    if selected_lab in df.columns and time_axis_2 in df.columns:
        df_lab = df.sort_values(by=time_axis_2)
        fig2 = px.line(
            df_lab, x=time_axis_2, y=selected_lab, markers=True,
            title=f"{selected_lab} — Patient {selected_patient}",
        )
        st.plotly_chart(fig2, use_container_width=True, key="lab_chart")
    else:
        st.warning("No valid data for the selected lab variable.")

# ── Tab 3: Prediction Scores ─────────────────────────────────────────────
with tab3:
    st.subheader("Prediction & Clinical Scores")

    pred_options = ["SepsisLabel", "Sepsis_SIRS", "Sepsis_SOFA"]
    # Only show scores that exist in the data
    available_preds = [p for p in pred_options if p in df.columns]
    if available_preds:
        selected_pred = st.selectbox("Score", available_preds)
        time_axis_3 = st.selectbox("Time axis", time_columns, key="t3_time")

        if selected_pred in df.columns and time_axis_3 in df.columns:
            df_pred = df.sort_values(by=time_axis_3)
            fig3 = px.line(
                df_pred, x=time_axis_3, y=selected_pred, markers=True,
                title=f"{selected_pred} — Patient {selected_patient}",
            )
            st.plotly_chart(fig3, use_container_width=True, key="pred_chart")
    else:
        st.info("No prediction score columns found in this dataset.")

# ── Tab 4: AI Model Query ────────────────────────────────────────────────
with tab4:
    st.subheader("Query the AI Prediction Service")

    available_hours = sorted(df["Hora"].dropna().unique()) if "Hora" in df.columns else []
    if available_hours:
        selected_hour = st.selectbox("Select hour", available_hours, key="ai_hour")
    else:
        selected_hour = st.number_input("Enter hour", min_value=0, step=1, key="ai_hour_input")

    body = {"patient": selected_patient, "hour": str(int(selected_hour))}
    st.code(f"POST {AI_URL}/predict/by-patient\n\n{body}", language="json")

    if st.button("Send prediction request"):
        try:
            resp = requests.post(f"{AI_URL}/predict/by-patient", json=body, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                prediction = result.get("prediction", "N/A")
                if prediction == 1:
                    st.error(f"SEPSIS RISK DETECTED  —  prediction = {prediction}")
                else:
                    st.success(f"No sepsis risk  —  prediction = {prediction}")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

# ---------------------------------------------------------------------------
# Background alert processing (MongoDB only, runs on every refresh cycle)
# ---------------------------------------------------------------------------
if using_mongo:
    if "processed_ids" not in st.session_state:
        st.session_state.processed_ids = set()

    new_records = list(
        collection.find({"notificado": False}, {"_id": 1, PATIENT_COL: 1, "Hora": 1})
    )
    new_records = [r for r in new_records if r["_id"] not in st.session_state.processed_ids]

    for record in new_records:
        st.session_state.processed_ids.add(record["_id"])
        body = {"patient": record[PATIENT_COL], "hour": str(record["Hora"])}
        try:
            resp = requests.post(f"{AI_URL}/predict/by-patient", json=body, timeout=10)
            if resp.status_code == 200:
                pred = resp.json().get("prediction", -1)
                if pred == 1:
                    st.toast(f"HIGH RISK — Patient {body['patient']} hour {body['hour']}", icon="\U0001f525")
                else:
                    st.toast(f"Patient {body['patient']} hour {body['hour']} — No risk", icon="\u2705")
            collection.update_one({"_id": record["_id"]}, {"$set": {"notificado": True}})
        except Exception as e:
            st.toast(f"Alert error: {e}", icon="\u26a0\ufe0f")
