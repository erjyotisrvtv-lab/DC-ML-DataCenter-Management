
import csv
import re
import time
import getpass
from pathlib import Path
from datetime import datetime
from netmiko import ConnectHandler
from archive_metrics import archive_old_rows

ROUTERS = {
    "LEAF1": "192.168.171.10",
    "LEAF2": "192.168.171.11",
    "SPINE1": "192.168.171.12",
    "SPINE2": "192.168.171.13",
}

CSV_FILE = Path("dc_metrics.csv")
FIELDNAMES = [
    "timestamp", "router", "cpu_percent",
    "input_bytes", "output_bytes",
    "memory_percent", "memory_raw"
]


def get_cpu(output):
    match = re.search(
        r"CPU utilization for five seconds:\s*(\d+)%",
        output,
        re.IGNORECASE
    )
    return float(match.group(1)) if match else None


def get_memory(output):
    match = re.search(
        r"^\s*Processor\s+\S+\s+(\d+)\s+(\d+)",
        output,
        re.MULTILINE
    )
    if not match:
        return None
    total = int(match.group(1))
    used = int(match.group(2))
    return round(used / total * 100, 2) if total else None


def get_traffic(output):
    input_match = re.search(
        r"\d+\s+packets input,\s*(\d+)\s+bytes",
        output,
        re.IGNORECASE
    )

    output_match = re.search(
        r"\d+\s+packets output,\s*(\d+)\s+bytes",
        output,
        re.IGNORECASE
    )

    return (
        int(input_match.group(1)) if input_match else None,
        int(output_match.group(1)) if output_match else None
    )

def collect_router(name, ip, password):
    device = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": "admin",
        "password": password,
        "conn_timeout": 15,
    }

    with ConnectHandler(**device) as conn:
        cpu_output = conn.send_command("show processes cpu")
        memory_output = conn.send_command("show memory statistics")
        traffic_output = conn.send_command(
            "show interfaces GigabitEthernet0/0"
        )

    cpu = get_cpu(cpu_output)
    memory = get_memory(memory_output)
    input_bytes, output_bytes = get_traffic(traffic_output)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "router": name,
        "cpu_percent": cpu,
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "memory_percent": memory,
        "memory_raw": " | ".join(memory_output.splitlines()),
    }


def save_rows(rows):
    if not rows:
        return

    # Check existing CSV schema before appending.
    if CSV_FILE.exists() and CSV_FILE.stat().st_size > 0:
        with CSV_FILE.open("r", newline="", encoding="utf-8-sig") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != FIELDNAMES:
            raise ValueError(
                "Existing CSV header does not match collector fields. "
                "Back up and correct the CSV before continuing."
            )

    needs_header = (
        not CSV_FILE.exists()
        or CSV_FILE.stat().st_size == 0
    )

    with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)


def main():
    print("Four-Node Data Center Monitoring")
    password = getpass.getpass("Enter router SSH password: ")

    while True:
        rows = []

        for name, ip in ROUTERS.items():
            try:
                row = collect_router(name, ip, password)
                rows.append(row)
                print(
                    f"{name}: CPU={row['cpu_percent']}% "
                    f"Memory={row['memory_percent']}%"
                )
            except Exception as error:
                print(f"{name}: COLLECTION FAILED - {error}")

        try:
            save_rows(rows)
            print(f"Saved {len(rows)} readings to {CSV_FILE}")
            archive_old_rows()
        except Exception as error:
            print(f"CSV SAVE FAILED: {error}")

        print("Next collection in 30 seconds...\n")
        time.sleep(30)


if __name__ == "__main__":
    main()
