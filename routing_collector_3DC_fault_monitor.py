"""Read-only Cisco OSPF/BGP neighbor collector for a three-DC EVE-NG lab.

Run separately: python routing_collector_3DC.py
Uses the same Windows Credential Manager entry as multi_collector.py.
"""
import csv
import re
from datetime import datetime
from pathlib import Path

import keyring
from netmiko import ConnectHandler

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / 'routing_health.csv'
INTERFACE_CSV = ROOT / 'interface_health.csv'
INTERFACE_FIELDS = ['timestamp','router','interface','ip_address','admin_status','protocol_status','detail']
ROUTERS = {
    'DC1-LEAF1': '192.168.171.10',
    'DC1-LEAF2': '192.168.171.11',
    'DC1-SPINE1': '192.168.171.12',
    'DC1-SPINE2': '192.168.171.13',
    'DC2-SPINE1': '192.168.171.20',
    'DC2-SPINE2': '192.168.171.21',
    'DC2-LEAF1': '192.168.171.22',
    'DC2-LEAF2': '192.168.171.23',
    'DC3-SPINE1': '192.168.171.30',
    'DC3-SPINE2': '192.168.171.33',
    'DC3-LEAF1': '192.168.171.31',
    'DC3-LEAF2': '192.168.171.32',
}
FIELDS = ['timestamp', 'router', 'protocol', 'peer', 'state', 'detail']


def parse_ospf(output, router, timestamp):
    rows = []
    # IOS: Neighbor ID Pri State Dead Time Address Interface
    for line in output.splitlines():
        m = re.match(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+\d+\s+(FULL|2WAY|2-WAY|EXSTART|EXCHANGE|LOADING|INIT|DOWN|ATTEMPT)(?:/\S+)?\s+', line, re.I)
        if m:
            state = m.group(2).upper().replace('2WAY', '2-WAY')
            rows.append(dict(timestamp=timestamp, router=router, protocol='OSPF', peer=m.group(1), state=state, detail=line.strip()))
    return rows


def parse_bgp(output, router, timestamp):
    rows = []
    in_table = False
    for line in output.splitlines():
        if re.search(r'^\s*Neighbor\s+V\s+AS\s+', line, re.I):
            in_table = True
            continue
        if not in_table:
            continue
        # IOS 'show ip bgp summary': Neighbor V AS MsgRcvd MsgSent TblVer InQ OutQ Up/Down State/PfxRcd
        parts = line.split()
        if len(parts) < 10 or not re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', parts[0]):
            continue
        final = parts[-1]
        state = 'ESTABLISHED' if final.isdigit() else final.upper()
        rows.append(dict(timestamp=timestamp, router=router, protocol='BGP', peer=parts[0], state=state,
                         detail=f'Peer AS={parts[2]}; State/PfxRcd={final}; Up/Down={parts[-2]}'))
    return rows


def parse_interfaces(output, router, timestamp):
    """Parse Cisco IOS show ip interface brief; preserve admin-down status."""
    rows = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[0].startswith(('GigabitEthernet', 'FastEthernet', 'Ethernet')):
            continue
        # IOS columns: Interface IP-Address OK? Method Status Protocol
        ip = parts[1]
        status = ' '.join(parts[4:-1]).lower()
        protocol = parts[-1].lower()
        if status not in ('up','down','administratively down') or protocol not in ('up','down'):
            continue
        rows.append(dict(timestamp=timestamp, router=router, interface=parts[0],
                         ip_address=ip, admin_status=status, protocol_status=protocol,
                         detail=line.strip()))
    return rows


def save_interface_rows(rows):
    if not rows:
        return
    write_header = not INTERFACE_CSV.exists() or INTERFACE_CSV.stat().st_size == 0
    if not write_header:
        with INTERFACE_CSV.open(newline='', encoding='utf-8-sig') as f:
            if next(csv.reader(f), []) != INTERFACE_FIELDS:
                raise ValueError('Existing interface_health.csv schema differs; back it up first.')
    with INTERFACE_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=INTERFACE_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    print(f'Saved {len(rows)} interface observations to {INTERFACE_CSV.name}')

def main():
    password = keyring.get_password('DC_ML_Project', 'admin')
    if not password:
        raise RuntimeError('Credential missing: save the SSH password in Windows Credential Manager first.')
    observations = []
    interface_observations = []
    failures = []
    timestamp = datetime.now().isoformat(timespec='seconds')
    for name, ip in ROUTERS.items():
        try:
            with ConnectHandler(device_type='cisco_ios', host=ip, username='admin', password=password, conn_timeout=15) as conn:
                ospf = conn.send_command('show ip ospf neighbor', read_timeout=20)
                bgp = conn.send_command('show ip bgp summary', read_timeout=20)
                interfaces = conn.send_command('show ip interface brief', read_timeout=20)
                interface_rows = parse_interfaces(interfaces, name, timestamp)
                interface_observations.extend(interface_rows)
                if re.search(r'%\s*(Invalid input|Unknown command)', ospf, re.I):
                    failures.append(f'{name}: OSPF command unsupported')
                if re.search(r'%\s*(Invalid input|Unknown command)', bgp, re.I):
                    failures.append(f'{name}: BGP command unsupported')
                ospf_rows = parse_ospf(ospf, name, timestamp)
                bgp_rows = parse_bgp(bgp, name, timestamp)
                observations.extend(ospf_rows + bgp_rows)
                print(f'[OK] {name}: {len(ospf_rows)} OSPF neighbors, {len(bgp_rows)} BGP peers, {len(interface_rows)} interfaces')
        except Exception as exc:
            failures.append(f'{name}: {type(exc).__name__}: {exc}')
            print(f'[FAILED] {name}: {type(exc).__name__}: {exc}')
    if observations:
        write_header = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
        if not write_header:
            with CSV_FILE.open(newline='', encoding='utf-8-sig') as f:
                if next(csv.reader(f), []) != FIELDS:
                    raise ValueError('Existing routing_health.csv schema differs; back it up before changing it.')
        with CSV_FILE.open('a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(observations)
        print(f'Saved {len(observations)} peer observations to {CSV_FILE.name}')
    else:
        print('No peer observations saved; check router command output and connectivity.')
    save_interface_rows(interface_observations)
    if failures:
        print('\nCollection issues:')
        for failure in failures:
            print(' -', failure)
    print('Note: Missing peers are not automatically treated as healthy; compare against your intended topology.')


if __name__ == '__main__':
    main()
