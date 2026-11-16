"""Read-only, all-DC Isolation Forest evaluation of dc_metrics.csv.
Run once: python ml_detection_3DC_auto.py
Continuously: python auto_ml_monitor.py
Requires pandas, numpy, scikit-learn. No router configuration changes.
"""
from pathlib import Path
from datetime import datetime
import argparse
import os
import sys
import tempfile

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parent.parent
ROUTERS = [f'DC{dc}-{role}{num}' for dc in (1, 2, 3) for role in ('SPINE', 'LEAF') for num in (1, 2)]
LEGACY = {'LEAF1':'DC1-LEAF1','LEAF2':'DC1-LEAF2','SPINE1':'DC1-SPINE1','SPINE2':'DC1-SPINE2'}
FEATURES = ['cpu_percent','memory_percent','input_kbps','output_kbps']


def load_metrics():
    path = ROOT / 'dc_metrics.csv'
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}; start your existing multi_collector.py first.')
    data = pd.read_csv(path, on_bad_lines='skip', low_memory=False)
    required = {'timestamp','router','cpu_percent','memory_percent','input_bytes','output_bytes'}
    if not required.issubset(data.columns):
        raise ValueError(f'Missing CSV columns: {sorted(required-set(data.columns))}')
    data['router'] = data['router'].astype(str).str.strip().str.upper().replace(LEGACY)
    data['timestamp'] = pd.to_datetime(data['timestamp'], errors='coerce')
    for col in ['cpu_percent','memory_percent','input_bytes','output_bytes']:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    data = data[data.router.isin(ROUTERS)].dropna(subset=['timestamp']).copy()
    data = data[data.timestamp <= pd.Timestamp.now()+pd.Timedelta(minutes=5)]
    for col in ['cpu_percent','memory_percent']:
        data.loc[~data[col].between(0,100),col] = np.nan
    data = data.sort_values(['router','timestamp']).drop_duplicates(['router','timestamp'],keep='last')
    for field in ['input','output']:
        delta = data.groupby('router')[f'{field}_bytes'].diff()
        seconds = data.groupby('router')['timestamp'].diff().dt.total_seconds()
        # Counter resets, gaps, and bad intervals must not be treated as spikes.
        valid = delta.ge(0) & seconds.between(5,300)
        data[f'{field}_kbps'] = ((delta*8)/(seconds*1000)).where(valid)
    return data


def evaluate(data, min_samples=20, contamination=0.05):
    rows = []
    evaluated_at = datetime.now().isoformat(timespec='seconds')
    for router in ROUTERS:
        subset = data[data.router.eq(router)].tail(300).copy()
        if subset.empty:
            rows.append(dict(timestamp=evaluated_at, router=router, anomaly_status='NO_DATA', anomaly_score=np.nan,
                             anomaly_reason='No metric samples', samples_used=0, model_scope='none', evaluated_at=evaluated_at))
            continue
        # Do not treat missing throughput as zero; use resource-only features until traffic deltas exist.
        usable = [c for c in FEATURES if subset[c].notna().sum() >= min_samples]
        train = subset.dropna(subset=usable) if usable else pd.DataFrame()
        latest = subset.iloc[-1]
        base = dict(timestamp=latest.timestamp.isoformat(),router=router,anomaly_score=np.nan,
                    samples_used=len(train),model_scope='per-router',evaluated_at=evaluated_at,
                    cpu_percent=latest.cpu_percent,memory_percent=latest.memory_percent,
                    input_kbps=latest.input_kbps,output_kbps=latest.output_kbps)
        if not usable or len(train)<min_samples or latest[usable].isna().any():
            rows.append({**base,'anomaly_status':'INSUFFICIENT_DATA',
                         'anomaly_reason':f'Need {min_samples} valid samples and a current reading; have {len(train)}'})
            continue
        x = train[usable].astype(float)
        # A constant feature adds no useful anomaly information.
        usable = [c for c in usable if x[c].nunique()>1]
        if not usable:
            rows.append({**base,'anomaly_status':'INSUFFICIENT_DATA','anomaly_reason':'No varying numeric features'})
            continue
        model = IsolationForest(n_estimators=100,contamination=contamination,random_state=42,n_jobs=1)
        model.fit(x[usable])
        sample = latest[usable].astype(float).to_frame().T
        score = float(model.decision_function(sample)[0])
        flag = int(model.predict(sample)[0]) == -1
        reason = 'No anomaly flagged'
        if flag:
            deviations=[]
            for feature in usable:
                center=float(x[feature].median())
                spread=float((x[feature]-center).abs().median())
                if spread <= 1e-9:
                    spread=float(x[feature].std())
                if spread > 1e-9:
                    deviations.append((abs(float(latest[feature])-center)/spread,feature,float(latest[feature]),center))
            if deviations:
                _, feature, value, center = max(deviations)
                reason=f'Largest relative deviation: {feature}={value:.3f} (baseline median {center:.3f}); indicative, not causal proof'
            else:
                reason='Unusual multivariate pattern; root cause not established'
        rows.append({**base,'anomaly_status':'Anomaly' if flag else 'Normal',
                     'anomaly_score':round(score,6),'anomaly_reason':reason,
                     'features_used':', '.join(usable)})
    return pd.DataFrame(rows)


def atomic_write(df, path):
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',suffix='.csv',prefix='.ml_',dir=ROOT,delete=False) as handle:
        tmp=Path(handle.name)
        df.to_csv(handle,index=False)
    try:
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--min-samples',type=int,default=20)
    p.add_argument('--contamination',type=float,default=0.05)
    args=p.parse_args()
    if args.min_samples<10 or not 0<args.contamination<=0.5:
        p.error('Use min-samples >=10 and contamination in (0,0.5]')
    data=load_metrics()
    output=evaluate(data,args.min_samples,args.contamination)
    # Latest router-level snapshot; do not append duplicates every polling cycle.
    atomic_write(output,ROOT/'ml_results.csv')
    counts=output.anomaly_status.value_counts().to_dict()
    print(f'[{datetime.now():%H:%M:%S}] ML evaluated {len(output)} routers: {counts}',flush=True)
    print(output[['router','anomaly_status','anomaly_score','anomaly_reason']].to_string(index=False),flush=True)

if __name__=='__main__':
    try:
        main()
    except (FileNotFoundError,ValueError,pd.errors.ParserError) as exc:
        print(f'[ERROR] {exc}',file=sys.stderr)
        sys.exit(1)
