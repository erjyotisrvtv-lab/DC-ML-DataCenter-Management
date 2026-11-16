from pathlib import Path
from datetime import datetime
import html
import pandas as pd
import altair as alt
import streamlit as st

BASE = Path(__file__).resolve().parent
st.set_page_config(page_title='Distributed Cloud Data Center Dashboard', page_icon='🌈', layout='wide')

st.markdown('''<style>
.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#05070d!important;color:#e2e8f0!important}
[data-testid="stSidebar"]{background:#0e1727!important}
[data-testid="stMainBlockContainer"]{padding-top:1.7rem}
h1,h2,h3{color:#27c9ff!important}
p, label,[data-testid="stCaptionContainer"]{color:#aabbd0!important}
[data-testid="stMetric"]{background:#152237;border:1px solid #34475f;border-radius:13px;padding:14px}
[data-testid="stMetricLabel"]{color:#9fc8fa!important}
[data-testid="stMetricValue"]{color:#f8fafc!important}
[data-testid="stDataFrame"]{border:1px solid #34475f;border-radius:10px}
.stButton button{background:#123252;color:white;border:1px solid #27c9ff;border-radius:10px}
[data-baseweb="select"]>div{background:#101827!important;border:1px solid #27c9ff!important;color:white!important}
.metric-card{border-radius:17px;padding:20px 22px;min-height:120px;color:white;box-shadow:0 8px 20px #0005}
.metric-card .label{font-size:15px;font-weight:500;color:#fff}
.metric-card .value{font-size:32px;font-weight:750;margin-top:8px;color:#fff}
.metric-cpu{background:linear-gradient(110deg,#fc2455,#ff7852)}
.metric-mem{background:linear-gradient(110deg,#7537fc,#ce24df)}
.metric-in{background:linear-gradient(110deg,#00a7db,#2157ed)}
.metric-out{background:linear-gradient(110deg,#0cb9a2,#5dc913)}
.chart-caption{font-size:13px;color:#9fb2c8;margin-top:3px}
</style>''', unsafe_allow_html=True)

st.title('🌈 Distributed Cloud Data Center Dashboard')
st.caption('Cisco EVE-NG · CPU · Memory · Network Traffic · ML Insights · OSPF')

@st.cache_data(ttl=10)
def load_csv(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f'Could not read {path.name}: {exc}')
        return pd.DataFrame()

with st.sidebar:
    st.header('⚙️ Controls')
    include_archive = st.checkbox('Include archived metrics', value=False)
    if st.button('🔄 Refresh data'):
        st.cache_data.clear()
        st.rerun()
    st.caption('Dashboard reads CSV files; it does not collect router data automatically.')

metrics = load_csv(BASE / 'dc_metrics.csv')
if include_archive:
    archive_dir = BASE / 'archive'
    archived = [load_csv(p) for p in sorted(archive_dir.glob('*.csv'))] if archive_dir.exists() else []
    archived = [x for x in archived if not x.empty]
    if archived:
        metrics = pd.concat([metrics, *archived], ignore_index=True).drop_duplicates()

def fmt(value, suffix='', decimals=2):
    value = pd.to_numeric(value, errors='coerce')
    return f'{value:,.{decimals}f}{suffix}' if pd.notna(value) else 'N/A'

def metric_card(label, value, cls, emoji):
    st.markdown(f'<div class="metric-card {cls}"><div class="label">{emoji} {html.escape(label)}</div>'
                f'<div class="value">{html.escape(value)}</div></div>', unsafe_allow_html=True)

def trend_chart(data, fields, names, colors, title, ytitle, domain=None):
    available = [f for f in fields if f in data.columns and data[f].notna().any()]
    if not available:
        st.info(f'No numeric data available for {title}.')
        return
    if 'timestamp' not in data.columns:
        st.info('Timestamp column is needed to plot trends.')
        return
    clean = data[['timestamp'] + available].dropna(subset=['timestamp']).copy()
    if clean.empty:
        st.info('No valid timestamps for this chart.')
        return
    long = clean.melt('timestamp', value_vars=available, var_name='series', value_name='value').dropna(subset=['value'])
    long['series'] = long['series'].map(names)
    color_domain = [names[f] for f in available]
    color_range = [colors[f] for f in available]
    yscale = alt.Scale(domain=domain, zero=True) if domain is not None else alt.Scale(zero=True)
    base = alt.Chart(long).encode(
        x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%H:%M', labelAngle=0, grid=True)),
        y=alt.Y('value:Q', title=ytitle, scale=yscale),
        color=alt.Color('series:N', scale=alt.Scale(domain=color_domain, range=color_range), legend=alt.Legend(title=None, orient='top')),
        tooltip=[alt.Tooltip('timestamp:T', title='Time'), alt.Tooltip('series:N', title='Metric'), alt.Tooltip('value:Q', format='.2f')]
    )
    chart = (base.mark_line(strokeWidth=2.5) + base.mark_point(size=40, filled=True)).properties(
        height=270, background='#1E293B', padding={'left':12,'right':18,'top':10,'bottom':8}
    ).configure_view(stroke='#34475f', cornerRadius=14).configure_axis(
        labelColor='#d6e0ec', titleColor='#d6e0ec', gridColor='#475569', domainColor='#718096', tickColor='#718096'
    ).configure_legend(labelColor='#f1f5f9', titleColor='#f1f5f9', symbolSize=130)
    st.subheader(title)
    st.altair_chart(chart, use_container_width=True, theme=None)

