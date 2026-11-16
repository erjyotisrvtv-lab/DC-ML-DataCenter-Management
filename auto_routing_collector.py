
import subprocess
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
COLLECTOR = ROOT / "routing_collector_3DC_fault_monitor.py"

INTERVAL_SECONDS = 120

logging.basicConfig(
    filename=ROOT / "routing_scheduler.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def run_collector():
    print(f"\n[{datetime.now()}] Routing collection started")

    try:
        result = subprocess.run(
            [sys.executable, str(COLLECTOR)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=110,
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print("[SUCCESS] Routing collection completed")
            logging.info("Routing collection completed")
        else:
            print(f"[ERROR] Exit code: {result.returncode}")
            logging.error(
                "Collector failed: %s",
                result.stderr or result.stdout
            )

    except subprocess.TimeoutExpired:
        print("[ERROR] Collector timed out")
        logging.error("Collector execution timed out")

    except Exception:
        logging.exception("Unexpected scheduler error")
        print("[ERROR] Unexpected scheduler error")


if __name__ == "__main__":
    if not COLLECTOR.is_file():
        sys.exit(f"Collector not found: {COLLECTOR}")

    print("====================================")
    print("AUTOMATED ROUTING HEALTH MONITORING")
    print("12 Routers | 3 Data Centers")
    print("Collection Interval: 2 Minutes")
    print("Press Ctrl+C to stop")
    print("====================================")

    try:
        while True:
            run_collector()
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n[STOPPED] Routing scheduler stopped")

