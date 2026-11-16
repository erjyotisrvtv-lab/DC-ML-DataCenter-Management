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
    fig.update_layout(paper_bgcolor='#142139',plot_bgcolor='#142139',font=dict(color='#e8f1ff'),height=320,
                      margin=dict(l=18,r=18,t=54,b=20),legend=dict(orientation='h',y=-0.35,x=0,title_text=''),
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
    history_limit = st.selectbox('Trend period', ['Last 30 minutes','Last 2 hours','Last 24 hours','All available'], index=2)
    if st.button('Refresh now',use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption('Read-only dashboard. Data collector and ML analysis run separately. CPU and Memory panels are always visible.')

st.title('🌈 Multi-Data Center | Operations Command Center')
st.markdown('''<div class="rainbow-panel"><small>EXECUTIVE OPERATIONS INTELLIGENCE · EVE-NG LAB</small><p>Three Data Centers &nbsp;•&nbsp; 12 Cisco Nodes &nbsp;•&nbsp; Capacity &amp; Traffic &nbsp;•&nbsp; ML Anomaly Insights &nbsp;•&nbsp; OSPF / BGP Routing Health</p></div>''', unsafe_allow_html=True)
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

# Always-visible executive charts directly under the three DC performance cards.
st.markdown('#### 📊 Live Data Center CPU & Memory Comparison')
st.caption('Current average of the latest available reading per router, grouped by data center. These are observed utilization values, not alert thresholds.')
latest_per_router = scoped.sort_values('timestamp').groupby('router', as_index=False).tail(1)
executive_dc = (latest_per_router.groupby('data_center', as_index=False)
                .agg(cpu=('cpu_percent','mean'), memory=('memory_percent','mean'),
                     routers=('router','nunique')))
executive_dc = executive_dc.set_index('data_center').reindex(['DC1','DC2','DC3']).reset_index()

def executive_bar(field, label, color):
    values = executive_dc.dropna(subset=[field])
    if values.empty:
        st.info(f'No {label} samples available.')
        return
    fig = go.Figure(go.Bar(
        x=values['data_center'], y=values[field],
        marker=dict(color=color, line=dict(color='rgba(255,255,255,0.2)', width=1)),
        text=[f'{v:.2f}%' for v in values[field]], textposition='outside',
        hovertemplate='<b>%{x}</b><br>'+label+': %{y:.2f}%<extra></extra>',
        width=0.52))
    ymax = max(12., float(values[field].max()) * 1.4)
    fig.update_layout(title=f'{label} by Data Center', xaxis_title='',
                      yaxis_title='Utilization (%)', height=295,
                      showlegend=False, margin=dict(t=55,b=25,l=35,r=15),
                      bargap=.40)
    fig.update_yaxes(range=[0, min(100., ymax)], ticksuffix='%')
    st.plotly_chart(style_plot(fig), use_container_width=True)

exec_cpu, exec_mem = st.columns(2, gap='medium')
with exec_cpu:
    executive_bar('cpu', 'CPU', '#38bdf8')
with exec_mem:
    executive_bar('memory', 'Memory', '#a78bfa')
st.caption('Blue = average CPU usage · Purple = average memory usage. Historical trend charts remain visible below.')

# Limit the visible trend window without affecting latest KPIs or historical CSVs.
periods = {'Last 30 minutes': pd.Timedelta(minutes=30),
           'Last 2 hours': pd.Timedelta(hours=2),
           'Last 24 hours': pd.Timedelta(hours=24)}
trend_scope = scoped.copy()
if history_limit in periods:
    cutoff = trend_scope['timestamp'].max() - periods[history_limit]
    trend_scope = trend_scope[trend_scope['timestamp'] >= cutoff]

st.subheader('📊 Performance Analytics | CPU & Memory')
st.caption('CPU and Memory are always visible together — no tabs, radio buttons, or extra clicks. DC-level overview is shown first.')
by_dc = trend_scope.copy()
by_dc['minute'] = by_dc['timestamp'].dt.floor('min')
by_dc = by_dc.groupby(['minute','data_center'], as_index=False)[['cpu_percent','memory_percent']].mean()

def dc_trend(field, title, axis):
    if by_dc.empty or by_dc[field].notna().sum() == 0:
        st.info(f'No {title} data for the selected period.')
        return
    fig = px.line(by_dc, x='minute', y=field, color='data_center', markers=True,
                  color_discrete_map=COLORS,
                  category_orders={'data_center':['DC1','DC2','DC3']})
    fig.update_traces(line_width=3, marker_size=5)
    fig.update_layout(title=title, xaxis_title='Time', yaxis_title=axis,
                      legend=dict(orientation='h',y=1.17,x=0), height=315)
    fig.update_yaxes(rangemode='tozero', ticksuffix='%')
    st.plotly_chart(style_plot(fig), use_container_width=True)

cpu_col, mem_col = st.columns(2, gap='medium')
with cpu_col:
    dc_trend('cpu_percent','CPU Utilization by Data Center','CPU (%)')
with mem_col:
    dc_trend('memory_percent','Memory Utilization by Data Center','Memory (%)')

latest_dc = (scoped.sort_values('timestamp').groupby('router').tail(1)
             .groupby('data_center')[['cpu_percent','memory_percent']].mean())
if not latest_dc.empty:
    cpu_top = latest_dc['cpu_percent'].dropna()
    mem_top = latest_dc['memory_percent'].dropna()
    if not cpu_top.empty and not mem_top.empty:
        st.caption(f'**Interpretation:** Highest latest average CPU: {cpu_top.idxmax()} ({cpu_top.max():.2f}%). '
                   f'Highest latest average memory: {mem_top.idxmax()} ({mem_top.max():.2f}%). '
                   'These are utilization comparisons, not fault alerts.')

st.subheader('🖥️ Router Deep Dive | CPU & Memory Side by Side')
router_focus = router if router != 'ALL' else (router_names[0] if router_names else None)
router_focus = st.selectbox('Router to analyze', router_names,
                            index=router_names.index(router_focus) if router_focus in router_names else 0,
                            key='focus_router')
router_history = trend_scope[trend_scope['router'] == router_focus].sort_values('timestamp')

def router_trend(field, label, color):
    valid = router_history.dropna(subset=[field])
    if valid.empty:
        st.info(f'No {label} data for this period.')
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=valid['timestamp'],y=valid[field], mode='lines+markers',
                             name=label,line=dict(color=color,width=3),marker=dict(size=5),
                             fill='tozeroy',fillcolor='rgba(90,120,180,0.08)'))
    fig.update_layout(title=f'{router_focus} · {label}',xaxis_title='Time',yaxis_title=f'{label} (%)',
                      showlegend=False,height=300)
    fig.update_yaxes(rangemode='tozero',ticksuffix='%')
    st.plotly_chart(style_plot(fig),use_container_width=True)
    st.caption(f'Latest {label.lower()}: **{valid.iloc[-1][field]:.2f}%** · '
               f'Peak in selected period: **{valid[field].max():.2f}%**')

