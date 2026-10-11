import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import CommitteeFlagReport, TransactionFlag

def rep(flags):
    r = CommitteeFlagReport(committee_id="X", total_disbursed=0)
    for cat, amt, w in flags:
        r.flags.append(TransactionFlag(category=cat, label=cat,
            transaction={"disbursement_amount": amt}, reason="t", score_contribution=w))
    return r

# one large same-surname payment outranks many small ones
big = rep([("shared_surname_payee", 5000, 4.0)])
small = rep([("shared_surname_payee", 388, 4.0)] * 10)
assert big.vendor_risk_score > small.vendor_risk_score, (big.vendor_risk_score, small.vendor_risk_score)
assert abs(big.vendor_risk_score - 4.0) < 1e-9

# Card-issuer payments alone are a weak lead: capped at 1.0
card = rep([("credit_card_payment", 32000, 0.5)] * 4)
assert card.vendor_risk_score == 1.0
# ...and a modest same-surname payment scores below the cap
fam = rep([("shared_surname_payee", 2000, 1.57)])
assert fam.vendor_risk_score < 4.0
print("ranking weight tests passed")
