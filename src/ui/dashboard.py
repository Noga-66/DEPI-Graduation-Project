import streamlit as st
import requests
import pandas as pd
import os
import time
from pathlib import Path
import plotly.graph_objects as go

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(layout="wide", page_title="GridSentry AI", initial_sidebar_state="expanded")

if "auto_scan" not in st.session_state: st.session_state.auto_scan = None
if "diag_result" not in st.session_state: st.session_state.diag_result = None
if "pred_history" not in st.session_state:
    st.session_state.pred_history = pd.DataFrame(columns=["ts", "wind_pred", "solar_pred"])

css_path = Path(__file__).resolve().parent / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
else:
    st.warning("style.css not found next to dashboard.py — running with default Streamlit styling.")

st.markdown("""
    <div class="site-header">
        <div>
            <p class="site-title">GridSentry <span>AI</span></p>
            <p class="site-subtitle">Renewable Telemetry &amp; AI Diagnostics</p>
        </div>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Control Panel")
    live_sync = st.toggle("Live Data Sync", value=False)
    st.markdown("---")
    st.markdown('<span class="breaker-tag">CHAOS ENGINEERING</span>', unsafe_allow_html=True)
    st.subheader("Fault Injection")
    chaos_asset = st.selectbox("Target Node", ["wind", "solar"])

    if st.button("Inject Surge & Auto-Analyze", use_container_width=True, type="primary"):
        try:
            inj_resp = requests.post(f"{API_URL}/grid/inject_anomaly/{chaos_asset}", timeout=15)
            if inj_resp.status_code == 200:
                st.success("Surge injected. Initiating auto-scan")
                target_id = "1BY6WEcLGh8j5v7" if chaos_asset == "solar" else "1"
                st.session_state.auto_scan = {"type": chaos_asset, "id": target_id}
                st.rerun()
            else:
                st.error("Injection failed.")
        except requests.exceptions.RequestException as e:
            st.error(f"API error: {e}")

try:
    forecast_resp = requests.get(f"{API_URL}/grid/forecast", timeout=5)
    if forecast_resp.status_code == 200:
        f_data = forecast_resp.json()
        wind_kw = f_data.get("wind_forecast_kw", 0.0)
        solar_kw = f_data.get("solar_forecast_kw", 0.0)
        demand_kw = f_data.get("grid_demand_kw", 0.0)
        status = f_data.get("net_grid_status", "Unknown")
        
        now_ts = pd.Timestamp.now(tz="UTC")
        new_pred = pd.DataFrame([{"ts": now_ts, "wind_pred": wind_kw, "solar_pred": solar_kw}])
        st.session_state.pred_history = pd.concat([st.session_state.pred_history, new_pred]).tail(100)
        
        generation_kw = wind_kw + solar_kw
        span = max(generation_kw, demand_kw, 1.0)
        delta_ratio = (generation_kw - demand_kw) / (2 * span)
        delta_ratio = max(-0.5, min(0.5, delta_ratio))
        fill_left = 50 + min(0, delta_ratio) * 100
        fill_width = abs(delta_ratio) * 100
        fill_color = "var(--stable)" if status == "Surplus" else "var(--alert)"
        status_class = "status-surplus" if status == "Surplus" else "status-deficit"

        st.markdown(f"""
            <div class="balance-meter-wrap">
                <div class="balance-meter-label">
                    <span>Deficit</span><span>Grid Balance</span><span>Surplus</span>
                </div>
                <div class="balance-meter-track">
                    <div class="balance-meter-ticks">{''.join('<div></div>' for _ in range(11))}</div>
                    <div class="balance-meter-zero"></div>
                    <div class="balance-meter-fill" style="left:{fill_left}%; width:{fill_width}%; background:{fill_color};"></div>
                </div>
                <div class="balance-meter-readout">
                    Generation <b>{generation_kw:.2f} kW</b> &nbsp;·&nbsp; Demand <b>{demand_kw:.2f} kW</b>
                    &nbsp;·&nbsp; Status <b class="{status_class}">{status}</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Wind Generation", f"{wind_kw:.2f} kW")
        with m2: st.metric("Solar Generation", f"{solar_kw:.2f} kW")
        with m3: st.metric("Grid Demand", f"{demand_kw:.2f} kW")
        with m4: st.metric("Net Status", status)
    else:
        st.warning("Forecast telemetry offline.")
except requests.exceptions.RequestException:
    st.warning("Forecast telemetry offline.")

st.markdown("---")

try:
    response = requests.get(f"{API_URL}/grid/live", timeout=3)
    if response.status_code == 200:
        grid_data = response.json().get("data", [])
        if grid_data:
            df = pd.DataFrame(grid_data)
            wind_df = df[df["type"] == "wind"].copy()
            solar_df = df[df["type"] == "solar"].copy()

            if not wind_df.empty:
                wind_df["ts"] = pd.to_datetime(wind_df["ts"], utc = True)
            if not solar_df.empty:
                solar_df["ts"] = pd.to_datetime(solar_df["ts"], utc = True)

            if not st.session_state.pred_history.empty:
                st.session_state.pred_history["ts"] = pd.to_datetime(st.session_state.pred_history["ts"], utc=True)

            left_col, right_col = st.columns(2)

            with left_col:
                st.markdown('<p class="panel-eyebrow">Wind Array</p>', unsafe_allow_html=True)
                st.subheader("Wind Generation (Actual vs AI Forecast)")
                if not wind_df.empty:
                    wind_df["raw_wind_kw"] = (wind_df["wind_speed"] ** 3) * 0.85 
                    fig_wind = go.Figure()
                    
                    # 1. Actual historical telemetry
                    fig_wind.add_trace(go.Scatter(
                        x=wind_df["ts"], y=wind_df["raw_wind_kw"],
                        name="Actual Telemetry", mode="lines+markers",
                        line=dict(color="#5B8DB8", width=2.5),
                        marker=dict(size=6)
                    ))
                    
                    # 2. AI Forecast History
                    if not st.session_state.pred_history.empty:
                        fig_wind.add_trace(go.Scatter(
                            x=st.session_state.pred_history["ts"], 
                            y=st.session_state.pred_history["wind_pred"],
                            name="AI Forecast", mode="lines+markers",
                            line=dict(color="#00E5FF", width=2.5, dash="dot"),
                            marker=dict(size=7, symbol="star")
                        ))

                    fig_wind.update_layout(
                        yaxis_title="Power (kW)", template="plotly_dark", 
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
                        margin=dict(l=0, r=0, t=10, b=0),
                        font=dict(family="IBM Plex Mono, monospace", size=11),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_wind, use_container_width=True)
                else:
                    st.caption("No wind telemetry yet.")


            with right_col:
                st.markdown('<p class="panel-eyebrow">Solar Array</p>', unsafe_allow_html=True)
                st.subheader("Solar Generation (Actual vs AI Forecast)")
                if not solar_df.empty:
                    solar_df["raw_solar_kw"] = solar_df["irradiance"] * 2.1 
                    
                    fig_solar = go.Figure()
                    
                    # Actual historical telemetry
                    fig_solar.add_trace(go.Scatter(
                        x=solar_df["ts"], y=solar_df["raw_solar_kw"],
                        name="Actual Telemetry", mode="lines+markers",
                        line=dict(color="#E3A857", width=2.5),
                        marker=dict(size=6)
                    ))

                    # AI Forecast History
                    if not st.session_state.pred_history.empty:
                        fig_solar.add_trace(go.Scatter(
                            x=st.session_state.pred_history["ts"], 
                            y=st.session_state.pred_history["solar_pred"],
                            name="AI Forecast", mode="lines+markers",
                            line=dict(color="#00FF41", width=2.5, dash="dot"),
                            marker=dict(size=7, symbol="star")
                        ))

                    fig_solar.update_layout(
                        yaxis_title="Power (kW)", template="plotly_dark", 
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
                        margin=dict(l=0, r=0, t=10, b=0),
                        font=dict(family="IBM Plex Mono, monospace", size=11),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_solar, use_container_width=True)
                else:
                    st.caption("No solar telemetry yet.")
    else:
        st.info("Live telemetry offline.")
except requests.exceptions.RequestException:
    st.info("Live telemetry offline.")
st.markdown("---")

st.markdown('<p class="panel-eyebrow">Explainable AI</p>', unsafe_allow_html=True)
st.subheader("Diagnostic Center")
diag_col, result_col = st.columns(2)

with diag_col:
    st.caption("Run a SHAP + RAG diagnostic scan against the latest hardware telemetry.")
    selected_asset_type = st.selectbox("Target Hardware", ["wind", "solar"])
    default_id = "1BY6WEcLGh8j5v7" if selected_asset_type == "solar" else "1"
    selected_asset_id = st.text_input("Hardware UID", value=default_id)
    execute_scan = st.button("Run Diagnostic Scan", use_container_width=True, type="primary")

if execute_scan or st.session_state.auto_scan:
    scan_type = st.session_state.auto_scan["type"] if st.session_state.auto_scan else selected_asset_type
    scan_id = st.session_state.auto_scan["id"] if st.session_state.auto_scan else selected_asset_id

    with st.spinner(f"Scanning {scan_type.upper()} node {scan_id}..."):
        try:
            diag_response = requests.post(f"{API_URL}/diagnose/{scan_type}/{scan_id}", timeout=60)
            if diag_response.status_code == 200:
                st.session_state.diag_result = diag_response.json()
            else:
                st.error(f"Inference engine failed ({diag_response.status_code}).")
        except requests.exceptions.RequestException:
            st.error("Network transaction failure.")

    st.session_state.auto_scan = None

with result_col:
    if st.session_state.diag_result:
        res = st.session_state.diag_result
        status_html = (
            '<div class="diag-status status-surplus">STABLE — no anomalies detected</div>'
            if res.get("anomaly_type") == "None"
            else f'<div class="diag-status status-deficit">ANOMALY — {res.get("anomaly_type")}</div>'
        )
        st.markdown(f'<div class="diag-card">{status_html}', unsafe_allow_html=True)
        st.markdown("**RAG resolution blueprint**")
        st.text_area(
            label="rag_blueprint", value=res.get("rag_repair_blueprint", ""),
            height=160, disabled=True, label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.caption("Run a scan to see results here.")

if live_sync:
    time.sleep(3)
    st.rerun()
