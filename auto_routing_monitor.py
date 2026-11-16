"""Continuously run the existing read-only 3-DC routing/interface collector.

Usage: python auto_routing_monitor.py
Stop: Ctrl+C. Keeps using existing keyring credentials and CSV schema.
"""
from datetime import datetime
from pathlib import Path
import argparse
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
COLLECTOR = ROOT / 'routing_collector_3DC_fault_monitor.py'


def main():
    parser = argparse.ArgumentParser(description='Automatic interface, OSPF and BGP polling')
    parser.add_argument('--interval', type=int, default=30, help='Minimum seconds between collection START times (default 30)')
    args = parser.parse_args()
    if args.interval < 10:
        parser.error('Use an interval of at least 10 seconds to avoid excessive SSH polling')
    if not COLLECTOR.is_file():
        parser.error(f'Missing collector in same folder: {COLLECTOR.name}')
    print(f'Automatic 3-DC monitor started | interval target: {args.interval}s | Ctrl+C to stop', flush=True)
    try:
        while True:
            start = time.monotonic()
            print(f'\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Starting 12-router polling cycle...', flush=True)
            try:
                result = subprocess.run([sys.executable, str(COLLECTOR)], cwd=str(ROOT), check=False)
                if result.returncode:
                    print(f'[WARNING] Collector exited with code {result.returncode}; will retry next cycle.', flush=True)
            except OSError as exc:
                print(f'[WARNING] Could not start collector: {exc}', flush=True)
            elapsed = time.monotonic() - start
            wait = max(0, args.interval - elapsed)
            print(f'Cycle duration: {elapsed:.1f}s. Next cycle in {wait:.1f}s.', flush=True)
            if wait:
                time.sleep(wait)
    except KeyboardInterrupt:
        print('\nAutomatic monitor stopped by user.', flush=True)


if __name__ == '__main__':
    main()
