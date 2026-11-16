"""Executive multi-data-center operations dashboard. Run: streamlit run dashboard_3DC_executive.py"""
from pathlib import Path
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Rainbow | Multi-DC Command Center', page_icon='🌈', layout='wide')
ROOT = Path(__file__).resolve().parent
ROUTERS = {f'DC{d}-{role}{i}' for d in (1, 2, 3) for role in ('SPINE', 'LEAF') for i in (1, 2)}
LEGACY = {'LEAF1':'DC1-LEAF1','LEAF2':'DC1-LEAF2','SPINE1':'DC1-SPINE1','SPINE2':'DC1-SPINE2'}
COLORS = {'DC1':'#38bdf8','DC2':'#a78bfa','DC3':'#34d399'}
RAINBOW = ['#38bdf8','#a78bfa','#34d399','#fb7185','#fbbf24','#22d3ee','#f472b6','#c4b5fd','#86efac','#fdba74','#60a5fa','#e879f9']
def style_plot(fig):
    fig.update_layout(paper_bgcolor='#142139',plot_bgcolor='#142139',font=dict(color='#e8f1ff'),height=350,
                      margin=dict(l=18,r=18,t=54,b=20),legend=dict(orientation='h',y=-0.26),
                      title_font=dict(size=16,color='#e8f1ff'),hovermode='x unified')
    fig.update_xaxes(gridcolor='#30415c',zerolinecolor='#30415c')
    fig.update_yaxes(gridcolor='#30415c',zerolinecolor='#30415c')
    return fig
