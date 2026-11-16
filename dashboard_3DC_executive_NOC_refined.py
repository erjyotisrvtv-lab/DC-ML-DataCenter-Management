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
    fig.update_layout(paper_bgcolor='#142139',plot_bgcolor='#142139',font=dict(color='#e8f1ff'),height=340,
                      margin=dict(l=45,r=18,t=50,b=55),legend=dict(orientation='h',y=-0.27,x=0,title_text=''),
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
.block-container{padding-top:1.3rem;max-width:1720px}
html,body,[class*=css]{font-size:16px}
[data-testid='stMetricValue']{font-size:1.65rem!important}
[data-testid='stMetricLabel']{font-size:.92rem!important}
[data-testid='stMarkdownContainer'] p{line-height:1.55}
[data-testid='stPlotlyChart']{border:1px solid #304660;border-radius:14px;overflow:hidden}
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
    df = df[df['timestamp'] <= pd.Timestamp.now() + pd.Timedelta(minutes=5)]
    for f in ('cpu_percent','memory_percent'):
        df.loc[~df[f].between(0,100),f] = float('nan')
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
    history_limit = st.selectbox('Trend period', ['Last 30 minutes','Last 2 hours','Last 24 hours','All available'], index=0)
    if st.button('Refresh now',use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption('Read-only dashboard. Data collector and ML analysis run separately. CPU and Memory panels are always visible.')

st.title('🌈 Executive NOC | Distributed Data Center Intelligence')
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
st.caption('KPI scope: latest stored sample per router in the selected DC/router scope. Node count is data coverage, not uptime.')

# PHASE 1 — management-friendly executive performance summary.
st.markdown('#### 🎯 Executive Performance Scorecard')
site_latest = (metrics.sort_values('timestamp').groupby('router').tail(1))
site_latest = site_latest if dc == 'ALL' else site_latest[site_latest['data_center'] == dc]
valid_cpu = site_latest['cpu_percent'].dropna()
valid_mem = site_latest['memory_percent'].dropna()
sc1,sc2,sc3,sc4 = st.columns(4)
sc1.metric('Peak CPU · latest samples', f'{valid_cpu.max():.2f}%' if not valid_cpu.empty else 'N/A')
sc2.metric('Peak Memory · latest samples', f'{valid_mem.max():.2f}%' if not valid_mem.empty else 'N/A')
sc3.metric('Fresh nodes (≤5 min)', f'{int(((pd.Timestamp.now() - site_latest["timestamp"]).between(pd.Timedelta(0), pd.Timedelta(minutes=5))).sum())} / {len(site_latest)}')
sc4.metric('Sites with collected data', str(site_latest['data_center'].nunique()))
st.caption('Peak = maximum of latest router samples (not historical peak). Fresh = reading within 5 minutes of host clock; no uptime/SLA claim.')

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
st.markdown('#### 📊 Latest Data Center CPU & Memory Comparison')
st.caption('Latest recorded average per router, grouped by data center (check freshness indicator above). These are observed utilization values, not alert thresholds.')
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
st.caption('Blue = CPU, Purple = Memory. Both bars use latest sample per router. Historical trends below use the selected time window.')

# Use a common latest timestamp for scope, but do not join disconnected collection sessions.
periods = {'Last 30 minutes': pd.Timedelta(minutes=30),
           'Last 2 hours': pd.Timedelta(hours=2),
           'Last 24 hours': pd.Timedelta(hours=24)}
trend_scope = scoped.copy()
if history_limit in periods:
    cutoff = trend_scope['timestamp'].max() - periods[history_limit]
    trend_scope = trend_scope[trend_scope['timestamp'] >= cutoff]

# Segment series when there is a large polling gap. Plotly must not draw a line
# from an old session to a new session, which can look like a false spike/drop.
def add_gaps(df, group_col, time_col, fields, expected_seconds=30):
    parts=[]
    for _,g in df.groupby(group_col,sort=False):
        g=g.sort_values(time_col).copy()
        gaps=g[time_col].diff().dt.total_seconds().gt(max(180,expected_seconds*5))
        if gaps.any():
            extras=g.loc[gaps].copy()
            extras[time_col]=extras[time_col]-pd.Timedelta(microseconds=1)
            for f in fields: extras[f]=float('nan')
            g=pd.concat([g,extras],ignore_index=True)
        parts.append(g)
    return pd.concat(parts,ignore_index=True).sort_values([group_col,time_col]) if parts else df

st.subheader('📊 Performance Analytics | CPU & Memory')
st.caption(f'CPU and Memory side-by-side · Window: {history_limit} · Gaps between polling sessions are not joined.')
by_dc = trend_scope.copy()
by_dc['minute'] = by_dc['timestamp'].dt.floor('min')
by_dc = by_dc.groupby(['minute','data_center'], as_index=False)[['cpu_percent','memory_percent']].mean()
by_dc = add_gaps(by_dc,'data_center','minute',['cpu_percent','memory_percent'])

def dc_trend(field, title, axis):
    if by_dc.empty or by_dc[field].notna().sum() == 0:
        st.info(f'No {title} data for the selected period.')
        return
    fig = px.line(by_dc, x='minute', y=field, color='data_center', markers=False,
                  color_discrete_map=COLORS,
                  category_orders={'data_center':['DC1','DC2','DC3']})
    fig.update_traces(line_width=3, connectgaps=False)
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
    valid = add_gaps(valid.assign(router=router_focus),'router','timestamp',[field])
    fig.add_trace(go.Scatter(x=valid['timestamp'],y=valid[field], mode='lines',connectgaps=False,
                             name=label,line=dict(color=color,width=3),marker=dict(size=5),
                             fill='tozeroy',fillcolor='rgba(90,120,180,0.08)'))
    fig.update_layout(title=f'{router_focus} · {label}',xaxis_title='Time',yaxis_title=f'{label} (%)',
                      showlegend=False,height=300)
    fig.update_yaxes(rangemode='tozero',ticksuffix='%')
    st.plotly_chart(style_plot(fig),use_container_width=True)
    clean = valid.dropna(subset=[field])
    if not clean.empty:
        st.caption(f'Latest {label.lower()}: **{clean.iloc[-1][field]:.2f}%** · '
                   f'Peak in selected period: **{clean[field].max():.2f}%** · '
                   f'Average: **{clean[field].mean():.2f}%**')

left,right=st.columns(2,gap='medium')
with left:
    router_trend('cpu_percent','CPU','#38bdf8')
with right:
    router_trend('memory_percent','Memory','#a78bfa')

st.subheader('📡 Network Traffic | Input & Output')
st.caption(f'{router_focus} · GigabitEthernet0/0 · Calculated throughput (Kbps) from successive counter readings; not interface capacity')
traffic = scoped[scoped['router'] == router_focus].sort_values('timestamp').copy()
traffic['seconds'] = traffic['timestamp'].diff().dt.total_seconds()
for direction in ('input','output'):
    delta = traffic[f'{direction}_bytes'].diff()
    traffic[f'{direction}_kbps'] = (delta * 8 / traffic['seconds'] / 1000).where(
        (traffic['seconds'].between(5,180)) & (delta >= 0) & traffic[f'{direction}_bytes'].notna())
if history_limit in periods and not traffic.empty:
    cutoff = traffic['timestamp'].max() - periods[history_limit]
    traffic = traffic[traffic['timestamp'] >= cutoff]
traffic = add_gaps(traffic.assign(router=router_focus),'router','timestamp',['input_kbps','output_kbps'])
traffic_long = traffic.melt(id_vars='timestamp',value_vars=['input_kbps','output_kbps'],
                            var_name='direction',value_name='kbps').dropna(subset=['kbps'])
if not traffic_long.empty:
    traffic_long['direction'] = traffic_long['direction'].map({'input_kbps':'Input','output_kbps':'Output'})
    # Retain NaN gap separators so Plotly does not connect disconnected sessions.
    chart_traffic = traffic.melt(id_vars='timestamp',value_vars=['input_kbps','output_kbps'],var_name='direction',value_name='kbps')
    chart_traffic['direction'] = chart_traffic['direction'].map({'input_kbps':'Input','output_kbps':'Output'})
    fig=px.line(chart_traffic,x='timestamp',y='kbps',color='direction',markers=False,
                color_discrete_map={'Input':'#34d399','Output':'#fbbf24'})
    fig.update_traces(line_width=3,connectgaps=False)
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
               'Only 5–180 second valid intervals are used; counter resets and large sampling gaps are excluded. A peak is not automatically an incident.')
else:
    st.info('At least two consecutive valid samples are required for traffic rates. Keep the collector running.')

# PHASE 1 — comparative traffic summary (no extra clicks).
st.markdown('#### 📊 Traffic Summary · selected router')
if not traffic_long.empty:
    traffic_stats = traffic_long.groupby('direction')['kbps'].agg(['mean','max','last']).reindex(['Input','Output'])
    t1,t2,t3,t4 = st.columns(4)
    for widget, direction, statistic, label in [
        (t1,'Input','mean','Average Input'), (t2,'Input','max','Peak Input'),
        (t3,'Output','mean','Average Output'), (t4,'Output','max','Peak Output')]:
        value = traffic_stats.loc[direction,statistic] if direction in traffic_stats.index else float('nan')
        widget.metric(label, f'{value:.2f} Kbps' if pd.notna(value) else 'N/A')
    st.caption('Throughput uses valid 5–180 s consecutive samples and counter deltas. Not interface utilization %. Gaps are not interpolated.')
else:
    st.info('Traffic summary will appear after two valid sequential interface-counter samples.')

st.caption('**Examiner note:** CPU is processor load; memory is used processor memory; '
           'traffic is sampled throughput. Separate panels make trends easy to compare '
           'without confusing utilization (%) with bandwidth (Kbps).')

# PHASE 2 — glanceable routing status near the top of advanced sections.
st.subheader('🗺️ Routing Health at a Glance')
route_preview = load_optional('routing_health.csv')
if not route_preview.empty and {'router','protocol','peer','state','timestamp'}.issubset(route_preview.columns):
    route_preview = route_preview[route_preview['router'].isin(selected['router'].unique())].copy()
    route_preview = route_preview.dropna(subset=['timestamp']).sort_values('timestamp').drop_duplicates(['router','protocol','peer'],keep='last')
    route_preview['protocol'] = route_preview['protocol'].astype(str).str.upper()
    route_preview['state'] = route_preview['state'].astype(str).str.upper()
    os = route_preview[route_preview['protocol']=='OSPF']
    bg = route_preview[route_preview['protocol']=='BGP']
    rc1,rc2,rc3 = st.columns(3)
    rc1.metric('OSPF FULL / observed', f'{int(os["state"].eq("FULL").sum())} / {len(os)}')
    rc2.metric('BGP Established / observed', f'{int(bg["state"].eq("ESTABLISHED").sum())} / {len(bg)}')
    rc3.metric('Latest routing snapshot', route_preview['timestamp'].max().strftime('%H:%M:%S') if not route_preview.empty else 'N/A')
    st.caption('Routing status is from a separate snapshot, not continuous real-time telemetry.')
else:
    st.info('Routing scorecard appears after running routing_collector_3DC.py.')

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

# PHASE 2 — timeline uses actual ML output only, never simulated incidents.
st.markdown('#### 🧠 ML Exception Timeline')
ml_history = load_optional('ml_results.csv')
if not ml_history.empty and {'timestamp','router','anomaly_status'}.issubset(ml_history.columns):
    ml_history = ml_history[ml_history['router'].isin(selected['router'].unique())].dropna(subset=['timestamp']).copy()
    ml_history['is_anomaly'] = ml_history['anomaly_status'].astype(str).str.strip().str.lower().eq('anomaly')
    flagged = ml_history[ml_history['is_anomaly']]
    if not flagged.empty:
        fig = px.scatter(flagged, x='timestamp', y='router', color='router',
                         hover_data=['anomaly_status'], title='Flagged ML observations by router and time',
                         color_discrete_sequence=RAINBOW)
        fig.update_traces(marker=dict(size=11,symbol='diamond'))
        st.plotly_chart(style_plot(fig), use_container_width=True)
    else:
        st.info('No anomaly-labeled rows in the selected ML snapshot. This does not prove that no incidents occurred.')
else:
    st.info('ML timeline requires ml_results.csv with timestamp, router, anomaly_status.')

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
        st.markdown('#### 🧭 Routing Protocol Health · observed peers')
        routing_counts = pd.DataFrame([
            {'Protocol':'OSPF','State':'FULL','Peers':ospf_up},
            {'Protocol':'OSPF','State':'Other','Peers':len(ospf_rows)-ospf_up},
            {'Protocol':'BGP','State':'Established','Peers':bgp_up},
            {'Protocol':'BGP','State':'Other','Peers':len(bgp_rows)-bgp_up},
        ])
        rfig = px.bar(routing_counts, x='Protocol', y='Peers', color='State', barmode='stack',
                      text='Peers', color_discrete_map={'FULL':'#34d399','Established':'#38bdf8','Other':'#fb7185'},
                      title='Observed OSPF and BGP peer states')
        rfig.update_layout(height=300)
        st.plotly_chart(style_plot(rfig), use_container_width=True)
        st.caption('Only discovered peers are shown. A missing expected neighbor requires topology-aware validation.')
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
