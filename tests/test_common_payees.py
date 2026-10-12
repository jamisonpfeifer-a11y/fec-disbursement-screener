import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import CommitteeFlagReport, TransactionFlag
from src.risk_scoring import damp_common_payees


def rep(cid, flags):
    r = CommitteeFlagReport(committee_id=cid, total_disbursed=0)
    for cat, payee, w in flags:
        r.flags.append(TransactionFlag(category=cat, label=cat,
            transaction={"disbursement_amount": 2000, "recipient_name": payee},
            reason="t", score_contribution=w))
    return r

# a venue flagged for 4 committees is damped; a one-off venue is not
reps = [rep(f"C{i}", [("luxury_travel", "Lansdowne  Resort", 0.7)]) for i in range(4)]
solo = rep("C9", [("luxury_travel", "Hidden Cove Resort", 0.7),
                  ("shared_surname_payee", "Lansdowne Resort", 1.0)])
reps.append(solo)
common = damp_common_payees(reps)
assert common == {"LANSDOWNE RESORT": 4}, common
assert all(abs(r.flags[0].score_contribution - 0.35) < 1e-9 for r in reps[:4])
assert solo.flags[0].score_contribution == 0.7
assert solo.flags[1].score_contribution == 1.0  # name-based: never damped

# repeated flags in one committee count once
one = [rep("C1", [("luxury_travel", "X Resort", 0.7)] * 6)]
assert damp_common_payees(one) == {}

# default per-category cap: a single category cannot reach the total cap
big = rep("C1", [("luxury_travel", "A Resort", 0.7)] * 11)
assert big.vendor_risk_score == 4.0, big.vendor_risk_score
print("common payee tests passed")
