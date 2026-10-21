"""Quick sanity summary of a screening report.

Usage: python3 scripts/health_check.py [report.json]
Defaults to the newest file in output/. Use it after each state run to see
whether the run looks reasonable before reading individual names.
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path is None:
        files = sorted(glob.glob("output/screening_report_*.json"), key=os.path.getmtime)
        if not files:
            sys.exit("No report found in output/")
        path = files[-1]
    with open(path) as f:
        report = json.load(f)

    n = len(report)
    print(f"Report: {path}")
    print(f"Candidates scored: {n}")
    if not n:
        return

    scores = sorted((r["composite_score"] for r in report), reverse=True)
    flagged = [r for r in report if r["vendor_flags"]]
    print(f"With at least one vendor flag: {len(flagged)} ({len(flagged) / n:.0%})")
    print(f"Score: max {scores[0]:.2f}, median {scores[n // 2]:.2f}, "
          f"at or above 5.0: {sum(s >= 5 for s in scores)}")

    cats = Counter()
    for r in report:
        cats.update({f["category"] for f in r["vendor_flags"]})
    print("\nCandidates flagged per category:")
    for cat, count in cats.most_common():
        print(f"  {count:>4}  {cat}")

    # Payees that show up for several committees are usually institutions
    # (venues, card issuers, large vendors).
    payee_committees = defaultdict(set)
    for r in report:
        for f in r["vendor_flags"]:
            if not f["category"].startswith("shared_surname"):
                payee_committees[(f["recipient"] or "").upper().strip()].add(r["committee_id"])
    common = sorted(((len(v), k) for k, v in payee_committees.items() if len(v) >= 3), reverse=True)
    print("\nPayees flagged for 3+ committees (check these are institutions):")
    for count, payee in common[:10] or [(0, "(none)")]:
        print(f"  {count:>4}  {payee}")

    name_based = sum(
        1 for r in report[:10]
        if any(f["category"].startswith("shared_surname") for f in r["vendor_flags"]))
    print(f"\nTop 10 with a shared-surname flag: {name_based}")

    groups = {a["peer_group_size"] for r in report for a in r["peer_anomalies"]}
    if groups:
        print(f"Peer group sizes seen in anomalies: min {min(groups)}, max {max(groups)}")
        if min(groups) < 10:
            print("  Note: small peer groups make peer scores unreliable.")
    else:
        print("No peer anomalies in this report.")


if __name__ == "__main__":
    main()
