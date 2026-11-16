
import pandas as pd
from pathlib import Path
import shutil

csv_file = Path("dc_metrics.csv")
backup_file = Path("dc_metrics_backup.csv")

if not csv_file.exists():
    print("ERROR: dc_metrics.csv not found")
else:
    # Preserve original data
    shutil.copy2(csv_file, backup_file)

    df = pd.read_csv(csv_file)

    if "memory_percent" not in df.columns:
        df["memory_percent"] = pd.NA

    # Keep existing columns and their order
    columns = list(df.columns)
    columns.remove("memory_percent")

    if "memory_raw" in columns:
        index = columns.index("memory_raw")
        columns.insert(index, "memory_percent")
    else:
        columns.append("memory_percent")

    df = df[columns]
    df.to_csv(csv_file, index=False)

    print("SUCCESS! CSV updated.")
    print("Backup:", backup_file)
    print("Columns:", df.columns.tolist())
