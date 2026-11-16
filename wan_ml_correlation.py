
import csv
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parent

BGP_FILE = BASE / "wan_bgp_events.csv"
ML_FILE = BASE / "ml_results.csv"
OUTPUT = BASE / "wan_ml_correlation.csv"

WINDOW = timedelta(minutes=5)

def read_csv(path):
    if not path.exists():
        print(f"File missing: {path.name}")
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except ValueError:
        return None

def ml_time(row):
    for col in ("evaluated_at", "timestamp", "collected_at"):
        result = parse_time(row.get(col))
        if result:
            return result
    return None

def is_anomaly(row):
    # Match only explicit ML anomaly labels.
    for col in ("status", "prediction",
                "anomaly", "anomaly_status",
                "ml_status", "label", "result"):
        value = str(row.get(col, "")).strip().lower()
        if value in ("anomaly", "anomalous", "outlier"):
            return True
    return False

def main():
    bgp_events = read_csv(BGP_FILE)
    ml_rows = read_csv(ML_FILE)

    results = []

    for event in bgp_events:
        event_time = parse_time(event.get("timestamp"))

        matches = []

        if event_time:
            for ml in ml_rows:
                check_time = ml_time(ml)

                if not check_time:
                    continue

                if abs(check_time - event_time) <= WINDOW:
                    if is_anomaly(ml):
                        matches.append(
                            ml.get("router", "UNKNOWN")
                        )

        if event_time is None:
            correlation = "INVALID_EVENT_TIME"
        elif matches:
            correlation = "TEMPORAL_COINCIDENCE"
        else:
            correlation = "NO_CONFIRMED_ML_MATCH"

        results.append({
            "timestamp": event.get("timestamp", ""),
            "wan_router": event.get("router", ""),
            "bgp_peer": event.get("neighbor_ip", ""),
            "bgp_event": event.get("event", ""),
            "ml_anomaly_routers": ",".join(sorted(set(matches))),
            "correlation": correlation,
        })

    fields = [
        "timestamp", "wan_router", "bgp_peer",
        "bgp_event", "ml_anomaly_routers", "correlation"
    ]

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print("\nWAN + ML Correlation Report")
    print("-----------------------------")
    print(f"BGP events processed: {len(bgp_events)}")
    print(f"ML records available: {len(ml_rows)}")
    print(f"Correlated records: {len(results)}")
    for row in results:
        print(
            row["wan_router"],
            row["bgp_event"],
            row["correlation"],
            row["ml_anomaly_routers"]
        )
    print(f"Output saved: {OUTPUT.name}")

if __name__ == "__main__":
    main()
