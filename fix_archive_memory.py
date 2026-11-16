import numpy as np
import pandas as pd
import re
from pathlib import Path

file = Path("archive/dc_metrics_2026-10-13.csv")

df = pd.read_csv(file)

def calculate_memory(raw):
    if pd.isna(raw):
        return np.nan

    match = re.search(
        r"Processor\s+\S+\s+(\d+)\s+(\d+)",
        str(raw)
    )

    if not match:
        return np.nan

    total = int(match.group(1))
    used = int(match.group(2))

    if total <= 0:
        return np.nan

    return round((used / total) * 100, 2)

df["memory_percent"] = pd.to_numeric(
    df["memory_percent"],
    errors="coerce"
)

missing = df["memory_percent"].isna()

df.loc[missing, "memory_percent"] = (
    df.loc[missing, "memory_raw"].apply(calculate_memory)
)

backup = file.with_suffix(".csv.bak")
backup.write_bytes(file.read_bytes())

df.to_csv(file, index=False)

print("Archive memory correction completed.")
print("Backup:", backup)
print(df[["timestamp", "router", "memory_percent"]].to_string(index=False))