router = None
if not metrics.empty and 'router' in metrics.columns:
    metrics['router'] = metrics['router'].astype(str).str.strip()
    if 'timestamp' in metrics.columns:
        metrics['timestamp'] = pd.to_datetime(metrics['timestamp'], errors='coerce')
    for field in ['cpu_percent','memory_percent','input_bytes','output_bytes','input_mbps','output_mbps']:
        if field in metrics.columns:
            metrics[field] = pd.to_numeric(metrics[field], errors='coerce')
    routers = sorted(metrics['router'].dropna().unique())
    router = st.selectbox('🌐 Select Router', routers)
    subset = metrics[metrics['router'].eq(router)].copy()
    if 'timestamp' in subset.columns:
        subset = subset.sort_values('timestamp')
    latest = subset.iloc[-1]
    last_time = latest.get('timestamp', pd.NaT)
    st.caption(f'Latest CSV reading: {last_time} | Router: {router} | Rows: {len(subset)}')
    if pd.notna(last_time) and pd.Timestamp.now() - last_time > pd.Timedelta(minutes=5):
        st.warning('Latest data is over 5 minutes old. Check whether multi_collector.py is running and writing new records.')
    cards = st.columns(4)
    input_col = 'input_bytes' if 'input_bytes' in subset.columns else 'input_mbps'
    output_col = 'output_bytes' if 'output_bytes' in subset.columns else 'output_mbps'
    with cards[0]: metric_card('CPU Usage', fmt(latest.get('cpu_percent'), '%'), 'metric-cpu', '⚡')
    with cards[1]: metric_card('Memory Usage', fmt(latest.get('memory_percent'), '%'), 'metric-mem', '🧠')
    with cards[2]: metric_card('Input Bytes' if input_col=='input_bytes' else 'Input Traffic', fmt(latest.get(input_col), decimals=0 if input_col=='input_bytes' else 2), 'metric-in', '📥')
    with cards[3]: metric_card('Output Bytes' if output_col=='output_bytes' else 'Output Traffic', fmt(latest.get(output_col), decimals=0 if output_col=='output_bytes' else 2), 'metric-out', '📤')
    st.write('')
    trend_chart(subset, ['cpu_percent','memory_percent'], {'cpu_percent':'CPU Usage (%)','memory_percent':'Memory Usage (%)'},
                {'cpu_percent':'#FF4569','memory_percent':'#A855F7'}, '📈 CPU & Memory Trends (%)', 'Usage (%)', [0,100])
    trend_chart(subset, ['input_mbps','output_mbps'], {'input_mbps':'Input (Mbps)','output_mbps':'Output (Mbps)'},
                {'input_mbps':'#38BDF8','output_mbps':'#34D399'}, '📡 Network Traffic Trends', 'Mbps')
else:
    st.warning('dc_metrics.csv is missing or has no router data. Run multi_collector.py first.')

st.divider()
st.subheader('🤖 ML Anomaly Detection')
ml = load_csv(BASE / 'ml_results.csv')
if not ml.empty and 'router' in ml.columns:
    if 'timestamp' in ml.columns:
        ml['timestamp'] = pd.to_datetime(ml['timestamp'], errors='coerce')
        ml = ml.sort_values('timestamp')
    latest_ml = ml.drop_duplicates('router', keep='last')
    cols = [c for c in ['router','anomaly_status','anomaly_score','valid_samples','timestamp'] if c in latest_ml.columns]
    st.dataframe(latest_ml[cols], use_container_width=True, hide_index=True)
    st.caption('ML flags statistical CPU/memory anomalies; they do not prove a network fault.')
else:
    st.info('No ML results found. Run ml_detection.py.')

st.divider()
st.subheader('🌐 OSPF Network Health')
ospf = load_csv(BASE / 'ospf_status.csv')
if not ospf.empty and 'router' in ospf.columns:
    if 'timestamp' in ospf.columns:
        ospf['timestamp'] = pd.to_datetime(ospf['timestamp'], errors='coerce')
        ospf = ospf.sort_values('timestamp')
    latest_ospf = ospf.drop_duplicates('router', keep='last')
    cols = st.columns(4)
    for col, (_, record) in zip(cols, latest_ospf.head(4).iterrows()):
        with col:
            status = str(record.get('ospf_status', 'UNKNOWN'))
            count = pd.to_numeric(record.get('full_neighbors'), errors='coerce')
            st.metric(str(record['router']), status, f'{int(count)} FULL neighbors' if pd.notna(count) else 'Collection error', delta_color='off')
    visible = [c for c in ['router','ospf_status','full_neighbors','timestamp'] if c in latest_ospf.columns]
    st.dataframe(latest_ospf[visible], use_container_width=True, hide_index=True)
    counts = pd.to_numeric(latest_ospf['full_neighbors'], errors='coerce') if 'full_neighbors' in latest_ospf.columns else pd.Series(dtype=float)
    if len(latest_ospf) == 4 and latest_ospf['ospf_status'].eq('FULL').all() and len(counts)==4 and counts.ge(2).all():
        st.success('All four routers had at least two FULL OSPF neighbors at last collection.')
    else:
        st.warning('OSPF status needs attention. Check collection errors or missing neighbors.')
    st.caption('OSPF status is from the last CSV collection, not a live stream.')
else:
    st.info('No OSPF data found. Run ospf_monitor.py.')
