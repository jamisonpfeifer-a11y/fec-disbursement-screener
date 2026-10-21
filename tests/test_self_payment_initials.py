import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import _is_self_payment as me

assert me("VANCE, J D", "VANCE, JD")
assert me("VANCE, J D", "JD VANCE")
assert me("VANCE, J D", "VANCE, J.D.")
assert not me("VANCE, J D", "VANCE, JAMES")
assert not me("VANCE, J D", "VANCE, KAREN")
print("initials tests passed")
