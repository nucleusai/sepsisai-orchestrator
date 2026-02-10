"""
SepsisAI — Clinical Monitoring Dashboard (Streamlit).

Provides real-time visualization of patient data, clinical scores,
and AI-predicted sepsis risk.  Auto-refreshes every 10 seconds.
"""

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

AI_URL = f"http://{AI_HOST}:{AI_PORT}"

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SepsisAI Monitor",
    page_icon=":hospital:",
    layout="wide",
)

# Auto-refresh every 10 s
st_autorefresh(interval=10_000, key="refresh")

# ---------------------------------------------------------------------------
# MongoDB connection (cached so it survives re-runs)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_mongo_collection():
    client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    return client[MONGO_DB]["NewDataComplet"]


collection = get_mongo_collection()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("SepsisAI — Clinical Dashboard")
st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

# ---------------------------------------------------------------------------
# Patient selector (global)
# ---------------------------------------------------------------------------
patient_ids = sorted(collection.distinct("Paciente"))

if not patient_ids:
    st.warning(
        "No patient data found in MongoDB. "
        "Run the CDA preprocessing service first:  `make seed`"
    )
    st.stop()

selected_patient = st.selectbox("Select a patient", patient_ids)

# Fetch patient data once
raw_data = list(collection.find({"Paciente": selected_patient}, {"_id": 0}))
df = pd.DataFrame(raw_data).replace(-9999, np.nan)

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

    time_axis = st.selectbox(
        "Time axis", ["ICULOS", "Hora"], key="t0_time",
    )

    if not df.empty:
        df_sorted = df.sort_values(by=time_axis)
        vitals = {
            "HR": "Heart Rate",
            "O2Sat": "O2 Saturation",
            "Temp": "Temperature",
            "MAP": "Mean Arterial Pressure",
            "SBP": "Systolic BP",
            "DBP": "Diastolic BP",
            "Resp": "Respiration Rate",
        }

        fig = go.Figure()
        for var, label in vitals.items():
            y = pd.to_numeric(df_sorted[var], errors="coerce")
            fig.add_trace(go.Scatter(
                x=df_sorted[time_axis], y=y,
                mode="lines+markers", name=label,
            ))

        fig.update_layout(
            height=600,
            title=f"Vital Signs — Patient {selected_patient}",
            xaxis_title=time_axis,
            yaxis_title="Value",
            legend_title="Variable",
        )
        st.plotly_chart(fig, use_container_width=True, key="overview_chart")
    else:
        st.warning("No data available for this patient.")

# ── Tab 1: Clinical Variables (multi-patient comparison) ──────────────────
with tab1:
    st.subheader("Clinical Variable Comparison")

    compare_patients = st.multiselect(
        "Compare with other patients",
        patient_ids,
        default=[selected_patient],
    )

    vital_options = ["HR", "O2Sat", "Temp", "MAP", "SBP", "DBP", "Resp"]
    selected_var = st.selectbox("Variable", vital_options)
    time_axis_1 = st.selectbox("Time axis", ["ICULOS", "Hora"], key="t1_time")

    df_combined = pd.DataFrame()
    for pid in compare_patients:
        rows = list(collection.find({"Paciente": pid}))
        dfp = pd.DataFrame(rows)
        if selected_var in dfp.columns and time_axis_1 in dfp.columns:
            dfp = dfp.sort_values(by=time_axis_1)
            dfp[selected_var] = dfp[selected_var].replace(-9999, np.nan)
            dfp["Paciente"] = pid
            df_combined = pd.concat([df_combined, dfp], ignore_index=True)

    if not df_combined.empty:
        fig1 = px.line(
            df_combined, x=time_axis_1, y=selected_var,
            color="Paciente", markers=True,
            title=f"{selected_var} — Patient Comparison",
        )
        st.plotly_chart(fig1, use_container_width=True, key="comparison_chart")
    else:
        st.warning("No valid data for the selected patients.")

    # Distribution histogram
    st.markdown("### Global Distribution")
    all_vals = list(collection.find({}, {"_id": 0, selected_var: 1}))
    df_all = pd.DataFrame(all_vals)
    df_all[selected_var] = df_all[selected_var].replace(-9999, np.nan).dropna()

    if not df_all.empty:
        fig_dist = px.histogram(
            df_all, x=selected_var, nbins=50, marginal="box",
            opacity=0.7, histnorm="probability density",
            title=f"Distribution of {selected_var} across all patients",
        )

        # Highlight selected patients
        for pid in compare_patients:
            dfp = df_combined[df_combined["Paciente"] == pid]
            vals = dfp[selected_var].dropna().values
            if len(vals) > 0:
                last_val = vals[-1]
                fig_dist.add_vline(
                    x=last_val, line_dash="dash", line_color="red",
                    annotation_text=f"{pid}: {last_val:.2f}",
                    annotation_position="top",
                )

        st.plotly_chart(fig_dist, use_container_width=True, key="dist_chart")

