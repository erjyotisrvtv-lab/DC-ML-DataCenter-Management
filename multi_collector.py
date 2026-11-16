
import os
import re
import csv
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
import keyring
from netmiko import ConnectHandler

# ============================================================
# ML-BASED DISTRIBUTED CLOUD DATA CENTER MANAGEMENT
# 12 DC Routers + 2 ISP Routers
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dc_metrics.csv"

COLLECTION_INTERVAL = 30
RETENTION_HOURS = 24

USERNAME = os.getenv("DC_USERNAME", "admin")
PASSWORD = os.getenv("DC_PASSWORD") or keyring.get_password(
    "DC_ML_Project", USERNAME
)

# ============================================================
# ROUTER INVENTORY
# ============================================================

DC_ROUTERS = {
    "DC1-LEAF1": "192.168.171.10",
    "DC1-LEAF2": "192.168.171.11",
    "DC1-SPINE1": "192.168.171.12",
    "DC1-SPINE2": "192.168.171.13",

    "DC2-SPINE1": "192.168.171.20",
    "DC2-SPINE2": "192.168.171.21",
    "DC2-LEAF1": "192.168.171.22",
    "DC2-LEAF2": "192.168.171.23",

    "DC3-SPINE1": "192.168.171.30",
    "DC3-SPINE2": "192.168.171.33",
    "DC3-LEAF1": "192.168.171.31",
    "DC3-LEAF2": "192.168.171.32",
}

ISP_ROUTERS = {
    "ISP-1": "192.168.171.40",
    "ISP-2": "192.168.171.41",
}

ROUTERS = {**DC_ROUTERS, **ISP_ROUTERS}

# ============================================================
# TRAFFIC MONITORING INTERFACES
# DC routers use Gi0/0 as in the original collector.
# ISP routers use WAN interfaces, not SSH management ports.
# ============================================================

TRAFFIC_INTERFACES = {
    name: "GigabitEthernet0/0" for name in DC_ROUTERS
}

TRAFFIC_INTERFACES.update({
    "ISP-1": "GigabitEthernet0/1",
    "ISP-2": "GigabitEthernet0/0",
})

CSV_FIELDS = [
    "timestamp",
    "router",
    "cpu_percent",
    "input_bytes",
    "output_bytes",
    "memory_percent",
    "memory_raw",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# CPU PARSER
# ============================================================

def parse_cpu(output):
    match = re.search(
        r"five seconds:\s*(\d+)%", output, re.IGNORECASE
    )
    if match:
        return float(match.group(1))

    match = re.search(
        r"one minute:\s*(\d+)%", output, re.IGNORECASE
    )
    if match:
        return float(match.group(1))

    return None


# ============================================================
# MEMORY PARSER
# ============================================================

def parse_memory(output):
    # IOS memory summary, e.g. Processor  Total  Used  Free
    for line in output.splitlines():
        match = re.search(
            r"^\s*Processor\s+"
            r"(?:\S+\s+)?"
            r"(\d+)\s+(\d+)\s+(\d+)",
            line,
            re.IGNORECASE
        )
        if match:
            total = int(match.group(1))
            used = int(match.group(2))
            free = int(match.group(3))

            if total > 0 and used <= total:
                percent = round((used / total) * 100, 2)
                return percent, f"{used}/{total}"

    # Alternate IOS format
    match = re.search(
        r"Processor Pool Total:\s*(\d+)\s+Used:\s*(\d+)",
        output,
        re.IGNORECASE
    )
    if match:
        total = int(match.group(1))
        used = int(match.group(2))

        if total > 0:
            percent = round((used / total) * 100, 2)
            return percent, f"{used}/{total}"

    return None, ""


# ============================================================
# INTERFACE TRAFFIC COUNTERS
# ============================================================

def parse_traffic(output):
    """
    Extract cumulative interface byte counters
    from Cisco IOS show interfaces output.
    """

    input_match = re.search(
        r"(\d+)\s+packets\s+input\s*,\s*([\d,]+)\s+bytes",
        output,
        re.IGNORECASE
    )

    output_match = re.search(
        r"(\d+)\s+packets\s+output\s*,\s*([\d,]+)\s+bytes",
        output,
        re.IGNORECASE
    )

    input_bytes = (
        int(input_match.group(2).replace(",", ""))
        if input_match else None
    )

    output_bytes = (
        int(output_match.group(2).replace(",", ""))
        if output_match else None
    )

    return input_bytes, output_bytes

# ============================================================
# COLLECT SINGLE ROUTER
# ============================================================

def collect_router(router_name, router_ip):

    if router_name in ISP_ROUTERS:
        router_password = keyring.get_password(
            "DC_ML_Project_ISP", router_name
        )
    else:
        router_password = PASSWORD

    if not router_password:
        print(f"{router_name}: SSH password unavailable")
        return None

    device = {
        "device_type": "cisco_ios",
        "host": router_ip,
        "username": USERNAME,
        "password": router_password,
        "conn_timeout": 12,
        "auth_timeout": 12,
        "banner_timeout": 15,
        "fast_cli": False,
    }

    interface = TRAFFIC_INTERFACES.get(
        router_name, "GigabitEthernet0/0"
    )

    try:
        with ConnectHandler(**device) as connection:
            cpu_output = connection.send_command(
                "show processes cpu",
                read_timeout=20
            )

            memory_output = connection.send_command(
                "show memory statistics",
                read_timeout=20
            )

            traffic_output = connection.send_command(
                f"show interfaces {interface}",
                read_timeout=20
            )

        cpu = parse_cpu(cpu_output)
        memory, memory_raw = parse_memory(memory_output)
        input_bytes, output_bytes = parse_traffic(traffic_output)

        if cpu is None and memory is None:
            raise ValueError(
                "CPU and memory parsing both failed"
            )

        row = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "router": router_name,
            "cpu_percent": cpu if cpu is not None else "",
            "input_bytes": (
                input_bytes if input_bytes is not None else ""
            ),
            "output_bytes": (
                output_bytes if output_bytes is not None else ""
            ),
            "memory_percent": (
                memory if memory is not None else ""
            ),
            "memory_raw": memory_raw,
        }

        print(
            f"{router_name} ({router_ip}): "
            f"CPU={cpu}% Memory={memory}% "
            f"Interface={interface}"
        )

        return row

    except Exception as error:
        print(
            f"{router_name} ({router_ip}): "
            f"COLLECTION FAILED - {error}"
        )
        return None


