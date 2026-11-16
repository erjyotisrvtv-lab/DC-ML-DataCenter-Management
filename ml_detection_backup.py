from pathlib import Path
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'dc_metrics.csv'
RESULTS = BASE / 'ml_experiment_results.csv'
SUMMARY = BASE / 'ml_experiment_summary.csv'
ROUTERS = ['LEAF1', 'LEAF2', 'SPINE1', 'SPINE2']
FEATURES = ['cpu_percent', 'memory_percent']
MIN_READINGS = 30


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f'Missing test CSV: {SOURCE}')

    df = pd.read_csv(SOURCE, low_memory=False)
    required = ['timestamp', 'router', *FEATURES]
    missing_cols = [col for col in required if col not in df.columns]
    if missing_cols:
        raise ValueError(f'Missing CSV columns: {missing_cols}')

    # No .loc assignment into numeric columns: avoids pandas ArrowStringArray
    # empty-assignment dtype errors seen in the original experiment script.
    df['router'] = df['router'].astype('string').str.strip()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    df = df.dropna(subset=['timestamp', 'router']).copy()
    baseline = df[df['router'] == 'LEAF1'].sort_values('timestamp')
    if baseline.empty:
        raise ValueError('No LEAF1 records in test CSV; cannot inject test spike.')

    # Synthetic observation exists only in memory; source CSV stays unchanged.
    injected = baseline.iloc[-1].to_dict()
    injected_time = df['timestamp'].max() + pd.Timedelta(seconds=1)
    injected.update({
        'timestamp': injected_time,
        'router': 'LEAF1',
        'cpu_percent': 99.0,
        'memory_percent': 95.0,
    })
    injected_row = pd.DataFrame([injected])
    df = pd.concat([df, injected_row], ignore_index=True)
    df['is_synthetic'] = False
    df.loc[df.index[-1], 'is_synthetic'] = True

    print(f'Baseline rows: {len(df) - 1}')
    print(f'Synthetic spike: LEAF1 at {injected_time} | CPU 99% | Memory 95%')
    print('ML features: CPU and Memory only (traffic excluded)')

    all_results = []
    summaries = []
    for router in ROUTERS:
        group = df[df['router'] == router].sort_values('timestamp').copy()
        valid = group.dropna(subset=FEATURES).copy()
        count = len(valid)
        if count < MIN_READINGS:
            print(f'{router}: Insufficient Data ({count}/{MIN_READINGS})')
            summaries.append({'router': router, 'valid_samples': count,
                              'anomalies': None, 'status': 'Insufficient Data'})
            continue

        X = StandardScaler().fit_transform(valid[FEATURES])
        model = IsolationForest(n_estimators=150, contamination=0.08, random_state=42)
        model.fit(X)
        valid['anomaly_score'] = model.decision_function(X)
        valid['anomaly_status'] = [
            'Anomaly' if prediction == -1 else 'Normal'
            for prediction in model.predict(X)
        ]
        valid['valid_samples'] = count
        valid['recommendation'] = valid['anomaly_status'].map({
            'Anomaly': 'Investigate unusual CPU/memory readings',
            'Normal': 'Continue monitoring',
        })
        anomalies = int((valid['anomaly_status'] == 'Anomaly').sum())
        print(f'{router}: {count} valid samples; {anomalies} anomalies')
        summaries.append({'router': router, 'valid_samples': count,
                          'anomalies': anomalies, 'status': 'Trained'})
        all_results.append(valid[['timestamp', 'router', 'cpu_percent',
                                  'memory_percent', 'is_synthetic', 'anomaly_status',
                                  'anomaly_score', 'valid_samples', 'recommendation']])

    if not all_results:
        raise RuntimeError('No router had enough valid CPU/memory readings.')

    result = pd.concat(all_results, ignore_index=True)
    result.to_csv(RESULTS, index=False)
    pd.DataFrame(summaries).to_csv(SUMMARY, index=False)

    print('\nSYNTHETIC SPIKE RESULT:')
    spike = result[result['is_synthetic']]
    if spike.empty:
        print('Synthetic spike was not included in ML results.')
    else:
        print(spike[['timestamp', 'router', 'cpu_percent', 'memory_percent',
                     'anomaly_status', 'anomaly_score']].to_string(index=False))
    print(f'\nSaved: {RESULTS.name} and {SUMMARY.name}')
    print('This is an offline synthetic test, not a live router fault.')


if __name__ == '__main__':
    main()
