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

# past campaigns and joint victory funds named for the candidate are still self
assert me("DE BLASIO, BILL", "DE BLASIO 2020")
assert me("LAWLER, MICHAEL VINCENT", "LAWLER VICTORY FUND")
assert me("MALLIOTAKIS, NICOLE", "MALLIOTAKIS VICTORY COMMITTEE")
# someone else's named committee is not
assert not me("RYAN, PATRICK", "JULIA RYAN 2022")
assert not me("RYAN, PATRICK", "JULIA RYAN VICTORY FUND")
from src.vendor_rules import _is_committee_payee
assert _is_committee_payee("DE BLASIO 2020") and _is_committee_payee("DESPOSITO VICTORY FUND")
assert not _is_committee_payee("TARGETED VICTORY LLC")
print("named committee tests passed")

# nicknames, "TEAM <SURNAME>", "<SURNAME> FOR <cause>"
assert me("WILSON, TAMARA", "WILSON, TAMIE")
assert me("JORDAN, JAMES D.", "TEAM JORDAN")
assert me("SYKES, EMILIA", "SYKES FOR STRONG SCHOOLS")
assert not me("SYKES, EMILIA", "ANNA SYKES FOR STRONG SCHOOLS")
assert not me("WILSON, TAMARA", "WILSON, ANTHONY")
assert not me("JORDAN, JAMES D.", "TEAM SPIRIT LLC")
print("team and nickname tests passed")

# joint fundraising committee led by the candidate's surname is their own
assert me("CASEY, ROBERT P. JR.", "CASEY FETTERMAN VICTORY FUND")
assert not me("RYAN, PATRICK", "JULIA RYAN VICTORY FUND")
print("joint committee tests passed")
