from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'dc_metrics.csv'
ARCHIVE = BASE / 'archive'
RESULTS = BASE / 'ml_results.csv'
SUMMARY = BASE / 'ml_summary.csv'
ROUTERS = ['LEAF1', 'LEAF2', 'SPINE1', 'SPINE2']
FEATURES = ['cpu_percent', 'memory_percent']
MIN_SAMPLES = 30


def load_data():
    files = sorted(ARCHIVE.glob('dc_metrics_*.csv')) if ARCHIVE.exists() else []
    if SOURCE.exists():
        files.append(SOURCE)
    if not files:
        raise FileNotFoundError('No monitoring CSV files found in project or archive folder.')

    frames = []
    required = {'timestamp', 'router', *FEATURES}
    for file in files:
        try:
            frame = pd.read_csv(file, low_memory=False, on_bad_lines='skip')
            if not required.issubset(frame.columns):
                print(f'Skipping {file.name}: missing required columns')
                continue
            frames.append(frame[['timestamp', 'router', *FEATURES]].copy())
            print(f'Loaded {len(frame)} rows from {file}')
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            print(f'Skipping {file}: {exc}')
    if not frames:
        raise ValueError('No usable monitoring CSV files found.')

    df = pd.concat(frames, ignore_index=True)
    df['router'] = df['router'].astype('string').str.strip().str.upper()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
    df = df.dropna(subset=['timestamp', 'router'])
    df = df[df['router'].isin(ROUTERS)]
    df = df.drop_duplicates(subset=['timestamp', 'router'], keep='last')
    df = df.sort_values(['router', 'timestamp']).reset_index(drop=True)
    print(f'Unique historical + current rows: {len(df)}')
    return df


def main():
    df = load_data()
    results = []
    summaries = []
    injected_time = df['timestamp'].max() + pd.Timedelta(seconds=1)
    print('ML features: CPU and Memory only (traffic excluded)')
    print('Synthetic test: LEAF1 CPU=99%, Memory=95% (not included in model training)')

    for router in ROUTERS:
        baseline = df[df['router'] == router].dropna(subset=FEATURES).copy()
        count = len(baseline)
        if count < MIN_SAMPLES:
            print(f'{router}: Insufficient Data ({count}/{MIN_SAMPLES})')
            summaries.append({'router': router, 'valid_samples': count,
                              'anomalies': 0, 'status': 'Insufficient Data'})
            continue

        model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
        model.fit(baseline[FEATURES])
        baseline['is_synthetic'] = False
        baseline['anomaly_status'] = np.where(model.predict(baseline[FEATURES]) == -1,
                                               'Anomaly', 'Normal')
        baseline['anomaly_score'] = model.decision_function(baseline[FEATURES])
        baseline['valid_samples'] = count
        baseline['recommendation'] = baseline['anomaly_status'].map({
            'Anomaly': 'Investigate unusual CPU/memory readings',
            'Normal': 'Continue monitoring'
        })
        results.append(baseline)

        if router == 'LEAF1':
            synthetic = pd.DataFrame([{
                'timestamp': injected_time, 'router': router,
                'cpu_percent': 99.0, 'memory_percent': 95.0,
                'is_synthetic': True
            }])
            synthetic['anomaly_status'] = np.where(model.predict(synthetic[FEATURES]) == -1,
                                                    'Anomaly', 'Normal')
            synthetic['anomaly_score'] = model.decision_function(synthetic[FEATURES])
            synthetic['valid_samples'] = count
            synthetic['recommendation'] = 'Synthetic test only; not a real router fault'
            results.append(synthetic)
            print('\nSYNTHETIC SPIKE RESULT:')
            print(synthetic[['router', 'cpu_percent', 'memory_percent',
                             'anomaly_status', 'anomaly_score']].to_string(index=False))

        anomaly_count = int((baseline['anomaly_status'] == 'Anomaly').sum())
        print(f'{router}: {count} valid samples; {anomaly_count} baseline anomalies')
        summaries.append({'router': router, 'valid_samples': count,
                          'anomalies': anomaly_count, 'status': 'Trained'})

    pd.DataFrame(summaries).to_csv(SUMMARY, index=False)
    if not results:
        raise RuntimeError('No router had enough valid CPU/memory readings. Check archived CSV data.')

    output = pd.concat(results, ignore_index=True).sort_values('timestamp')
    output = output[['timestamp', 'router', 'cpu_percent', 'memory_percent',
                     'is_synthetic', 'anomaly_status', 'anomaly_score',
                     'valid_samples', 'recommendation']]
    output.to_csv(RESULTS, index=False)
    print(f'\nSaved: {RESULTS.name} and {SUMMARY.name}')
    print('Synthetic experiment is offline and does not indicate a live router fault.')


if __name__ == '__main__':
    main()
