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

# PHASE 2 — routing and ML intelligence, with visible summaries and no tab clicks.
st.divider()
st.subheader('🛡️ Network Intelligence | OSPF & BGP')
st.caption('Discovered peers from the most recent routing snapshot. Missing expected peers require a separate topology inventory.')
# Universal monitored-interface health, with explicitly reviewed UP/UP baseline.
st.subheader('🚨 All-DC Interface & Link Health | 12 Routers')
st.caption('Latest recorded interface states across all routers. Alerts compare against interface_inventory.csv; unmonitored ports do not create false alarms.')
iface = load_optional('interface_health.csv')
inv_path = ROOT / 'interface_inventory.csv'
required_iface = {'router','interface','admin_status','protocol_status','timestamp'}
if iface.empty or not required_iface.issubset(iface.columns):
    st.info('Interface observations unavailable. Start: python .\\auto_routing_monitor.py')
else:
    iface = iface.dropna(subset=['timestamp']).copy()
    iface['interface'] = iface['interface'].astype(str).str.strip()
    iface = iface[iface['router'].isin(ROUTERS)]
    # Latest row per interface; never infer current status from historic snapshots.
    latest_if = iface.sort_values('timestamp').drop_duplicates(['router','interface'], keep='last').copy()
    latest_if['data_center'] = latest_if['router'].str.extract(r'^(DC[123])-')
    latest_if['admin_status'] = latest_if['admin_status'].astype(str).str.lower().str.strip()
    latest_if['protocol_status'] = latest_if['protocol_status'].astype(str).str.lower().str.strip()
    latest_if['age_seconds'] = (pd.Timestamp.now() - latest_if['timestamp']).dt.total_seconds()
    latest_if['fresh'] = latest_if['age_seconds'].between(0,300)
    latest_if['link_up'] = (latest_if['admin_status']=='up') & (latest_if['protocol_status']=='up')
    if inv_path.exists():
        try:
            inventory = pd.read_csv(inv_path).fillna('')
            inventory['router'] = inventory['router'].astype(str).str.strip().str.upper()
            inventory['interface'] = inventory['interface'].astype(str).str.strip()
            inventory = inventory[inventory['monitor'].astype(str).str.lower().str.strip().isin(['yes','true','1'])]
            inventory = inventory.drop_duplicates(['router','interface'],keep='last')
            latest_if = latest_if.merge(inventory[['router','interface']].assign(expected=True), on=['router','interface'],how='left')
            latest_if['expected'] = latest_if['expected'].fillna(False).astype(bool)
            # Expected ports absent from latest readings must be UNKNOWN, not assumed UP.
            missing = inventory[['router','interface']].merge(latest_if[['router','interface']],on=['router','interface'],how='left',indicator=True)
            missing = missing[missing['_merge']=='left_only']
        except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
            st.error(f'Invalid interface_inventory.csv: {exc}')
            latest_if['expected'] = False
            missing = pd.DataFrame()
    else:
        latest_if['expected'] = False
        missing = pd.DataFrame()
        st.warning('No reviewed interface inventory yet. Run `python setup_interface_baseline.py` after restoring intended links; review the generated CSV. Showing observed states only until then.')
    latest_if['health'] = 'UNMONITORED'
    latest_if.loc[latest_if['expected'] & latest_if['fresh'] & latest_if['link_up'], 'health'] = 'UP'
    latest_if.loc[latest_if['expected'] & latest_if['fresh'] & ~latest_if['link_up'], 'health'] = 'DOWN'
    latest_if.loc[latest_if['expected'] & ~latest_if['fresh'], 'health'] = 'STALE'
    scoped = latest_if if dc=='ALL' else latest_if[latest_if['data_center']==dc]
    if router != 'ALL':
        scoped = scoped[scoped['router']==router]
    down = scoped[scoped['health']=='DOWN']
    stale = scoped[scoped['health']=='STALE']
    healthy = scoped[scoped['health']=='UP']
    unmonitored = scoped[scoped['health']=='UNMONITORED']
    a1,a2,a3,a4 = st.columns(4)
    a1.metric('Monitored UP',len(healthy))
    a2.metric('Monitored DOWN',len(down))
    a3.metric('Monitored STALE',len(stale))
    a4.metric('Observed unmonitored',len(unmonitored))
    if not down.empty:
        st.error('🔴 INTERFACE FAILURE: ' + '; '.join(f"{r.router} {r.interface} ({r.admin_status}/{r.protocol_status})" for r in down.itertuples()))
    if not stale.empty:
        st.warning(f'{len(stale)} monitored interface readings are stale (>5 min). Collector may be stopped or router unreachable.')
    if down.empty and stale.empty and not healthy.empty:
        st.success('All freshly observed, monitored interfaces in this view are UP/UP.')
    if not missing.empty:
        missing = missing[missing['router'].str.startswith(dc+'-')] if dc!='ALL' else missing
        if router!='ALL': missing=missing[missing['router']==router]
        if not missing.empty:
            st.warning(f'{len(missing)} inventoried interfaces have no observations; verify collection/inventory.')
            st.dataframe(missing[['router','interface']],use_container_width=True,hide_index=True)
    st.markdown('**All observed interfaces — latest reading**')
    if not scoped.empty:
        display = scoped[['data_center','router','interface','ip_address','admin_status','protocol_status','health','timestamp']].sort_values(['data_center','router','interface'])
        st.dataframe(display.style.map(lambda v: 'color: #fb7185; font-weight: bold' if v=='DOWN' else ('color: #4ade80; font-weight: bold' if v=='UP' else ''),subset=['health']),use_container_width=True,hide_index=True,height=390)
    with st.expander('Interface fault history (most recent 100 observations)'):
        h = iface if dc=='ALL' else iface[iface['data_center']==dc]
        if router!='ALL': h=h[h['router']==router]
        st.dataframe(h.sort_values('timestamp',ascending=False).head(100),use_container_width=True,hide_index=True)
    st.caption('Alert policy: only reviewed baseline interfaces are expected UP. Stale/unreachable data is UNKNOWN, not proof of link UP/DOWN. OSPF/BGP peer-loss inventory is a separate enhancement.')

