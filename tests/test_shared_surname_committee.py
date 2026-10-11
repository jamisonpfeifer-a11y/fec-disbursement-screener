import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.vendor_rules import flag_disbursements, load_categories

cfg = load_categories(os.path.join(ROOT, "config", "vendor_categories.yaml"))

def run(cand, recip, amt=5000, desc=""):
    tx = [{"committee_id": "C1", "recipient_name": recip, "disbursement_amount": amt,
           "disbursement_description": desc, "sub_id": "1"}]
    return flag_disbursements(tx, cfg, candidate_name=cand)

def cats(r):
    return {f.category for f in r.flags}

# committee name with a shared surname -> its own category, not shared_surname_payee
r = run("LOWENTHAL, ALAN", "JOSH LOWENTHAL FOR ASSEMNBLY 2024", 11000)
assert cats(r) == {"shared_surname_committee"}, cats(r)
assert r.category_totals.get("shared_surname_spend", 0) == 0
r = run("LIEU, TED", "BETTY LIEU FOR SCHOOL BOARD 2024", 500)
assert cats(r) == {"shared_surname_committee"}, cats(r)
# ordinary same-surname payee is still a shared_surname_payee
r = run("CHEN, ANITA S", "CHEN, KELLY", 2000)
assert cats(r) == {"shared_surname_payee"}, cats(r)
# own committee still a self-payment (no flag)
r = run("PORTER, KATHERINE", "KATIE PORTER FOR SENATE", 5000)
assert not cats(r), cats(r)
# hotel chain name is not a resort stay; a real resort still is
r = run("ARCHULETA, BOB", "HILTON HOTELS & RESORTS", 1108)
assert "luxury_travel" not in cats(r), cats(r)
r = run("STEEL, MICHELLE", "THE RESORT AT PELICAN HILL", 4137)
assert "luxury_travel" in cats(r), cats(r)
r = run("LIEU, TED", "JW MARRIOTT MIAMI TURNBERRY RESORT & SPA", 1053)
assert "luxury_travel" in cats(r), cats(r)
print("shared-surname-committee and chain-name tests passed")
