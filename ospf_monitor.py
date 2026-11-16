
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
import paramiko

BASE = Path(__file__).resolve().parent

ROUTERS = {
    "LEAF1": "192.168.171.10",
    "LEAF2": "192.168.171.11",
    "SPINE1": "192.168.171.12",
    "SPINE2": "192.168.171.13",
}

USERNAME = "admin"
PASSWORD = "LabTest12345"

records = []

for router, ip in ROUTERS.items():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=ip,
            username=USERNAME,
            password=PASSWORD,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )

        stdin, stdout, stderr = ssh.exec_command(
            "show ip ospf neighbor",
            timeout=15
        )
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
        ssh.close()

        if error.strip():
            print(f"{router}: SSH command warning: {error.strip()}")

        matches = re.findall(
            r"^\s*(\d+\.\d+\.\d+\.\d+)\s+\d+\s+"
            r"(FULL/\S+|FULL)\s+",
            output,
            re.MULTILINE
        )

        status = "FULL" if matches else "NO_FULL_NEIGHBOR"

        records.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "router": router,
            "ospf_status": status,
            "full_neighbors": len(matches),
        })

        print(f"{router}: {status} ({len(matches)} FULL neighbors)")

    except Exception as exc:
        records.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "router": router,
            "ospf_status": "COLLECTION_ERROR",
            "full_neighbors": None,
        })
        print(f"{router}: COLLECTION_ERROR - {exc}")

df = pd.DataFrame(records)
output_file = BASE / "ospf_status.csv"
df.to_csv(output_file, index=False)

print(f"\nSaved: {output_file}")