st.markdown("""<style>
.stApp{background:radial-gradient(ellipse at 90% 0%,#19254a 0%,#0b1220 42%,#080d18 100%);color:#e2e8f0}
.stApp:before{content:'';position:fixed;top:0;left:0;right:0;height:5px;z-index:9999;background:linear-gradient(90deg,#ff4569,#ffab43,#f7db56,#32d399,#24c6ff,#8165ff,#d954ef)}
[data-testid="stSidebar"]{background:#101a2c;border-right:1px solid #2a3b53}
[data-testid="stMetric"]{background:linear-gradient(135deg,#182943,#142139);border:1px solid #34445f;border-radius:16px;padding:16px;box-shadow:0 10px 22px #0004;min-height:120px}
[data-testid="stMetricLabel"]{color:#bdd0e8!important;font-weight:600}
[data-testid="stMetricValue"]{color:#ffffff!important;font-weight:800}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div:nth-child(5n+1) [data-testid="stMetric"]{border-top:4px solid #ff5d78}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div:nth-child(5n+2) [data-testid="stMetric"]{border-top:4px solid #a88bff}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div:nth-child(5n+3) [data-testid="stMetric"]{border-top:4px solid #32d6e9}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div:nth-child(5n+4) [data-testid="stMetric"]{border-top:4px solid #f5c85d}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div:nth-child(5n+5) [data-testid="stMetric"]{border-top:4px solid #45dc9b}
h1{background:linear-gradient(90deg,#60d6ff,#a994ff,#ff7aab);background-clip:text;-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:850!important}
h2,h3{color:#eaf4ff!important}
.block-container{padding-top:1.8rem;max-width:1600px}
[data-testid="stDataFrame"]{border:1px solid #304660;border-radius:13px}
.stButton button{background:linear-gradient(95deg,#2660a5,#7045b9);color:white;border:1px solid #6d91d2;border-radius:10px}
[data-testid="stAlert"]{border-radius:12px}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#26bff2,#8d72ff,#39d69b)!important}
.rainbow-panel{padding:14px 20px;background:linear-gradient(110deg,#192b47,#202146 48%,#182f3c);border:1px solid #3b4c70;border-radius:15px;margin:4px 0 18px}
.rainbow-panel small{color:#b5c8e0;letter-spacing:.11em;font-weight:650}
.rainbow-panel p{margin:7px 0 0;color:#d4e3f6}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=10)
def load_metrics(include_archive):
    paths = [ROOT/'dc_metrics.csv']
    if include_archive and (ROOT/'archive').exists():
        paths += sorted((ROOT/'archive').glob('*.csv'))
    frames = []
    needed = {'timestamp','router','cpu_percent','memory_percent','input_bytes','output_bytes'}
    for path in paths:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, on_bad_lines='skip')
            if needed.issubset(frame.columns):
                frames.append(frame[list(needed)].copy())
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
    if not frames:
        return pd.DataFrame(columns=sorted(needed))
    df = pd.concat(frames, ignore_index=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['router'] = df['router'].astype(str).str.strip().str.upper().replace(LEGACY)
    for field in ('cpu_percent','memory_percent','input_bytes','output_bytes'):
        df[field] = pd.to_numeric(df[field], errors='coerce')
    df = df[df['router'].isin(ROUTERS)].dropna(subset=['timestamp']).copy()
    df['data_center'] = df['router'].str.extract(r'^(DC[123])-')
    return df.drop_duplicates(subset=['router','timestamp'],keep='last').sort_values(['router','timestamp'])

@st.cache_data(ttl=10)
def load_optional(name):
    path = ROOT/name
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, on_bad_lines='skip')
        if 'router' in df:
            df['router'] = df['router'].astype(str).str.strip().str.upper().replace(LEGACY)
        if 'timestamp' in df:
            df['timestamp'] = pd.to_datetime(df['timestamp'],errors='coerce')
        return df
    except (OSError,ValueError,pd.errors.ParserError,pd.errors.EmptyDataError):
        return pd.DataFrame()

with st.sidebar:
    st.markdown('### 🌈 Command Center Controls')
    dc = st.selectbox('Data Center', ['ALL','DC1','DC2','DC3'])
    include_archive = st.checkbox('Include archived readings', value=False)
    refresh = st.checkbox('Auto-refresh (30 sec)',value=True)
    if st.button('Refresh now',use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption('Read-only dashboard. Data collector and ML analysis run separately.')

st.title('🌈 Multi-Data Center | Operations Command Center')
st.markdown('''<div class="rainbow-panel"><small>EXECUTIVE OPERATIONS INTELLIGENCE · EVE-NG LAB</small><p>Three Data Centers &nbsp;•&nbsp; 12 Cisco Nodes &nbsp;•&nbsp; Capacity &amp; Traffic &nbsp;•&nbsp; ML Anomaly Insights &nbsp;•&nbsp; OSPF Health</p></div>''', unsafe_allow_html=True)
metrics = load_metrics(include_archive)
if metrics.empty:
    st.error('No valid monitoring readings found. Put this file beside dc_metrics.csv and run multi_collector.py.')
    st.stop()
scoped = metrics if dc == 'ALL' else metrics[metrics['data_center']==dc]
router_names = sorted(scoped['router'].unique())
router = st.sidebar.selectbox('Router', ['ALL'] + router_names)
selected = scoped if router == 'ALL' else scoped[scoped['router']==router]
if selected.empty:
    st.warning('No readings for this selection.')
    st.stop()
latest = selected.sort_values('timestamp').groupby('router').tail(1)
latest_time = latest['timestamp'].max()
now = pd.Timestamp.now()
age = now - latest_time
fresh = pd.notna(age) and pd.Timedelta(0) <= age <= pd.Timedelta(minutes=5)
if not fresh:
    st.warning(f'Stale or future-dated readings: latest sample {latest_time:%Y-%m-%d %H:%M:%S}. Check collector and host clock.')

n1,n2,n3,n4,n5 = st.columns(5)
n1.metric('Routers with data',f'{latest["router"].nunique()} / {4 if dc != "ALL" else 12}')
n2.metric('Avg CPU',f'{latest["cpu_percent"].mean():.2f}%' if latest['cpu_percent'].notna().any() else 'N/A')
n3.metric('Avg Memory',f'{latest["memory_percent"].mean():.2f}%' if latest['memory_percent'].notna().any() else 'N/A')
n4.metric('Latest sample',latest_time.strftime('%H:%M:%S'))
n5.metric('Data freshness','Current' if fresh else 'Stale')
st.caption('Node count represents routers with stored readings, not independently verified availability. CPU/memory averages use latest recorded sample per router.')

st.subheader('🏢 Data Center Performance Overview')
summary = (scoped.sort_values('timestamp').groupby('router').tail(1)
           .groupby('data_center').agg(routers=('router','nunique'),cpu=('cpu_percent','mean'),memory=('memory_percent','mean')).reset_index())
cols = st.columns(3)
for i, dcname in enumerate(['DC1','DC2','DC3']):
    record = summary[summary['data_center']==dcname]
    with cols[i]:
        if not record.empty:
            r = record.iloc[0]
            st.markdown(f'**{dcname}** · {int(r["routers"])} routers with data')
            st.progress(min(1.,max(0.,float(r['cpu'])/100)) if pd.notna(r['cpu']) else 0.,text=f'CPU {r["cpu"]:.2f}%')
            st.progress(min(1.,max(0.,float(r['memory'])/100)) if pd.notna(r['memory']) else 0.,text=f'Memory {r["memory"]:.2f}%')
        else:
            st.markdown(f'**{dcname}** · No readings in selection')

st.subheader('📈 Utilization & Capacity Trends')
left,right = st.columns(2)
with left:
    fig = px.line(selected, x='timestamp',y='cpu_percent',color='router',title='CPU utilization (%)',markers=True, color_discrete_sequence=RAINBOW)
    fig.update_yaxes(rangemode='tozero')
    st.plotly_chart(style_plot(fig),use_container_width=True)
with right:
    fig = px.line(selected,x='timestamp',y='memory_percent',color='router',title='Memory utilization (%)',markers=True, color_discrete_sequence=RAINBOW)
    fig.update_yaxes(rangemode='tozero')
    st.plotly_chart(style_plot(fig),use_container_width=True)

st.subheader('🌐 Network Throughput | Gi0/0')
traffic = selected.sort_values(['router','timestamp']).copy()
traffic['seconds'] = traffic.groupby('router')['timestamp'].diff().dt.total_seconds()
for direction in ('input','output'):
    delta = traffic.groupby('router')[f'{direction}_bytes'].diff()
    traffic[f'{direction}_kbps'] = (delta * 8 / traffic['seconds'] / 1000).where((traffic['seconds']>0)&(delta>=0))
long = traffic.melt(id_vars=['timestamp','router'],value_vars=['input_kbps','output_kbps'],var_name='direction',value_name='kbps').dropna(subset=['kbps'])
if long.empty:
    st.info('At least two consecutive valid byte-counter readings are required for throughput.')
else:
    fig = px.line(long,x='timestamp',y='kbps',color='router',line_dash='direction',title='Calculated throughput (Kbps)',color_discrete_sequence=RAINBOW)
    fig.update_yaxes(rangemode='tozero')
    st.plotly_chart(style_plot(fig),use_container_width=True)
st.caption('Kbps derived from counter deltas; negative/reset intervals excluded. Counters are cumulative, not instantaneous bandwidth.')

st.subheader('🤖 AI / ML | Anomaly Detection')
ml = load_optional('ml_results.csv')
if ml.empty or not {'router','anomaly_status'}.issubset(ml.columns):
    st.info('ML output not available. Run ml_detection.py to generate ml_results.csv.')
else:
    ml = ml[ml['router'].isin(selected['router'].unique())].copy()
    if 'timestamp' in ml:
        ml = ml.sort_values('timestamp').drop_duplicates('router',keep='last')
    if ml.empty:
        st.info('No ML result for selected routers. Existing model may still cover only old DC1 labels.')
    else:
        anomalies = ml['anomaly_status'].astype(str).str.strip().str.lower().eq('anomaly').sum()
        st.metric('Latest flagged anomalies',int(anomalies))
        st.dataframe(ml,use_container_width=True,hide_index=True)
        st.caption('ML predictions are offline snapshots, not live alerts. Interpret only after validating model training and sample coverage.')

st.subheader('🛡️ Routing & Network Health | OSPF')
ospf = load_optional('ospf_status.csv')
if ospf.empty or 'router' not in ospf.columns:
    st.info('No OSPF status file found. Run ospf_monitor.py.')
else:
    ospf = ospf[ospf['router'].isin(selected['router'].unique())].copy()
    if 'timestamp' in ospf:
        ospf = ospf.sort_values('timestamp').drop_duplicates('router',keep='last')
    if ospf.empty:
        st.info('No OSPF results for the selected routers.')
    else:
        st.dataframe(ospf,use_container_width=True,hide_index=True)
        st.caption('OSPF neighbor expectations vary by topology; review per-node adjacency counts before interpreting health.')

with st.expander('Latest router-level evidence'):
    st.dataframe(latest[['timestamp','data_center','router','cpu_percent','memory_percent','input_bytes','output_bytes']].sort_values(['data_center','router']),use_container_width=True,hide_index=True)

st.divider()
st.caption('BITS Pilani | Design & Operation of Data Centers | EVE-NG Practical | Metrics are sampled lab evidence, not production SLA measurements')
if refresh:
    time.sleep(30)
    st.rerun()
