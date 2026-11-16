"""Run automatic ML evaluation from already collected dc_metrics.csv.
Does not launch or interfere with existing interface/routing or metric collectors.
Usage: python auto_ml_monitor.py --interval 60
"""
from datetime import datetime
from pathlib import Path
import argparse
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
SCRIPT=ROOT/'ml_detection_3DC_from_original_UPDATED.py'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--interval',type=int,default=60,help='Minimum seconds between ML cycle starts')
    args=parser.parse_args()
    if args.interval<30:
        parser.error('Use an interval >= 30 seconds')
    if not SCRIPT.exists():
        parser.error(f'Missing {SCRIPT.name}')
    print(f'3-DC automatic ML monitor started, interval target {args.interval}s. Ctrl+C to stop.',flush=True)
    try:
        while True:
            start=time.monotonic()
            print(f'[{datetime.now():%H:%M:%S}] Running 12-router ML evaluation...',flush=True)
            result=subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=False)
            if result.returncode:
                print(f'[WARNING] ML exited {result.returncode}; will retry.',flush=True)
            time.sleep(max(0,args.interval-(time.monotonic()-start)))
    except KeyboardInterrupt:
        print('ML monitor stopped.',flush=True)

if __name__=='__main__':
    main()
