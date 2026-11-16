"""Create a reviewed UP/UP interface inventory from latest successful router samples.
Run only when intended links are UP. Review interface_inventory.csv afterwards.
"""
import csv
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parent
src=ROOT/'interface_health.csv'
dst=ROOT/'interface_inventory.csv'
if dst.exists():
    raise SystemExit('Inventory already exists. Edit it manually if needed; not overwriting.')
if not src.exists():
    raise SystemExit('First run the routing/interface collector to create interface_health.csv')
with src.open(newline='',encoding='utf-8-sig') as f:
    data=list(csv.DictReader(f))
latest={}
for row in data:
    if row.get('router') and row.get('interface'):
        key=(row['router'].strip().upper(),row['interface'].strip())
        if key not in latest or row.get('timestamp','') >= latest[key].get('timestamp',''):
            latest[key]=row
rows=[]
for (router,interface),r in sorted(latest.items()):
    if r.get('admin_status','').strip().lower()=='up' and r.get('protocol_status','').strip().lower()=='up':
        rows.append({'router':router,'interface':interface,'expected_admin':'up','expected_protocol':'up','monitor':'yes','note':'Auto-created from UP/UP baseline; review before use'})
with dst.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['router','interface','expected_admin','expected_protocol','monitor','note']);w.writeheader();w.writerows(rows)
print(f'Created {dst} with {len(rows)} UP/UP interfaces. Review it: only listed enabled ports trigger DOWN alerts.')
