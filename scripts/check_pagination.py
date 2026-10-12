"""Compare cached Schedule B record counts with the API's own totals.

Run from the project root with FEC_API_KEY set:  python3 scripts/check_pagination.py
Makes about 6 API requests and prints no key. Counts UNIQUE records (by
sub_id), so repeated copies of the same page cannot pass as complete data.
"""
import glob
import json
import os
import re
import sys

import requests

BASE = "https://api.open.fec.gov/v1/schedules/schedule_b/"
key = os.environ.get("FEC_API_KEY")
if not key:
    sys.exit("Set FEC_API_KEY first.")

files = glob.glob("cache/disbursements_*.json")
if not files:
    sys.exit("No cached disbursement files found in ./cache")
files.sort(key=os.path.getsize, reverse=True)

print(f"{'committee':<12} {'unique cached':>13} {'api count':>10}  status")
for path in files[:6]:
    m = re.match(r"disbursements_(C\d+)_(\d+)\.json", os.path.basename(path))
    if not m:
        continue
    committee, period = m.group(1), int(m.group(2))
    rows = json.load(open(path))
    unique = len({r.get("sub_id") for r in rows})
    params = {"api_key": key, "committee_id": committee,
              "two_year_transaction_period": period, "per_page": 1}
    r = requests.get(BASE, params=params, timeout=60)
    r.raise_for_status()
    total = r.json()["pagination"]["count"]
    status = "OK" if unique >= total * 0.98 else f"INCOMPLETE ({total - unique} missing)"
    print(f"{committee:<12} {unique:>13} {total:>10}  {status}")
