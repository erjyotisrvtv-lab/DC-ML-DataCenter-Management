
import csv
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "wan_bgp_peer_health.csv"
EVENTS = BASE / "wan_bgp_events.csv"

FIELDS = [
    "timestamp", "router", "neighbor_ip",
    "event", "previous_state", "current_state",
    "detected_at"
]

def detect_events():
    with SOURCE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows.sort(key=lambda r: r["timestamp"])

    previous = {}
    events = []

    for row in rows:
        key = (row["router"], row["neighbor_ip"])

        # Do not classify SSH failure as BGP failure.
        if row["collection_status"] != "SUCCESS":
            continue

        current = (
            row["bgp_status"] == "ESTABLISHED"
            and not row["error"]
        )

        if key in previous:
            old = previous[key]

            if old != current:
                event = "RECOVERY" if current else "FAILURE"

                events.append({
                    "timestamp": row["timestamp"],
                    "router": row["router"],
                    "neighbor_ip": row["neighbor_ip"],
                    "event": event,
                    "previous_state": (
                        "HEALTHY" if old else "UNHEALTHY"
                    ),
                    "current_state": (
                        "HEALTHY" if current else "UNHEALTHY"
                    ),
                    "detected_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                })

        previous[key] = current

    with EVENTS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(events)

    print(f"Events detected: {len(events)}")
    for e in events:
        print(
            e["router"], e["neighbor_ip"],
            e["event"], e["timestamp"]
        )

    print(f"Evidence saved: {EVENTS.name}")

if __name__ == "__main__":
    detect_events()
