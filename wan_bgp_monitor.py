
import csv
import os
import re
import time
import argparse
from datetime import datetime
from pathlib import Path

import keyring
from netmiko import ConnectHandler

# =====================================================
# WAN BGP AUTOMATED MONITORING - DODC TOPIC 8
# =====================================================

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "wan_bgp_peer_health.csv"

USERNAME = "admin"
PASSWORD = keyring.get_password("DC_ML_Project_WAN", USERNAME)

WAN_ROUTERS = {
    "WAN-CORE1": os.getenv("WAN_CORE1_IP", "192.168.171.40"),
    "WAN-CORE2": os.getenv("WAN_CORE2_IP", "192.168.171.41"),
}

# Expected BGP peers and their remote AS numbers.
# Verify WAN-CORE1 peer details from its running BGP summary.
EXPECTED_BGP = {
    "WAN-CORE1": {
        "10.255.0.2": 65100,
    },
    "WAN-CORE2": {
        "10.255.0.1": 65000,
        "172.17.1.2": 65001,
        "172.17.2.2": 65002,
        "172.17.3.2": 65003,
    },
}

FIELDS = [
    "timestamp",
    "router",
    "local_as",
    "neighbor_ip",
    "remote_as",
    "session_type",
    "bgp_status",
    "prefix_count",
    "session_uptime",
    "collection_status",
    "error",
]


def parse_bgp_summary(output):
    """Extract local AS and peer information from Cisco IOS."""

    local_as_match = re.search(
        r"local AS number\s+(\d+)",
        output,
        re.IGNORECASE,
    )

    if not local_as_match:
        raise ValueError("Cannot determine local BGP AS")

    local_as = int(local_as_match.group(1))
    peers = {}

    for line in output.splitlines():
        parts = line.split()

        # Standard IOS BGP summary neighbor row.
        if len(parts) < 10:
            continue

        ip = parts[0]

        if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
            continue

        if parts[1] != "4" or not parts[2].isdigit():
            continue

        remote_as = int(parts[2])
        state = parts[-1]

        # Numeric State/PfxRcd generally indicates
        # an established session in Cisco IOS.
        established = state.isdigit()

        peers[ip] = {
            "remote_as": remote_as,
            "status": "ESTABLISHED" if established else state.upper(),
            "prefix_count": state if established else "",
            "uptime": parts[-2],
        }

    return local_as, peers


def check_router(name, host, timestamp):
    """Connect to one WAN router and check its BGP peers."""

    if not host:
        raise ValueError(f"Missing SSH address for {name}")

    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": USERNAME,
        "password": PASSWORD,
        "use_keys": False,
        "allow_agent": False,
        "conn_timeout": 20,
        "auth_timeout": 20,
        "banner_timeout": 20,
        "read_timeout_override": 30,
    }

    with ConnectHandler(**device) as conn:
        output = conn.send_command("show ip bgp summary")

    local_as, peers = parse_bgp_summary(output)
    rows = []

    for peer_ip, expected_as in EXPECTED_BGP[name].items():

        actual = peers.get(peer_ip)

        if actual is None:
            actual_as = ""
            session_type = ""
            status = "NOT_FOUND"
            prefixes = ""
            uptime = ""
            error = "Expected BGP peer missing"

        else:
            actual_as = actual["remote_as"]
            session_type = (
                "iBGP" if local_as == actual_as else "eBGP"
            )
            status = actual["status"]
            prefixes = actual["prefix_count"]
            uptime = actual["uptime"]

            error = (
                "REMOTE_AS_MISMATCH"
                if actual_as != expected_as
                else ""
            )

        rows.append({
            "timestamp": timestamp,
            "router": name,
            "local_as": local_as,
            "neighbor_ip": peer_ip,
            "remote_as": actual_as,
            "session_type": session_type,
            "bgp_status": status,
            "prefix_count": prefixes,
            "session_uptime": uptime,
            "collection_status": "SUCCESS",
            "error": error,
        })

        print(
            f"{name} | Peer {peer_ip} | "
            f"{session_type or 'UNKNOWN'} | "
            f"{status} | Prefixes: {prefixes or '-'}"
        )

    return rows


def collection_error_rows(name, timestamp, error):
    """Record collection failures without calling them BGP failures."""

    return [
        {
            "timestamp": timestamp,
            "router": name,
            "local_as": "",
            "neighbor_ip": peer_ip,
            "remote_as": "",
            "session_type": "",
            "bgp_status": "UNKNOWN",
            "prefix_count": "",
            "session_uptime": "",
            "collection_status": "ERROR",
            "error": error,
        }
        for peer_ip in EXPECTED_BGP[name]
    ]


def save_csv(rows):
    """Append new evidence without overwriting previous cycles."""

    exists = OUTPUT.exists() and OUTPUT.stat().st_size > 0

    with OUTPUT.open(
        "a", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if not exists:
            writer.writeheader()

        writer.writerows(rows)


def run_collection():
    """Collect one monitoring cycle from both WAN cores."""

    timestamp = datetime.now().isoformat(timespec="seconds")
    rows = []

    print("\n========================================")
    print(f"WAN BGP Monitoring: {timestamp}")
    print("========================================")

    for name, host in WAN_ROUTERS.items():

        try:
            router_rows = check_router(
                name, host, timestamp
            )
            rows.extend(router_rows)

        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            print(f"{name}: COLLECTION_ERROR - {message}")

            rows.extend(
                collection_error_rows(name, timestamp, message)
            )

    save_csv(rows)

    established = sum(
        row["bgp_status"] == "ESTABLISHED"
        and row["collection_status"] == "SUCCESS"
        and not row["error"]
        for row in rows
    )

    print("----------------------------------------")
    print(f"Healthy expected sessions: {established}/{len(rows)}")
    print(f"Evidence saved: {OUTPUT.name}")
    print("----------------------------------------")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Monitoring interval in seconds; 0 = once",
    )
    args = parser.parse_args()

    if not PASSWORD:
        raise RuntimeError(
            "WAN password missing from Windows keyring"
        )

    if args.interval < 0:
        parser.error("Interval cannot be negative")

    try:
        while True:
            run_collection()

            if args.interval == 0:
                break

            print(f"Next cycle in {args.interval} seconds")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nWAN BGP monitoring stopped by user.")


if __name__ == "__main__":
    main()