# ── Tab 2: Laboratory Data ────────────────────────────────────────────────
with tab2:
    st.subheader("Laboratory Data")

    lab_options = ["WBC", "Bilirubin_total", "FiO2", "BUN"]
    selected_lab = st.selectbox("Lab variable", lab_options)
    time_axis_2 = st.selectbox("Time axis", ["ICULOS", "Hora"], key="t2_time")

    if selected_lab in df.columns and time_axis_2 in df.columns:
        df_lab = df.sort_values(by=time_axis_2)
        fig2 = px.line(
            df_lab, x=time_axis_2, y=selected_lab,
            markers=True,
            title=f"{selected_lab} — Patient {selected_patient}",
        )
        st.plotly_chart(fig2, use_container_width=True, key="lab_chart")
    else:
        st.warning("No valid data for the selected lab variable.")

# ── Tab 3: Prediction Scores ─────────────────────────────────────────────
with tab3:
    st.subheader("Prediction & Clinical Scores")

    pred_options = ["SepsisLabel", "Sepsis_SIRS", "Sepsis_SOFA"]
    selected_pred = st.selectbox("Score", pred_options)
    time_axis_3 = st.selectbox("Time axis", ["ICULOS", "Hora"], key="t3_time")

    if selected_pred in df.columns and time_axis_3 in df.columns:
        df_pred = df.sort_values(by=time_axis_3)
        fig3 = px.line(
            df_pred, x=time_axis_3, y=selected_pred,
            markers=True,
            title=f"{selected_pred} — Patient {selected_patient}",
        )
        st.plotly_chart(fig3, use_container_width=True, key="pred_chart")
    else:
        st.warning("No valid data for the selected prediction score.")

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
# Background alert processing  (runs on every refresh cycle)
# ---------------------------------------------------------------------------
if "processed_ids" not in st.session_state:
    st.session_state.processed_ids = set()

new_records = list(
    collection.find({"notificado": False}, {"_id": 1, "Paciente": 1, "Hora": 1})
)
new_records = [r for r in new_records if r["_id"] not in st.session_state.processed_ids]

for record in new_records:
    st.session_state.processed_ids.add(record["_id"])
    body = {"patient": record["Paciente"], "hour": str(record["Hora"])}

    try:
        resp = requests.post(f"{AI_URL}/predict/by-patient", json=body, timeout=10)
        if resp.status_code == 200:
            pred = resp.json().get("prediction", -1)
            if pred == 1:
                st.toast(
                    f"HIGH RISK — Patient {body['patient']} hour {body['hour']}",
                    icon="🔥",
                )
            else:
                st.toast(
                    f"Patient {body['patient']} hour {body['hour']} — No risk",
                    icon="✅",
                )
        collection.update_one({"_id": record["_id"]}, {"$set": {"notificado": True}})
    except Exception as e:
        st.toast(f"Alert error: {e}", icon="⚠️")