routing = load_optional('routing_health.csv')
required_routing = {'router','protocol','peer','state','timestamp'}
if routing.empty or not required_routing.issubset(routing.columns):
    st.info('Routing snapshot not available. Run: python .\\routing_collector_3DC.py')
    legacy_ospf = load_optional('ospf_status.csv')
    if not legacy_ospf.empty and 'router' in legacy_ospf.columns:
        with st.expander('Older OSPF evidence (may cover DC1 only)'):
            st.dataframe(legacy_ospf[legacy_ospf['router'].isin(selected['router'].unique())], use_container_width=True, hide_index=True)
else:
    routing = routing[routing['router'].isin(selected['router'].unique())].copy()
    routing = routing.dropna(subset=['timestamp']).sort_values('timestamp')
    routing['protocol'] = routing['protocol'].astype(str).str.strip().str.upper()
    routing['state'] = routing['state'].astype(str).str.strip().str.upper()
    routing = routing.drop_duplicates(['router','protocol','peer'], keep='last')
    if routing.empty:
        st.info('No OSPF/BGP observations for the current router/DC filter.')
    else:
        snap_time = routing['timestamp'].max()
        route_age = pd.Timestamp.now() - snap_time
        route_fresh = pd.Timedelta(0) <= route_age <= pd.Timedelta(minutes=5)
        if not route_fresh:
            st.warning(f'Routing snapshot is not current: {snap_time:%Y-%m-%d %H:%M:%S}. Run routing collector again.')
        ospf = routing[routing['protocol'].eq('OSPF')].copy()
        bgp = routing[routing['protocol'].eq('BGP')].copy()
        ospf_good = int(ospf['state'].str.startswith('FULL').sum())
        bgp_good = int(bgp['state'].eq('ESTABLISHED').sum())
        k1,k2,k3,k4 = st.columns(4)
        k1.metric('OSPF FULL · observed', f'{ospf_good} / {len(ospf)}')
        k2.metric('BGP Established · observed', f'{bgp_good} / {len(bgp)}')
        k3.metric('Routing snapshot', snap_time.strftime('%H:%M:%S'))
        k4.metric('Routing data', 'Current' if route_fresh else 'Stale')
        left_route,right_route=st.columns(2,gap='medium')
        def protocol_panel(df, protocol, healthy, color):
            total=len(df)
            ok=int(healthy.sum()) if total else 0
            fig=go.Figure()
            fig.add_trace(go.Bar(x=[protocol], y=[ok], name='Healthy observed',marker_color=color,text=[ok],textposition='inside'))
            fig.add_trace(go.Bar(x=[protocol], y=[total-ok], name='Other observed',marker_color='#fb7185',text=[total-ok],textposition='inside'))
            fig.update_layout(title=f'{protocol} · observed peer states', barmode='stack',height=265,
                              yaxis_title='Observed peers',legend=dict(orientation='h',y=-0.30))
            fig.update_yaxes(dtick=1,rangemode='tozero')
            st.plotly_chart(style_plot(fig),use_container_width=True)
            if total:
                view=[c for c in ['router','peer','state','detail','timestamp'] if c in df.columns]
                st.dataframe(df[view],use_container_width=True,hide_index=True,height=230)
            else:
                st.info(f'No {protocol} peer rows discovered for this selection.')
        with left_route:
            protocol_panel(ospf,'OSPF',ospf['state'].str.startswith('FULL'),'#34d399')
        with right_route:
            protocol_panel(bgp,'BGP',bgp['state'].eq('ESTABLISHED'),'#38bdf8')
        st.caption('OSPF FULL and BGP Established indicate observed protocol states, not end-to-end service availability. Counts exclude peers missing from collection.')
        with st.expander('Routing collection evidence · all discovered rows'):
            st.dataframe(routing.sort_values(['protocol','router','peer']),use_container_width=True,hide_index=True)