left,right=st.columns(2,gap='medium')
with left:
    router_trend('cpu_percent','CPU','#38bdf8')
with right:
    router_trend('memory_percent','Memory','#a78bfa')

st.subheader('📡 Network Traffic | Input & Output')
st.caption(f'{router_focus} · GigabitEthernet0/0 · Actual sampled Kbps, not cumulative byte counts')
traffic = scoped[scoped['router'] == router_focus].sort_values('timestamp').copy()
traffic['seconds'] = traffic['timestamp'].diff().dt.total_seconds()
for direction in ('input','output'):
    delta = traffic[f'{direction}_bytes'].diff()
    traffic[f'{direction}_kbps'] = (delta * 8 / traffic['seconds'] / 1000).where(
        (traffic['seconds'] > 0) & (delta >= 0))
if history_limit in periods and not traffic.empty:
    cutoff = traffic['timestamp'].max() - periods[history_limit]
    traffic = traffic[traffic['timestamp'] >= cutoff]
traffic_long = traffic.melt(id_vars='timestamp',value_vars=['input_kbps','output_kbps'],
                            var_name='direction',value_name='kbps').dropna(subset=['kbps'])
if not traffic_long.empty:
    traffic_long['direction'] = traffic_long['direction'].map({'input_kbps':'Input','output_kbps':'Output'})
    fig=px.line(traffic_long,x='timestamp',y='kbps',color='direction',markers=True,
                color_discrete_map={'Input':'#34d399','Output':'#fbbf24'})
    fig.update_traces(line_width=3,marker_size=5)
    fig.update_layout(title='Interface Throughput Trend',xaxis_title='Time',yaxis_title='Kbps',
                      legend=dict(orientation='h',y=1.17,x=0),height=340)
    fig.update_yaxes(rangemode='tozero')
    st.plotly_chart(style_plot(fig),use_container_width=True)
    last_valid=traffic.dropna(subset=['input_kbps','output_kbps'])
    if not last_valid.empty:
        t=last_valid.iloc[-1]
        x,y=st.columns(2)
        x.metric('Latest Input Rate',f'{t["input_kbps"]:.2f} Kbps')
        y.metric('Latest Output Rate',f'{t["output_kbps"]:.2f} Kbps')
    st.caption('**Interpretation:** Green = received traffic; amber = transmitted traffic. '
               'Rates are derived from consecutive Gi0/0 byte-counter readings. '
               'A traffic peak is not automatically an incident.')