# ============================================================
# CSV STORAGE
# ============================================================

def save_metrics(rows):
    if not rows:
        print("No successful readings to save.")
        return

    file_exists = CSV_FILE.exists()
    needs_header = (
        not file_exists or CSV_FILE.stat().st_size == 0
    )

    with CSV_FILE.open(
        "a", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=CSV_FIELDS
        )

        if needs_header:
            writer.writeheader()

        writer.writerows(rows)

    print(f"Saved {len(rows)} readings to {CSV_FILE.name}")


def cleanup_old_metrics():
    if not CSV_FILE.exists():
        return

    cutoff = datetime.now() - timedelta(
        hours=RETENTION_HOURS
    )

    with CSV_FILE.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames != CSV_FIELDS:
            print(
                "CSV schema differs; cleanup skipped "
                "to protect existing data."
            )
            return

        rows = list(reader)

    retained = []

    for row in rows:
        try:
            timestamp = datetime.fromisoformat(
                row["timestamp"]
            )
            if timestamp >= cutoff:
                retained.append(row)
        except (ValueError, KeyError, TypeError):
            retained.append(row)

    removed = len(rows) - len(retained)

    if removed:
        with CSV_FILE.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file, fieldnames=CSV_FIELDS
            )
            writer.writeheader()
            writer.writerows(retained)

    print(f"Removed {removed} readings older than 24 hours.")


# ============================================================
# MAIN MONITORING LOOP
# ============================================================

def main():
    if not PASSWORD:
        raise RuntimeError(
            "SSH password not found. Configure Windows "
            "Credential Manager for DC_ML_Project/admin "
            "or set DC_PASSWORD."
        )

    print("=" * 60)
    print("MULTI-DATA CENTER & DUAL-ISP MONITORING")
    print("=" * 60)
    print(f"DC Routers: {len(DC_ROUTERS)}")
    print(f"ISP Routers configured: {len(ISP_ROUTERS)}")
    print(f"Total configured monitoring devices: {len(ROUTERS)}")
    print(f"Collection interval: {COLLECTION_INTERVAL} seconds")
    print(f"CSV File: {CSV_FILE}")
    print("=" * 60)

    while True:
        print(
            "\nCollection started:",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        readings = []

        for router_name, router_ip in ROUTERS.items():
            row = collect_router(router_name, router_ip)

            if row:
                readings.append(row)

        save_metrics(readings)
        cleanup_old_metrics()

        print(
            f"\nNext collection in "
            f"{COLLECTION_INTERVAL} seconds..."
        )
        time.sleep(COLLECTION_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
