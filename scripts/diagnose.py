"""Print a compact explanation of the top-N candidates in the latest report."""
import glob
import json
import sys
from collections import defaultdict

n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
f = sorted(glob.glob("output/screening_report_*.json"))[-1]
data = json.load(open(f))
rows = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
print("Report:", f, "| candidates scored:", len(rows))
for r in sorted(rows, key=lambda r: r["composite_score"], reverse=True)[:n]:
    print("=" * 70)
    print(f'{r["candidate_name"]}  composite={r["composite_score"]}')
    cats = defaultdict(lambda: [0, 0.0, defaultdict(float)])
    for fl in r["vendor_flags"]:
        c = cats[fl["category"]]
        c[0] += 1
        c[1] += fl["amount"] or 0
        c[2][fl["recipient"]] += fl["amount"] or 0
    for cat, (cnt, amt, recips) in cats.items():
        top = sorted(recips.items(), key=lambda x: -x[1])[:3]
        print(f"  {cat}: {cnt} hits, ${amt:,.0f}  top: {top}")
    for p in r["peer_anomalies"][:3]:
        print(f'  peer: {p["category"]} share={p["candidate_share"]} vs median={p["peer_median_share"]} z={p["robust_z"]}')
