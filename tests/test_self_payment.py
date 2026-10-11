import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vendor_rules import _is_self_payment

CASES = [
    ("ENGDAHL, ANDREW", "ANDREW ENGDAHL FOR CONGRESS", True),
    ("FERRELL, DAVID", "FERRELL FOR CONGRESS 2024", True),
    ("TANAKA, GREG", "GREG TANAKA FOR CONGRESS", True),
    ("TANAKA, GREG", "TANAKA, GREG", True),
    ("CURRY, ERIC ALLEN", "CURRY, ERIC A.", True),
    ("ISSA, DARRELL", "ISSA - PERSONAL FUNDS, DARRELL", True),
    ("ROBERTS, BOYD", "ROBERTS, BOYD LACHLAN", True),
    ("SMITH, JANE", "SMITH, ROBERT", False),
    ("SMITH, JANE", "SMITH CONSULTING LLC", False),
    ("SMITH, JANE", "OFFICE DEPOT", False),
    ("PORTER, KATHERINE", "KATIE PORTER FOR SENATE", True),
    ("CHEN, ANITA S", "CHEN, TEDRA", False),
]

for cand, recip, expected in CASES:
    got = _is_self_payment(cand, recip)
    assert got == expected, f"{cand!r} vs {recip!r}: expected {expected}, got {got}"

print("self-payment tests passed")
