"""
Command-line entry point.

Examples:
    python -m src.cli screen --cycle 2024 --office H --state CA
    python -m src.cli screen --cycle 2024 --office H --state CA --refresh
    python -m src.cli screen-committee --committee-id C00123456 --cycle 2024

FEC data is cached under ./cache. Re-running a command fetches only what is
missing (for example candidates skipped by API rate limits), and re-scoring
after a rule change makes no API calls. Use --refresh to download everything
again.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from .fec_client import FECClient, FECRateLimitError
from .peer_comparison import CandidateSpendProfile, compute_peer_anomalies
from .risk_scoring import damp_common_payees, rank_candidates, score_candidate
from .vendor_rules import flag_disbursements, load_categories

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def _resolve_config_path() -> str:
    """Use config/vendor_categories.yaml (your private rules) if present,
    otherwise fall back to the public example so a fresh clone still runs."""
    private = os.path.join(_CONFIG_DIR, "vendor_categories.yaml")
    if os.path.exists(private):
        return private
    print("Note: config/vendor_categories.yaml not found; using the public "
          "example rules (vendor_categories.example.yaml).", file=sys.stderr)
    return os.path.join(_CONFIG_DIR, "vendor_categories.example.yaml")


CONFIG_PATH = _resolve_config_path()
CACHE_DIR = "cache"


def _cached(name: str, fetch, refresh: bool):
    """Return cached JSON for `name`, or call fetch() and cache the result."""
    path = os.path.join(CACHE_DIR, name + ".json")
    if not refresh and os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, ValueError):
            pass  # unreadable cache file: re-fetch
    data = fetch()
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, default=str)
    os.replace(tmp, path)  # atomic, so a crash never leaves a partial file
    return data


def _build_profile_and_flags(client: FECClient, config: dict, candidate: dict, cycle: int,
                             refresh: bool = False):
    candidate_id = candidate["candidate_id"]
    candidate_name = candidate.get("name", "")

    committees = _cached(
        f"committees_{candidate_id}_{cycle}",
        lambda: client.get_candidate_committees(candidate_id, cycle),
        refresh,
    )
    principal_committees = [c for c in committees if c.get("designation") == "P"] or committees
    if not principal_committees:
        return None, None

    committee_id = principal_committees[0]["committee_id"]

    two_year_period = cycle if cycle % 2 == 0 else cycle + 1
    disbursements = _cached(
        f"disbursements_{committee_id}_{two_year_period}",
        lambda: client.get_disbursements(committee_id, two_year_period),
        refresh,
    )
    if not disbursements:
        return None, None

    vendor_report = flag_disbursements(disbursements, config, candidate_name=candidate_name)

    profile = CandidateSpendProfile(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        committee_id=committee_id,
        office=candidate.get("office", ""),
        state=candidate.get("state", ""),
        party=candidate.get("party", ""),
        incumbent_challenge=candidate.get("incumbent_challenge", ""),
        cycle=cycle,
        total_disbursed=vendor_report.total_disbursed,
        category_totals=vendor_report.category_totals,
    )
    return profile, vendor_report


def cmd_screen(args):
    client = FECClient()
    config = load_categories(CONFIG_PATH)
    refresh = getattr(args, "refresh", False)

    print(f"Fetching candidates: cycle={args.cycle} office={args.office} state={args.state}", file=sys.stderr)
    cand_key = f"candidates_{args.cycle}_{args.office}_{args.state or 'ALL'}_{args.party or 'ALL'}"
    candidates = _cached(
        cand_key,
        lambda: client.get_candidates(
            cycle=args.cycle, office=args.office, state=args.state, party=args.party
        ),
        refresh,
    )
    print(f"Found {len(candidates)} candidates.", file=sys.stderr)

    profiles = []
    vendor_reports = {}
    skipped = []
    seen_committees = set()
    for i, cand in enumerate(candidates):
        print(f"[{i+1}/{len(candidates)}] {cand.get('name')}", file=sys.stderr)
        try:
            profile, vendor_report = _build_profile_and_flags(
                client, config, cand, args.cycle, refresh=refresh
            )
        except FECRateLimitError as e:
            print(f"\n{e}", file=sys.stderr)
            print(f"Stopped after {i} of {len(candidates)} candidates. Downloaded data is cached; "
                  "re-run the same command later (the quota resets hourly) to continue.", file=sys.stderr)
            return
        except Exception as e:
            print(f"  SKIPPED (error: {e})", file=sys.stderr)
            skipped.append(cand.get("name"))
            continue
        if profile is None:
            continue
        # The same person can be listed under several candidate IDs; count
        # each committee once so duplicates do not skew peer comparisons.
        if profile.committee_id in seen_committees:
            continue
        seen_committees.add(profile.committee_id)
        profiles.append(profile)
        vendor_reports[profile.candidate_id] = vendor_report

    peer_categories = list(config.get("peer_comparison_categories", {}).keys())
    peer_results = compute_peer_anomalies(profiles, peer_categories)

    peer_by_candidate: dict[str, list] = {}
    for r in peer_results:
        peer_by_candidate.setdefault(r.candidate_id, []).append(r)

    common = damp_common_payees(list(vendor_reports.values()))
    if common:
        print(f"{len(common)} payees flagged across many committees were down-weighted.", file=sys.stderr)

    summaries = []
    for profile in profiles:
        vendor_report = vendor_reports[profile.candidate_id]
        summary = score_candidate(
            profile.candidate_id,
            profile.candidate_name,
            vendor_report,
            peer_by_candidate.get(profile.candidate_id, []),
        )
        summaries.append(summary)

    ranked = rank_candidates(summaries)
    _write_report(ranked, args)

    if skipped:
        print(f"\n{len(skipped)} candidate(s) were skipped because of API errors:", file=sys.stderr)
        print("  " + "; ".join(str(n) for n in skipped), file=sys.stderr)
        print("Re-run the same command to retry just those (everything else is cached).", file=sys.stderr)
    else:
        print("\nAll candidates processed. No skips.", file=sys.stderr)


def cmd_screen_committee(args):
    client = FECClient()
    config = load_categories(CONFIG_PATH)
    refresh = getattr(args, "refresh", False)

    two_year_period = args.cycle if args.cycle % 2 == 0 else args.cycle + 1
    disbursements = _cached(
        f"disbursements_{args.committee_id}_{two_year_period}",
        lambda: client.get_disbursements(args.committee_id, two_year_period),
        refresh,
    )
    vendor_report = flag_disbursements(disbursements, config)

    summary = score_candidate(args.committee_id, args.committee_id, vendor_report, [])
    _write_report([summary], args)


def _write_report(ranked, args):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"output/screening_report_{timestamp}.json"

    payload = [
        {
            "candidate_id": s.candidate_id,
            "candidate_name": s.candidate_name,
            "committee_id": s.committee_id,
            "composite_score": s.composite_score,
            "vendor_score": s.vendor_score,
            "peer_anomaly_score": s.peer_anomaly_score,
            "vendor_flags": s.vendor_flags,
            "peer_anomalies": s.peer_anomalies,
        }
        for s in ranked
    ]

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nWrote report to {out_path}", file=sys.stderr)
    print("\nTop candidates by composite risk score:", file=sys.stderr)
    for s in ranked[:10]:
        print(f"  {s.composite_score:>6.2f}  {s.candidate_name}  (vendor={s.vendor_score}, peer={s.peer_anomaly_score})", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="FEC disbursement screening tool (leads for human review, not findings)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_screen = sub.add_parser("screen", help="Screen all candidates matching filters")
    p_screen.add_argument("--cycle", type=int, required=True)
    p_screen.add_argument("--office", choices=["H", "S", "P"], required=True)
    p_screen.add_argument("--state", required=False)
    p_screen.add_argument("--party", required=False)
    p_screen.add_argument("--refresh", action="store_true",
                          help="Ignore cached FEC data and download everything again")
    p_screen.set_defaults(func=cmd_screen)

    p_committee = sub.add_parser("screen-committee", help="Screen a single committee by ID")
    p_committee.add_argument("--committee-id", required=True)
    p_committee.add_argument("--cycle", type=int, required=True)
    p_committee.add_argument("--refresh", action="store_true",
                             help="Ignore cached FEC data and download everything again")
    p_committee.set_defaults(func=cmd_screen_committee)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
