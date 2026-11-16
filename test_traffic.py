import pandas as pd

df = pd.read_csv("dc_metrics.csv")

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

for col in ["input_bytes", "output_bytes"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(
    subset=["timestamp", "input_bytes", "output_bytes"]
)

df = df.sort_values(["router", "timestamp"])

seconds = df.groupby("router")["timestamp"].diff().dt.total_seconds()

for counter, rate in [
    ("input_bytes", "input_mbps"),
    ("output_bytes", "output_mbps")
]:
    delta = df.groupby("router")[counter].diff()
    df[rate] = delta * 8 / seconds / 1_000_000
    df.loc[(delta < 0) | (seconds <= 0), rate] = float("nan")

print(df.groupby("router")[["input_mbps", "output_mbps"]].count())
print("\nLatest calculated traffic:")
print(df.groupby("router").tail(3)[
    ["timestamp", "router", "input_mbps", "output_mbps"]
].to_string(index=False))
