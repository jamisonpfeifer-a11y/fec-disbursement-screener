import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import _is_self_payment as me, flag_disbursements

CFG = {"categories": {
    "tobacco_lounge": {"label": "Tobacco", "keywords": ["cigar"], "weight": 1.0,
                       "per_transaction_flag_usd": 100, "escalation": True},
    "shared_surname_payee": {"label": "Shared surname", "weight": 1.0, "escalation": False},
}}


def txn(recipient, amount, i=0):
    return {"committee_id": "C1", "recipient_name": recipient, "disbursement_amount": amount,
            "disbursement_description": "", "sub_id": i}


# own committee with the committee word glued to a stray letter
assert me("PFLUGER, AUGUST LEE II", "PFRIENDS OF PFLUGER")
assert me("LIEU, TED", "FRIENDS OF LIEU")
assert not me("BROWN, M SHONTEL", "FRIENDS OF SHERROD BROWN")

# PACs are not cigar shops
r = flag_disbursements([txn("PREMIUM CIGAR ASSOCIATION POLITICAL ACTION COMMITTEE", 875, 1),
                        txn("CIGAR-PAC (CIGAR ASSOCIATION OF AMERICA, INC.)", 470, 2),
                        txn("JOSEPH'S CIGAR SHOP", 700, 3)], CFG, candidate_name="NEHLS, TROY")
assert [f.transaction["recipient_name"] for f in r.flags] == ["JOSEPH'S CIGAR SHOP"]

# negative amounts (returned payments) are not flagged
r = flag_disbursements([txn("CRENSHAW, TARA", -441.71, 1)], CFG, candidate_name="CRENSHAW, DANIEL")
assert not r.flags

# common surnames count at half weight
rare = flag_disbursements([txn("CRENSHAW, TARA", 1000, 1)], CFG, candidate_name="CRENSHAW, DANIEL")
common = flag_disbursements([txn("GONZALEZ, LUZ", 1000, 1)], CFG, candidate_name="GONZALEZ, VICENTE")
assert abs(common.flags[0].score_contribution - rare.flags[0].score_contribution / 2) < 1e-9
print("texas pattern tests passed")

# many payments to people sharing a very common surname cannot reach the full cap
many = flag_disbursements([txn(f"GONZALEZ, PERSON{i}", 1000, i) for i in range(25)], CFG,
                          candidate_name="GONZALEZ, VICENTE")
assert many.vendor_risk_score <= 2.0 + 1e-9, many.vendor_risk_score
few = flag_disbursements([txn(f"CRENSHAW, PERSON{i}", 1000, i) for i in range(25)], CFG,
                         candidate_name="CRENSHAW, DANIEL")
assert few.vendor_risk_score > 2.0
print("common surname cap tests passed")
