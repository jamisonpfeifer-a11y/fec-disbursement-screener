import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vendor_rules import _is_self_payment as me

# own committee, various spellings: still self
assert me("PORTER, KATHERINE", "KATIE PORTER FOR SENATE")
assert me("SIKDER, ABDUR R DR", "DRSIKDERFORCONGRESS")
assert me("SIKDER, ABDUR R DR", "SIKDER FOR CONGRESS")
assert me("LIEU, TED", "TED LIEU FOR CONGRESS")
assert me("ENGDAHL, ANDREW DAVID", "ENGDAHL FOR CONGRESS 2024")
assert me("CURRY, ERIC", "ERIC CURRY FOR CONGRESS")
# another person's committee with the same office wording is NOT self
assert not me("LOWENTHAL, ALAN", "JOSH LOWENTHAL FOR ASSEMBLY 2024")
assert not me("LOWENTHAL, ALAN", "JOSH LOWENTHAL FOR ASSEMNBLY 2024")
assert not me("LIEU, TED", "BETTY LIEU FOR CONGRESS")
print("own-committee tests passed")
