import csv
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'dc_metrics.csv'
ARCHIVE = BASE / 'archive'


def archive_old_rows():
    if not SOURCE.exists() or SOURCE.stat().st_size == 0:
        print('No metrics CSV to archive.')
        return
    cutoff = datetime.now() - timedelta(hours=24)
    with SOURCE.open('r', newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if not fields or 'timestamp' not in fields:
            raise ValueError('CSV must contain timestamp column.')
        recent = []
        older = defaultdict(list)
        invalid = 0
        for row in reader:
            stamp = (row.get('timestamp') or '').strip()
            try:
                moment = datetime.fromisoformat(stamp)
                if moment.tzinfo is not None:
                    moment = moment.astimezone().replace(tzinfo=None)
            except ValueError:
                recent.append(row)  # Preserve malformed data rather than lose it.
                invalid += 1
                continue
            if moment < cutoff:
                older[moment.strftime('%Y-%m-%d')].append(row)
            else:
                recent.append(row)

    if not older:
        print(f'No rows older than 24 hours. Unparseable timestamps: {invalid}')
        return

    ARCHIVE.mkdir(exist_ok=True)
    # Write archived rows first. If anything fails, original source remains intact.
    for day, rows in sorted(older.items()):
        target = ARCHIVE / f'dc_metrics_{day}.csv'
        if target.exists() and target.stat().st_size:
            with target.open('r', newline='', encoding='utf-8-sig') as check:
                existing_fields = next(csv.reader(check), [])
            if existing_fields != fields:
                raise ValueError(f'Archive header mismatch: {target}')
        need_header = not target.exists() or target.stat().st_size == 0
        with target.open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if need_header:
                writer.writeheader()
            writer.writerows(rows)
        print(f'Archived {len(rows)} rows to {target.name}')

    # Atomically replace source only after all archive writes succeeded.
    fd, tmp = tempfile.mkstemp(prefix='metrics_', suffix='.tmp', dir=BASE)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(recent)
        os.replace(tmp, SOURCE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f'Current CSV: {len(recent)} rows retained; {sum(map(len, older.values()))} archived.')


if __name__ == '__main__':
    archive_old_rows()