else:
    st.info('At least two consecutive valid samples are required for traffic rates. Keep the collector running.')

st.caption('**Examiner note:** CPU is processor load; memory is used processor memory; '
           'traffic is sampled throughput. Separate panels make trends easy to compare '
           'without confusing utilization (%) with bandwidth (Kbps).')

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

st.subheader('🛡️ 4. Routing & Network Health — OSPF + BGP')
st.caption('OSPF checks internal adjacencies; BGP checks inter-DC/WAN routing sessions. Data comes from routing_health.csv, collected separately over SSH.')
routing = load_optional('routing_health.csv')
if routing.empty or not {'router','protocol','peer','state','timestamp'}.issubset(routing.columns):
    st.info('Routing telemetry not available yet. Run: python routing_collector_3DC.py')
    legacy_ospf = load_optional('ospf_status.csv')
    if not legacy_ospf.empty and 'router' in legacy_ospf.columns:
        st.caption('Legacy OSPF snapshot (may cover only DC1):')
        st.dataframe(legacy_ospf[legacy_ospf['router'].isin(selected['router'].unique())], use_container_width=True, hide_index=True)
else:
    routing = routing[routing['router'].isin(selected['router'].unique())].copy()
    routing['protocol'] = routing['protocol'].astype(str).str.upper()
    routing['state'] = routing['state'].astype(str).str.upper()
    routing = routing.dropna(subset=['timestamp']).sort_values('timestamp')
    routing = routing.drop_duplicates(subset=['router','protocol','peer'],keep='last')
    if routing.empty:
        st.info('No routing observations for the selected routers.')
    else:
        latest_route_time = routing['timestamp'].max()
        stale_route = pd.Timestamp.now() - latest_route_time > pd.Timedelta(minutes=5)
        if stale_route:
            st.warning(f'Routing observations are stale. Latest collection: {latest_route_time:%Y-%m-%d %H:%M:%S}')
        ospf_rows = routing[routing['protocol']=='OSPF']
        bgp_rows = routing[routing['protocol']=='BGP']
        ospf_up = int(ospf_rows['state'].eq('FULL').sum())
        bgp_up = int(bgp_rows['state'].eq('ESTABLISHED').sum())
        x1,x2,x3,x4 = st.columns(4)
        x1.metric('OSPF FULL neighbors', f'{ospf_up} / {len(ospf_rows)}')
        x2.metric('BGP Established peers', f'{bgp_up} / {len(bgp_rows)}')
        x3.metric('OSPF not FULL', int((~ospf_rows['state'].eq('FULL')).sum()))
        x4.metric('BGP not Established', int((~bgp_rows['state'].eq('ESTABLISHED')).sum()))
        st.caption('Counts reflect discovered peer rows, not expected adjacency counts. Missing peers, missing routers and routing failures require separate inventory/collection validation.')
        ospf_tab,bgp_tab = st.tabs(['🔷 OSPF Neighbors','🟣 BGP Peering'])
        with ospf_tab:
            if ospf_rows.empty:
                st.info('No OSPF neighbors reported in the latest routing snapshots.')
            else:
                st.dataframe(ospf_rows[['router','peer','state','detail','timestamp']],use_container_width=True,hide_index=True)
                st.caption('FULL indicates completed OSPF adjacency. Other states can be transient or problematic depending on interface and topology.')
        with bgp_tab:
            if bgp_rows.empty:
                st.info('No BGP neighbors reported. Not all leaf/spine devices necessarily run BGP.')
            else:
                st.dataframe(bgp_rows[['router','peer','state','detail','timestamp']],use_container_width=True,hide_index=True)
                st.caption('Established means the BGP session is up. Verify advertised/received prefixes and end-to-end reachability separately.')
        with st.expander('Routing collection status / raw evidence'):
            st.dataframe(routing.sort_values(['protocol','router','peer']),use_container_width=True,hide_index=True)

with st.expander('Latest router-level evidence'):
    st.dataframe(latest[['timestamp','data_center','router','cpu_percent','memory_percent','input_bytes','output_bytes']].sort_values(['data_center','router']),use_container_width=True,hide_index=True)

st.divider()
st.caption('BITS Pilani | Design & Operation of Data Centers | EVE-NG Practical | Metrics are sampled lab evidence, not production SLA measurements')
if refresh:
    time.sleep(30)
    st.rerun()