st.divider()
st.subheader('🧠 AI / ML Intelligence | Anomaly Monitoring')
st.caption('ML predictions come from ml_results.csv, generated separately by ml_detection.py. They are not continuously evaluated by this dashboard.')
ml = load_optional('ml_results.csv')
required_ml={'router','anomaly_status'}
if ml.empty or not required_ml.issubset(ml.columns):
    st.info('ML results not available. Run: python .\\ml_detection.py')
else:
    ml = ml[ml['router'].isin(selected['router'].unique())].copy()
    if ml.empty:
        st.info('No ML records for selected routers. Check whether the ML script covers DC2 and DC3.')
    else:
        if 'timestamp' in ml.columns:
            ml=ml.sort_values('timestamp')
            latest_ml=ml.drop_duplicates('router',keep='last')
        else:
            latest_ml=ml.drop_duplicates('router',keep='last')
        flagged_latest=latest_ml['anomaly_status'].astype(str).str.strip().str.lower().eq('anomaly')
        m1,m2,m3,m4=st.columns(4)
        m1.metric('Latest flagged routers',int(flagged_latest.sum()))
        m2.metric('Routers with ML result',f'{latest_ml["router"].nunique()} / {selected["router"].nunique()}')
        m3.metric('Latest ML result',latest_ml['timestamp'].max().strftime('%H:%M:%S') if 'timestamp' in latest_ml and latest_ml['timestamp'].notna().any() else 'Unknown')
        m4.metric('Latest non-flagged',int((~flagged_latest).sum()))
        if 'timestamp' in ml and ml['timestamp'].notna().any():
            latest_ml_time=ml['timestamp'].max()
            ml_age=pd.Timestamp.now()-latest_ml_time
            if not (pd.Timedelta(0)<=ml_age<=pd.Timedelta(minutes=5)):
                st.warning(f'ML results may be stale: latest {latest_ml_time:%Y-%m-%d %H:%M:%S}.')
        ml_left,ml_right=st.columns([1.15,1],gap='medium')
        with ml_left:
            st.markdown('**ML Exception Timeline**')
            if 'timestamp' in ml:
                flagged=ml[ml['anomaly_status'].astype(str).str.strip().str.lower().eq('anomaly')].dropna(subset=['timestamp'])
                if not flagged.empty:
                    fig=px.scatter(flagged,x='timestamp',y='router',color='router',
                                   hover_data=['anomaly_status'],title='Flagged observations by time',color_discrete_sequence=RAINBOW)
                    fig.update_traces(marker=dict(size=12,symbol='diamond'))
                    st.plotly_chart(style_plot(fig),use_container_width=True)
                else:
                    st.info('No anomaly-labeled records in the available ML file.')
            else:
                st.info('Timeline needs a timestamp column in ml_results.csv.')
        with ml_right:
            st.markdown('**Latest Router-Level ML Decisions**')
            show=[c for c in ['timestamp','router','anomaly_status','anomaly_score'] if c in latest_ml.columns]
            st.dataframe(latest_ml[show].sort_values('router'),use_container_width=True,hide_index=True,height=290)
        st.caption('No flagged record does not prove incident-free operation. Validate model training, coverage and anomaly thresholds before making operational claims.')

with st.expander('Latest router-level evidence'):
    st.dataframe(latest[['timestamp','data_center','router','cpu_percent','memory_percent','input_bytes','output_bytes']].sort_values(['data_center','router']),use_container_width=True,hide_index=True)

st.divider()
st.caption('BITS Pilani | Design & Operation of Data Centers | EVE-NG Practical | Metrics are sampled lab evidence, not production SLA measurements')
if refresh:
    time.sleep(30)
    st.rerun()
