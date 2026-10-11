import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import _is_self_payment, _surname_hit

assert _is_self_payment("MIN, DAVE", "MIN, DAVID K.")
assert not _surname_hit({"tran"}, "MONTWAY AUTO TRANSPORT")
assert not _surname_hit({"tran"}, "CALIFORNIA EXCURSIONS & TRANSPORTATION INC")
assert _surname_hit({"tran"}, "TRAN, LINDA")
assert not _surname_hit({"min"}, "MINDY SMITH")
assert _surname_hit({"hafif"}, "LAW OFFICE OF HERBERT HAFIF")
print("surname word-boundary tests passed")
