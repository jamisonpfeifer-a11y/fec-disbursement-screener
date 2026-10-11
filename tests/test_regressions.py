import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from src.vendor_rules import (_is_self_payment, flag_disbursements,
                              load_categories, _matches_keywords)

cfg = load_categories(os.path.join(ROOT, "config", "vendor_categories.yaml"))

SELF = [
    ("ENGDAHL, ANDREW DAVID", "ANDREW ENGDAHL FOR CONGRESS", True),
    ("FERRELL, DAVID", "FERRELL FOR CONGRESS 2024", True),
    ("TANAKA, GREG LIN", "TANAKA, GREG", True),
    ("PORTER, KATHERINE", "KATIE PORTER FOR SENATE", True),
    ("SIKDER, ABDUR R DR", "DRSIKDERFORCONGRESS", True),
    ("SHERIDAN, TIMOTHY J", "SHERIDAN, TIM", True),
    ("HERMAN, THOMAS", "HERMAN, TOM", True),
    ("HERMAN, THOMAS", "HERMAN, ELDA", False),
    ("HERMAN, THOMAS", "GODOY DE HERMAN, ELDA", False),
    ("CHEN, ANITA S", "CHEN, TEDRA", False),
    ("ARBALLO, PHIL", "ARBALLO, CYNTHIA", False),
    ("ISSA, DARRELL", "ISSA - PERSONAL FUNDS, DARRELL", True),
    ("SMITH, JANE", "SMITH, ROBERT", False),
    ("SMITH, JANE", "OFFICE DEPOT", False),
    ("CURRY, ERIC", "CURRY, ERIC A.", True),
]
for cand, recip, expected in SELF:
    got = _is_self_payment(cand, recip)
    assert got == expected, f"{cand!r} vs {recip!r}: expected {expected}, got {got}"

assert not _matches_keywords("northern california community newspapers", ["spa"])
assert _matches_keywords("lakeside spa", ["spa"])
assert _matches_keywords("cigars etc", ["cigar"])
assert not _matches_keywords("my brother", ["other"])


def tx(recipient, amount, date="", desc="", cat=""):
    return {"committee_id": "C1", "recipient_name": recipient,
            "disbursement_amount": amount, "disbursement_date": date,
            "disbursement_description": desc,
            "disbursement_purpose_category": cat}


# newspaper ad buys are not luxury travel
r = flag_disbursements([tx("SONOMA MEDIA INVESTMENTS LLC", 6464, "2024-01-01", "NEWSPAPER ADVERTISING")], cfg, "MUNN, JOHN")
assert not r.flags

# refunds to a same-surname donor are not family payments
r = flag_disbursements([tx("WILKINSON, PHILIP R.", 3300, "2024-01-01", "CONTRIBUTION REFUND", "REFUNDS")], cfg, "WILKINSON, MARGARITA")
assert not r.flags and not r.category_totals

# a same-surname payee that is not a refund is still flagged
r = flag_disbursements([tx("ARBALLO, CYNTHIA", 500, "2024-01-01", "payroll")], cfg, "ARBALLO, PHIL")
assert [f.category for f in r.flags] == ["shared_surname_payee"]
assert r.category_totals["shared_surname_spend"] == 500

# the candidate's own committee is excluded from the peer comparison too
r = flag_disbursements([tx("DRSIKDERFORCONGRESS", 3580, "2024-01-01")], cfg, "SIKDER, ABDUR R DR")
assert not r.flags and not r.category_totals

# a card payment is its own (weak) category, not a family flag
r = flag_disbursements([tx("CAL BANK & TRUST VISA - FONG", 20658, "2024-01-01")], cfg, "FONG, VINCE")
assert [f.category for f in r.flags] == ["credit_card_payment"]

# repeated cigar-lounge visits still escalate
r = flag_disbursements([tx("HAVANA CIGAR LOUNGE", 400, f"2024-0{i}-01") for i in range(1, 5)], cfg, "DOE, JOHN")
assert len(r.flags) == 4 and r.vendor_risk_score > 2

print("regression tests passed")
