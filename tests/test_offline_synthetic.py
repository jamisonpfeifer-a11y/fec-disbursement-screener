"""
Offline sanity test using synthetic disbursement data (no network / FEC API
calls). Confirms:
  1. A candidate with repeated cigar-lounge spending gets hard-flagged.
  2. A candidate whose "catering" spending share is a wild outlier vs. peers
     gets caught by peer comparison, while normal peers do not.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vendor_rules import flag_disbursements, load_categories
from src.peer_comparison import CandidateSpendProfile, compute_peer_anomalies

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "vendor_categories.yaml")


def make_txn(committee_id, recipient, description, amount, date="2023-06-01"):
    return {
        "committee_id": committee_id,
        "recipient_name": recipient,
        "disbursement_description": description,
        "disbursement_amount": amount,
        "disbursement_date": date,
    }


def test_cigar_lounge_hard_flag():
    config = load_categories(CONFIG_PATH)
    disbursements = [
        make_txn("C001", "Downtown Cigar Lounge", "client meeting", 450),
        make_txn("C001", "Downtown Cigar Lounge", "client meeting", 600),
        make_txn("C001", "Office Depot", "supplies", 120),
    ]
    report = flag_disbursements(disbursements, config, candidate_name="Jane Smith")
    tobacco_flags = [f for f in report.flags if f.category == "tobacco_lounge"]
    assert len(tobacco_flags) == 2, f"expected 2 tobacco flags, got {len(tobacco_flags)}"
    # escalation should make the second flag's contribution higher than the first
    assert tobacco_flags[1].score_contribution > tobacco_flags[0].score_contribution
    print("PASS: cigar lounge repeated spending hard-flagged with escalation")


def test_peer_comparison_catches_outlier():
    config = load_categories(CONFIG_PATH)

    profiles = []
    # 12 "normal" peers spending ~5% of budget on catering
    for i in range(12):
        total = 100_000
        catering = 5_000  # 5%
        profiles.append(CandidateSpendProfile(
            candidate_id=f"NORM{i}",
            candidate_name=f"Normal Candidate {i}",
            committee_id=f"C{i}",
            office="H",
            state="CA",
            party="DEM",
            incumbent_challenge="C",
            cycle=2024,
            total_disbursed=total,
            category_totals={"catering_events": catering},
        ))

    # 1 outlier spending 60% of budget on catering
    profiles.append(CandidateSpendProfile(
        candidate_id="OUTLIER1",
        candidate_name="Outlier Candidate",
        committee_id="C_OUT",
        office="H",
        state="CA",
        party="DEM",
        incumbent_challenge="C",
        cycle=2024,
        total_disbursed=100_000,
        category_totals={"catering_events": 60_000},
    ))

    results = compute_peer_anomalies(profiles, ["catering_events"])
    outlier_results = [r for r in results if r.candidate_id == "OUTLIER1"]
    normal_results = [r for r in results if r.candidate_id == "NORM0"]

    assert outlier_results, "outlier candidate should have a peer comparison result"
    assert abs(outlier_results[0].robust_z) > 5, f"expected large z-score for outlier, got {outlier_results[0].robust_z}"

    if normal_results:
        assert abs(normal_results[0].robust_z) < 1, f"normal candidate should not be flagged, got {normal_results[0].robust_z}"

    print(f"PASS: peer comparison flagged outlier (z={outlier_results[0].robust_z:.2f}) "
          f"and left normal peers alone")


if __name__ == "__main__":
    test_cigar_lounge_hard_flag()
    test_peer_comparison_catches_outlier()
    print("\nAll offline sanity tests passed.")
