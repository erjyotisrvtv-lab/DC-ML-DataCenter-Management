import time
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Distributed Cloud DC | ML Dashboard", page_icon="🌈", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "dc_metrics.csv"
ARCHIVE_DIR = ROOT / "archive"
ML_FILE = ROOT / "ml_results.csv"
ROUTERS = ["LEAF1", "LEAF2", "SPINE1", "SPINE2"]

st.markdown("""
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {background:#05070d !important;color:#e2e8f0 !important;}
section[data-testid="stSidebar"] {background:#101827 !important;}
section[data-testid="stSidebar"] * {color:#f1f5f9 !important;}
h1,h2,h3 {color:#38bdf8 !important;}
[data-testid="stAppViewContainer"] p, [data-testid="stAppViewContainer"] label {color:#e2e8f0;}
div[data-testid="stMetric"] {border-radius:16px;padding:16px 18px;min-height:130px;border:1px solid #263b56;box-shadow:0 8px 20px rgba(0,0,0,.2);}
div[data-testid="stMetric"] * {color:white !important;}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {font-weight:800;}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div:nth-child(4n+1) div[data-testid="stMetric"] {background:linear-gradient(110deg,#ff4366,#ff8059);}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div:nth-child(4n+2) div[data-testid="stMetric"] {background:linear-gradient(110deg,#8053ff,#cf35eb);}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div:nth-child(4n+3) div[data-testid="stMetric"] {background:linear-gradient(110deg,#00b5d8,#2563eb);}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div:nth-child(4n+4) div[data-testid="stMetric"] {background:linear-gradient(110deg,#0bb8a8,#71cc13);}
[data-testid="stDataFrame"] {border:1px solid #263b56;border-radius:10px;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=10, show_spinner=False)
def load_metrics(include_archive):
    paths = []
    if include_archive and ARCHIVE_DIR.exists():
        paths += sorted(ARCHIVE_DIR.glob("*.csv"))
    if DATA_FILE.exists():
        paths.append(DATA_FILE)
    frames = []
    needed = {"timestamp", "router", "cpu_percent", "memory_percent", "input_bytes", "output_bytes"}
    for path in paths:
        try:
            data = pd.read_csv(path, on_bad_lines="skip")
            if needed.issubset(data.columns):
                frames.append(data[list(needed)])
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
    if not frames:
        return pd.DataFrame(columns=sorted(needed))
    data = pd.concat(frames, ignore_index=True)
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    data["router"] = data["router"].astype(str).str.strip().str.upper()
    for col in ["cpu_percent", "memory_percent", "input_bytes", "output_bytes"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["timestamp"])
    data = data[data["router"].isin(ROUTERS)]
    return (data.drop_duplicates(subset=["timestamp", "router"], keep="last")
            .sort_values(["router", "timestamp"]).reset_index(drop=True))

@st.cache_data(ttl=10, show_spinner=False)
def load_ml():
    if not ML_FILE.exists():
        return pd.DataFrame()
    try:
        data = pd.read_csv(ML_FILE)
        if "router" in data.columns:
            data["router"] = data["router"].astype(str).str.upper().str.strip()
        return data
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()

with st.sidebar:
    st.header("🎛️ Dashboard Controls")
    include_archive = st.checkbox("Include archived CSV files", value=True)
    auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=True)
    if st.button("🔄 Refresh now", use_container_width=True):
        load_metrics.clear()
        load_ml.clear()
        st.rerun()
    st.caption("Collector runs separately; dashboard reads saved CSV data.")
    st.divider()
    st.caption("ML predictions update only after running ml_detection.py.")

st.title("🌐 Distributed Cloud Data Center Dashboard")
st.caption("Cisco EVE-NG · CPU · Memory · Network Traffic · ML Insights")

router_choice = st.selectbox("🌐 Select Router", ["ALL"] + ROUTERS, index=1)
metrics = load_metrics(include_archive)
if metrics.empty:
    st.warning("No valid data found. Check dc_metrics.csv and archive folder.")
    st.stop()

selected = metrics if router_choice == "ALL" else metrics[metrics["router"] == router_choice]
if selected.empty:
    st.warning(f"No readings found for {router_choice}.")
    st.stop()

latest = selected.sort_values("timestamp").groupby("router").tail(1)
last_timestamp = selected["timestamp"].max()
st.caption(f"Latest CSV reading: {last_timestamp:%d %b %Y · %H:%M:%S} | Router: {router_choice} | Rows: {len(selected):,}")
if last_timestamp < pd.Timestamp.now() - pd.Timedelta(minutes=5):
    st.warning("Latest data is over 5 minutes old. Check whether multi_collector.py is running and writing new records.")

cpu = latest["cpu_percent"].mean()
mem = latest["memory_percent"].mean()
inbytes = latest["input_bytes"].sum(min_count=1)
outbytes = latest["output_bytes"].sum(min_count=1)

def pct(v):
    return f"{v:.2f}%" if pd.notna(v) else "N/A"

def count(v):
    return f"{int(v):,}" if pd.notna(v) else "N/A"

c1, c2, c3, c4 = st.columns(4)
c1.metric("⚡ CPU Usage", pct(cpu), help="Latest sampled Cisco router CPU percentage")
c2.metric("🧠 Memory Usage", pct(mem), help="Latest sampled Cisco router processor memory percentage")
c3.metric("📥 Input Bytes", count(inbytes), help="Cumulative Gi0/0 input bytes, not a bandwidth rate")
c4.metric("📤 Output Bytes", count(outbytes), help="Cumulative Gi0/0 output bytes, not a bandwidth rate")
if router_choice == "ALL":
    st.caption("ALL view shows average CPU/memory and sums the latest Gi0/0 byte counters across four routers.")

st.subheader("📈 CPU & Memory Trends (%)")
# Draw one or four router lines per metric. Separate the metric names in ALL view.
chart_data = selected.copy()
if router_choice == "ALL":
    long = chart_data.melt(id_vars=["timestamp", "router"], value_vars=["cpu_percent", "memory_percent"], var_name="metric", value_name="percent")
    long["series"] = long["router"] + " · " + long["metric"].str.replace("_percent", "", regex=False).str.upper()
else:
    long = chart_data.melt(id_vars=["timestamp", "router"], value_vars=["cpu_percent", "memory_percent"], var_name="metric", value_name="percent")
    long["series"] = long["metric"].str.replace("_percent", "", regex=False).str.upper()
trend = long.pivot_table(index="timestamp", columns="series", values="percent", aggfunc="last").sort_index()
if trend.empty or trend.notna().sum().sum() == 0:
    st.info("CPU/Memory graph needs valid readings.")
else:
    fig = go.Figure()
    palette = ["#ff4569", "#a855f7", "#38bdf8", "#22c55e", "#f97316", "#eab308", "#2dd4bf", "#f472b6"]
    for i, series in enumerate(trend.columns):
        fig.add_trace(go.Scatter(x=trend.index, y=trend[series], name=str(series),
                                 mode="lines+markers", line=dict(color=palette[i % len(palette)], width=2)))
    fig.update_layout(paper_bgcolor="#1E293B", plot_bgcolor="#1E293B",
                      font=dict(color="#f8fafc"), height=350,
                      xaxis_title="Time", yaxis_title="Utilization (%)",
                      legend=dict(orientation="h", y=1.18),
                      margin=dict(l=45, r=20, t=65, b=35))
    fig.update_xaxes(gridcolor="#475569")
    fig.update_yaxes(gridcolor="#475569")
    st.plotly_chart(fig, use_container_width=True)

# Calculate traffic rate from valid consecutive byte-counter samples.
# Missing samples are excluded before calculating deltas; invalid/reset intervals are ignored.
traffic = metrics.copy().sort_values(["router", "timestamp"])
traffic = traffic.dropna(subset=["input_bytes", "output_bytes"])
traffic["elapsed_seconds"] = traffic.groupby("router")["timestamp"].diff().dt.total_seconds()
for direction in ("input", "output"):
    col = f"{direction}_bytes"
    delta = traffic.groupby("router")[col].diff()
    valid = (traffic["elapsed_seconds"] > 0) & (delta >= 0)
    traffic[f"{direction}_kbps"] = (delta * 8 / traffic["elapsed_seconds"] / 1000).where(valid)
if router_choice != "ALL":
    traffic = traffic[traffic["router"] == router_choice]

st.subheader("📡 Network Traffic Trends (Gi0/0 · Kbps)")
fig_traffic = go.Figure()
for direction, label, color in [("input", "Input Traffic", "#00d4ff"),
                                ("output", "Output Traffic", "#f97316")]:
    for router in sorted(traffic["router"].unique()):
        subset = traffic[traffic["router"] == router].dropna(subset=[f"{direction}_kbps"])
        if not subset.empty:
            legend_name = label if router_choice != "ALL" else f"{router} · {label}"
            fig_traffic.add_trace(go.Scatter(
                x=subset["timestamp"], y=subset[f"{direction}_kbps"],
                name=legend_name, mode="lines+markers",
                line=dict(color=color, width=2),
                opacity=0.85 if router_choice == "ALL" else 1.0))
if fig_traffic.data:
    fig_traffic.update_layout(paper_bgcolor="#1E293B", plot_bgcolor="#1E293B",
                              font=dict(color="#f8fafc"), height=380,
                              xaxis_title="Time", yaxis_title="Traffic (Kbps)",
                              legend=dict(orientation="h", y=1.18),
                              margin=dict(l=45, r=20, t=65, b=35))
    fig_traffic.update_xaxes(gridcolor="#475569")
    fig_traffic.update_yaxes(gridcolor="#475569", rangemode="tozero")
    st.plotly_chart(fig_traffic, use_container_width=True)
else:
    st.info("At least two valid byte-counter readings are needed for a traffic trend.")
st.caption("Traffic rates are derived from cumulative Gi0/0 byte counters; this is historical sampled data.")

st.subheader("🤖 Isolation Forest — ML Anomaly Detection")
ml = load_ml()
if ml.empty or not {"router", "anomaly_status"}.issubset(ml.columns):
    st.info("No valid ML results found. Run: .\\.venv313\\Scripts\\python.exe ml_detection.py")
else:
    ml = ml[ml["router"].isin(ROUTERS)]
    if "timestamp" in ml.columns:
        ml["timestamp"] = pd.to_datetime(ml["timestamp"], errors="coerce")
        ml = ml.sort_values("timestamp").drop_duplicates(subset="router", keep="last")
    if router_choice != "ALL":
        ml = ml[ml["router"] == router_choice]
    if ml.empty:
        st.info("No ML result available for the selected router.")
    else:
        for _, row in ml.iterrows():
            name = row["router"]
            status = str(row["anomaly_status"]).strip()
            samples = row.get("valid_samples", "?")
            if status.lower() == "anomaly":
                st.error(f"🚨 {name}: ANOMALY DETECTED")
            elif status.lower() == "normal":
                st.success(f"✅ {name}: NORMAL")
            else:
                st.warning(f"⏳ {name}: {status} ({samples} valid samples)")
            score = pd.to_numeric(row.get("anomaly_score"), errors="coerce")
            if pd.notna(score):
                st.caption(f"Anomaly score: {score:.4f}")
            recommendation = row.get("recommendation", "")
            if pd.notna(recommendation) and str(recommendation).strip():
                st.write(f"**Recommendation:** {recommendation}")
        st.dataframe(ml, use_container_width=True, hide_index=True)
        if "timestamp" in ml.columns and ml["timestamp"].notna().any():
            ml_time = ml["timestamp"].max()
            st.caption(f"Last ML analysis: {ml_time:%d %b %Y · %H:%M:%S} (offline snapshot)")

with st.expander("📁 Latest raw monitoring records"):
    st.dataframe(selected.sort_values("timestamp", ascending=False).head(100), use_container_width=True, hide_index=True)

st.divider()
st.caption("BITS Pilani · DODC Practical Assignment · EVE-NG + Cisco IOSv + Isolation Forest")

# OSPF Network Health Monitoring
st.subheader("🌐 OSPF Network Health")

ospf_file = ROOT / "ospf_status.csv"

if ospf_file.exists():
    ospf_df = pd.read_csv(ospf_file)

    if not ospf_df.empty:
        ospf_df["timestamp"] = pd.to_datetime(
            ospf_df["timestamp"], errors="coerce"
        )

        latest_ospf = (
            ospf_df.sort_values("timestamp")
            .drop_duplicates("router", keep="last")
        )

        st.dataframe(
            latest_ospf[
                ["router", "ospf_status", "full_neighbors", "timestamp"]
            ],
            use_container_width=True,
            hide_index=True
        )

        if (
            (latest_ospf["ospf_status"] == "FULL").all()
            and (latest_ospf["full_neighbors"] >= 2).all()
        ):
            st.success("All monitored routers have at least 2 FULL OSPF neighbors")
        else:
            st.warning("OSPF monitoring requires attention")
else:
    st.info("Run ospf_monitor.py to collect OSPF status")
# Refresh only after every section has been rendered.
if auto_refresh:
    time.sleep(30)
    st.rerun()
