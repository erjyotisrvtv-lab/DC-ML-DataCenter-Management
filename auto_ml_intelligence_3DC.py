"""Run ML intelligence every 60+ seconds; existing collectors stay separate."""
from pathlib import Path
import argparse
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--interval',type=int,default=60)
args=parser.parse_args()
if args.interval<30:
    parser.error('Minimum interval is 30 seconds')
print('3-DC ML Intelligence automatic monitor started. Ctrl+C to stop.',flush=True)
try:
    while True:
        start=time.monotonic()
        code=subprocess.call([sys.executable,str(ROOT/'ml_intelligence_3DC.py')],cwd=ROOT)
        if code:
            print(f'Warning: intelligence engine exit code {code}',flush=True)
        time.sleep(max(0,args.interval-(time.monotonic()-start)))
except KeyboardInterrupt:
    print('ML Intelligence monitor stopped.')
