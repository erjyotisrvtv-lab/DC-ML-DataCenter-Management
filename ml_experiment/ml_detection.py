from pathlib import Path
import re
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'dc_metrics.csv'
ARCHIVE = ROOT / 'archive'
OUTPUT = ROOT / 'ml_results.csv'
ROUTERS = ['LEAF1', 'LEAF2', 'SPINE1', 'SPINE2']
MIN_READINGS = 30
FEATURES = ['cpu_percent', 'memory_percent']


def parse_memory(raw):
    if pd.isna(raw):
        return float('nan')
    m = re.search(r'Processor\s+\S+\s+(\d+)\s+(\d+)', str(raw))
    if not m:
        return float('nan')
    total, used = map(int, m.groups())
    return round(100 * used / total, 2) if total else float('nan')


def load_data():
    paths = ([SOURCE] if SOURCE.exists() else [])
    if ARCHIVE.exists():
        paths += sorted(ARCHIVE.glob('dc_metrics_*.csv'))
    frames = []
    for path in paths:
        try:
            frame = pd.read_csv(path, on_bad_lines='warn')
            if {'timestamp', 'router'}.issubset(frame.columns):
                frames.append(frame)
            else:
                print(f'Skipping {path.name}: missing timestamp/router columns')
        except (OSError, pd.errors.ParserError) as exc:
            print(f'Skipping {path.name}: {exc}')
    if not frames:
        raise SystemExit('No readable metrics CSV files found.')
    df = pd.concat(frames, ignore_index=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp', 'router'])
    df['router'] = df['router'].astype(str).str.strip().str.upper()
    df = df.sort_values(['router', 'timestamp']).drop_duplicates(['router', 'timestamp'], keep='last')
    for col in ('cpu_percent', 'memory_percent', 'input_bytes', 'output_bytes'):
        if col not in df.columns:
            df[col] = float('nan')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'memory_raw' in df.columns:
        missing = df['memory_percent'].isna()
        df.loc[missing, 'memory_percent'] = df.loc[missing, 'memory_raw'].apply(parse_memory)
    # Repair historical CSVs where raw memory text was saved in memory_percent.
    if 'memory_raw' in df.columns:
        raw_source = df['memory_raw'].where(df['memory_raw'].notna(), '')
    else:
        raw_source = pd.Series('', index=df.index)
    df['memory_percent'] = df['memory_percent'].fillna(raw_source.apply(parse_memory))
    return df


def add_rates(group):
    group = group.sort_values('timestamp').copy()
    seconds = group['timestamp'].diff().dt.total_seconds()
    for direction in ('input', 'output'):
        delta = group[f'{direction}_bytes'].diff()
        # A reset, negative counter, duplicate timestamp or >10-minute gap
        # should not create a misleading Mbps sample.
        valid = (seconds > 0) & (seconds <= 600) & (delta >= 0)
        group[f'{direction}_mbps'] = (delta * 8 / seconds / 1_000_000).where(valid)
    return group


def main():
    df = load_data()
    results = []
    for router in ROUTERS:
        group = add_rates(df[df['router'] == router])
        valid = group.dropna(subset=FEATURES).copy()
        if len(valid) < MIN_READINGS:
            print(f'{router}: Insufficient Data ({len(valid)}/{MIN_READINGS} valid ML samples)')
            if not group.empty:
                latest = group.iloc[-1]
                results.append({'timestamp': latest['timestamp'], 'router': router,
                                'anomaly_status': 'Insufficient Data', 'anomaly_score': None,
                                'valid_samples': len(valid), 'recommendation': 'Collect more baseline readings'})
            continue
        X = StandardScaler().fit_transform(valid[FEATURES])
        model = IsolationForest(n_estimators=150, contamination=0.08, random_state=42)
        model.fit(X)
        valid['anomaly_score'] = model.decision_function(X)
        valid['anomaly_score'] = model.decision_function(X)
        valid['anomaly_status'] = ['Anomaly' if x == -1 else 'Normal' for x in model.predict(X)]
        valid['valid_samples'] = len(valid)
        valid['recommendation'] = valid['anomaly_status'].map({
            'Anomaly': 'Investigate CPU, memory and interface traffic; verify OSPF/interface health',
            'Normal': 'Continue monitoring'
        })
        results.extend(valid[['timestamp', 'router', 'anomaly_status', 'anomaly_score',
                              'valid_samples', 'recommendation']].to_dict('records'))
        print(f'{router}: {len(valid)} valid samples; {sum(valid.anomaly_status == "Anomaly")} anomalies')
    output = pd.DataFrame(results, columns=['timestamp', 'router', 'anomaly_status',
                                             'anomaly_score', 'valid_samples', 'recommendation'])
    output.to_csv(OUTPUT, index=False)
    print(f'Results saved to {OUTPUT.name} ({len(output)} rows)')
    print('Note: This is offline model analysis; rerun after collecting new data.')


if __name__ == '__main__':
    main()
