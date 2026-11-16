
import pandas as pd
import re
import shutil
from pathlib import Path

file = Path("dc_metrics.csv")
backup = Path("dc_metrics_before_memory_fix.csv")

# Stop collector and close Excel before running
shutil.copy2(file, backup)

df = pd.read_csv(file)

def extract_memory(raw):
    if pd.isna(raw):
        return None

    match = re.search(
        r"Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)",
        str(raw)
    )

    if not match:
        return None

    total = int(match.group(1))
    used = int(match.group(2))

    return round(used / total * 100, 2) if total else None

# Recover raw memory saved in wrong column
mask = df["memory_raw"].isna() & df["memory_percent"].astype(str).str.contains(
    "Processor", na=False
)

df.loc[mask, "memory_raw"] = df.loc[mask, "memory_percent"]

# Calculate percentage from recovered raw data
df["memory_percent"] = df["memory_raw"].apply(extract_memory)

df.to_csv(file, index=False)

print("SUCCESS! Memory columns corrected.")
print(df[["timestamp", "memory_percent"]].tail())
