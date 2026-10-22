"""Export every flagged transaction from a screening report to a CSV.

Usage:
  python3 scripts/export_flags.py                      # newest report in output/
  python3 scripts/export_flags.py report.json --min-amount 5000
  python3 scripts/export_flags.py --category shared_surname_payee --candidate LIEU

One row per flagged transaction, sorted by amount, with links back to the FEC
filing. Open the CSV in Excel or Google Sheets to sort and filter.
"""
import argparse
import csv
import glob
import json
import os
import sys
from urllib.parse import quote_plus

DOCQUERY = "https://docquery.fec.gov/cgi-bin/fecimg/?"


def filing_link(flag: dict) -> str:
    """Link to the scanned filing page that contains the transaction."""
    if flag.get("pdf_url"):
        return flag["pdf_url"]
    if flag.get("image_number"):
        return DOCQUERY + str(flag["image_number"])
    return ""


def search_link(committee_id: str, flag: dict) -> str:
    """FEC.gov disbursement search for the same committee and payee."""
    url = ("https://www.fec.gov/data/disbursements/?data_type=processed"
           f"&committee_id={committee_id}")
    if flag.get("recipient"):
        url += "&recipient_name=" + quote_plus(str(flag["recipient"]))
    return url


def rows(report, min_amount=0.0, category=None, candidate=None):
    for cand in report:
        if candidate and candidate.lower() not in cand["candidate_name"].lower():
            continue
        for flag in cand["vendor_flags"]:
            try:
                amount = float(flag.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if abs(amount) < min_amount:
                continue
            if category and flag["category"] != category:
                continue
            yield {
                "candidate": cand["candidate_name"],
                "committee_id": cand["committee_id"],
                "candidate_score": cand["composite_score"],
                "date": (flag.get("date") or "")[:10],
                "amount": amount,
                "recipient": flag.get("recipient") or "",
                "description": flag.get("description") or "",
                "category": flag["category"],
                "reason": flag["reason"],
                "flag_weight": flag.get("score_contribution"),
                "filing_link": filing_link(flag),
                "fec_search_link": search_link(cand["committee_id"], flag),
            }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", nargs="?", help="report JSON (default: newest in output/)")
    ap.add_argument("--min-amount", type=float, default=0.0, help="only transactions of at least this size")
    ap.add_argument("--category", help="only this category, e.g. shared_surname_payee")
    ap.add_argument("--candidate", help="only candidates whose name contains this text")
    ap.add_argument("--out", help="CSV path (default: next to the report)")
    args = ap.parse_args()

    path = args.report
    if path is None:
        files = sorted(glob.glob("output/screening_report_*.json"), key=os.path.getmtime)
        if not files:
            sys.exit("No report found in output/")
        path = files[-1]
    with open(path) as f:
        report = json.load(f)

    data = sorted(rows(report, args.min_amount, args.category, args.candidate),
                  key=lambda r: abs(r["amount"]), reverse=True)
    out = args.out or path.replace(".json", "_flags.csv")
    fields = ["candidate", "committee_id", "candidate_score", "date", "amount", "recipient",
              "description", "category", "reason", "flag_weight", "filing_link", "fec_search_link"]
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)

    missing = sum(1 for r in data if not r["filing_link"])
    print(f"Wrote {len(data)} flagged transactions to {out}")
    if missing:
        print(f"{missing} rows have no filing link (re-run the screen to add filing details; "
              "cached data is reused, so this is quick). The fec_search_link still works.")


if __name__ == "__main__":
    main()
