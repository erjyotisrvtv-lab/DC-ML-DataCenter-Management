from pathlib import Path
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "dc_metrics.csv"
OUTPUT = BASE / "ml_experiment_results.csv"
SUMMARY = BASE / "ml_experiment_summary.csv"

if not SOURCE.exists():
    raise FileNotFoundError(f"Test CSV missing: {SOURCE}")

df = pd.read_csv(SOURCE)

required = ["timestamp", "router", "cpu_percent", "memory_percent"]
missing_columns = [c for c in required if c not in df.columns]
if missing_columns:
    raise ValueError(f"Missing columns: {missing_columns}")

df["router"] = df["router"].astype("string").str.strip()
df["cpu_percent"] = pd.to_numeric(df["cpu_percent"], errors="coerce")
df["memory_percent"] = pd.to_numeric(df["memory_percent"], errors="coerce")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

df = df.dropna(subset=required).copy()
df = df.sort_values(["router", "timestamp"])

# Synthetic test reading: original CSV remains unchanged
leaf = df[df["router"] == "LEAF1"]
if leaf.empty:
    raise ValueError("LEAF1 data not found")

spike = leaf.iloc[-1].to_dict()
spike["timestamp"] = df["timestamp"].max() + pd.Timedelta(seconds=30)
spike["cpu_percent"] = 99.0
spike["memory_percent"] = 95.0
spike["synthetic"] = True

df["synthetic"] = False
df = pd.concat([df, pd.DataFrame([spike])], ignore_index=True)

results = []
summaries = []

for router, group in df.groupby("router"):
    group = group.copy()
    features = ["cpu_percent", "memory_percent"]

    if len(group) < 30:
        print(f"{router}: insufficient samples ({len(group)})")
        continue

    X = StandardScaler().fit_transform(group[features])

    model = IsolationForest(
        n_estimators=150,
        contamination=0.08,
        random_state=42
    )
    model.fit(X)

    group["anomaly_score"] = model.decision_function(X)
    group["anomaly_status"] = [
        "Anomaly" if value == -1 else "Normal"
        for value in model.predict(X)
    ]

    results.append(group)
    summaries.append({
        "router": router,
        "valid_samples": len(group),
        "anomalies": (group["anomaly_status"] == "Anomaly").sum()
    })

    print(f"{router}: {len(group)} samples")

if not results:
    raise ValueError("No router has enough valid samples")

result = pd.concat(results, ignore_index=True)
result.to_csv(OUTPUT, index=False)
pd.DataFrame(summaries).to_csv(SUMMARY, index=False)

test = result[result["synthetic"] == True]

print("\nSYNTHETIC SPIKE RESULT:")
print(test[[
    "timestamp", "router", "cpu_percent",
    "memory_percent", "anomaly_status", "anomaly_score"
]].to_string(index=False))

print("\nExperiment completed.")
print("Original monitoring CSV was not modified.")
