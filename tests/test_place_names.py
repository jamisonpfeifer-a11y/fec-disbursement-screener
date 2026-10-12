import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import _is_shared_surname_payee, CommitteeFlagReport, TransactionFlag

sherman = {"sherman"}
assert not _is_shared_surname_payee(sherman, "SHERMAN OAKS PROFESSIONAL PLAZA LTD.")
assert not _is_shared_surname_payee({"lee"}, "Lee Heights Storage")
assert _is_shared_surname_payee(sherman, "SHERMAN, KAREN")
assert _is_shared_surname_payee(sherman, "Sherman Consulting LLC")
assert _is_shared_surname_payee(sherman, "Sherman Oaks Cafe; Sherman Properties")

r = CommitteeFlagReport(committee_id="X", total_disbursed=0)
for _ in range(10):
    r.flags.append(TransactionFlag("vague_high_dollar", "v", {"disbursement_amount": 5000}, "t", 0.5))
assert r.vendor_risk_score == 1.5
print("place name tests passed")
