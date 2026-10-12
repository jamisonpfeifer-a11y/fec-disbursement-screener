"""Transaction-level screening rules.

Each Schedule B disbursement is checked against the categories in
config/vendor_categories.yaml and against payee-name checks (same surname as
the candidate, or a committee for someone who shares it). Repeated hits in a
category compound; per-category caps keep one weak signal from dominating.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import yaml


@dataclass
class TransactionFlag:
    category: str
    label: str
    transaction: dict
    reason: str
    score_contribution: float


# Maximum vendor-score contribution per category (default: _DEFAULT_CAP).
_CATEGORY_CAPS = {
    "shared_surname_payee": 4.0,
    "shared_surname_committee": 2.0,
    "vague_high_dollar": 1.5,
    "credit_card_payment": 1.0,
}
_DEFAULT_CAP = 4.0
_TOTAL_CAP = 10.0

# Name-based categories scale with dollars, reaching full weight at this total.
_NAME_BASED = ("shared_surname_payee", "shared_surname_committee")
_FULL_WEIGHT_USD = 5000.0
_MIN_DOLLAR_FACTOR = 0.4


@dataclass
class CommitteeFlagReport:
    committee_id: str
    total_disbursed: float
    flags: list[TransactionFlag] = field(default_factory=list)
    category_totals: dict[str, float] = field(default_factory=dict)  # for peer comparison

    @property
    def vendor_risk_score(self) -> float:
        """Sum of per-category scores, each capped so no single weak category
        can saturate the total."""
        points: dict[str, float] = {}
        dollars: dict[str, float] = {}
        for f in self.flags:
            points[f.category] = points.get(f.category, 0.0) + f.score_contribution
            try:
                amount = abs(float(f.transaction.get("disbursement_amount") or 0))
            except (TypeError, ValueError, AttributeError):
                amount = 0.0
            dollars[f.category] = dollars.get(f.category, 0.0) + amount

        total = 0.0
        for category, value in points.items():
            value = min(value, _CATEGORY_CAPS.get(category, _DEFAULT_CAP))
            if category in _NAME_BASED:
                # Many tiny payments should rank below one large one.
                factor = _MIN_DOLLAR_FACTOR + (1 - _MIN_DOLLAR_FACTOR) * dollars[category] / _FULL_WEIGHT_USD
                value *= min(1.0, factor)
            total += value
        return min(total, _TOTAL_CAP)


def load_categories(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """True if any keyword appears as a whole word (a plural is allowed)."""
    if not text or not keywords:
        return False
    text_lower = text.lower()
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"(?:s|es)?\b"
        if re.search(pattern, text_lower):
            return True
    return False


def _extract_surname_candidates(name: str) -> set[str]:
    """Surname from an FEC-style "LAST, FIRST MIDDLE" name. Only the surname
    is used for surname matching; first names would match self-payments."""
    if not name:
        return set()
    surname = name.split(",")[0].strip().lower()
    return {surname} if len(surname) > 2 else set()


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


_COMMITTEE_RE = re.compile(
    r"\bfor\s+(?:congress|assembly|senate|school\s+board|city\s+council|council|mayor|"
    r"supervisor|governor|judge|sheriff|county|state|district)\b"
    r"|\bfor\b.*\b20\d\d\b|\bcommittee\b|\bcampaign\b|\bfriends\s+of\b|\bcitizens\s+for\b",
    re.I)
_CHAIN_RE = re.compile(r"hotels?\s*(?:&|and)\s*resorts?", re.I)
# "Sherman Oaks", "Culver Heights": a surname followed by a place word is a
# place name, not a person.
_PLACE_RE = re.compile(
    r"\b[a-z]+\s+(?:oaks?|hills?|heights|beach|valley|springs?|canyon|grove|village|creek|ridge)\b",
    re.I)


def _is_committee_payee(recipient: str) -> bool:
    return bool(_COMMITTEE_RE.search(recipient or ""))


def _surname_hit(surnames: set[str], recipient: str) -> bool:
    """Whole-word surname match: "tran" must not match "transport"."""
    r = _PLACE_RE.sub(" ", (recipient or "").lower())
    return any(re.search(r"(?<![a-z])" + re.escape(sn) + r"(?![a-z])", r) for sn in surnames)


def _is_shared_surname_payee(surnames: set[str], recipient: str) -> bool:
    """Payee shares a surname but is not a campaign committee."""
    return bool(surnames) and _surname_hit(surnames, recipient) and not _is_committee_payee(recipient)


# Nicknames that are not simple prefixes of the formal first name.
_KATHERINE = {"katherine", "kathryn", "catherine", "katharine"}
_NICKNAMES = {
    "alex": {"alexander", "alexandra"}, "andy": {"andrew"}, "ben": {"benjamin"},
    "beth": {"elizabeth"}, "betty": {"elizabeth"}, "bill": {"william"},
    "billy": {"william"}, "bob": {"robert"}, "bobby": {"robert"},
    "cathy": _KATHERINE, "charlie": {"charles"}, "chuck": {"charles"},
    "dan": {"daniel"}, "danny": {"daniel"}, "dave": {"david"}, "davey": {"david"},
    "deb": {"deborah"}, "debbie": {"deborah"}, "dick": {"richard"},
    "drew": {"andrew"}, "ed": {"edward"}, "eddie": {"edward"}, "greg": {"gregory"},
    "hank": {"henry"}, "jack": {"john"}, "jake": {"jacob"}, "jen": {"jennifer"},
    "jenny": {"jennifer"}, "jim": {"james"}, "jimmy": {"james"}, "joe": {"joseph"},
    "johnny": {"john"}, "josh": {"joshua"}, "kate": _KATHERINE, "katie": _KATHERINE,
    "kathy": _KATHERINE, "ken": {"kenneth"}, "liz": {"elizabeth"},
    "maggie": {"margaret"}, "matt": {"matthew"}, "mike": {"michael"},
    "mikey": {"michael"}, "nick": {"nicholas"}, "peggy": {"margaret"},
    "pete": {"peter"}, "rich": {"richard"}, "rick": {"richard"}, "rob": {"robert"},
    "robbie": {"robert"}, "ron": {"ronald"}, "sam": {"samuel", "samantha"},
    "steve": {"steven", "stephen"}, "sue": {"susan"}, "susie": {"susan"},
    "ted": {"edward", "theodore"}, "tom": {"thomas"}, "tommy": {"thomas"},
    "tony": {"anthony"}, "will": {"william"},
}


def _first_name_matches(first: str, recip: str) -> bool:
    """True if the candidate's first name appears as a word in the recipient
    name, allowing for nicknames in either direction (candidate listed as
    'TIMOTHY' paid as 'TIM', or candidate listed as 'STAN' paid as 'STANLEY')."""
    if not first:
        return False
    for tok in re.findall(r"[a-z']+", recip.lower()):
        if tok == first:
            return True
        if len(tok) >= 3 and first.startswith(tok):
            return True
        if len(first) >= 3 and tok.startswith(first):
            return True
        if first in _NICKNAMES.get(tok, ()):
            return True
        if tok in _NICKNAMES.get(first, ()):
            return True
    return False


_OFFICE = r"(congress|senate|u\.?s\.?|house|ca\b|california|state|governor|president|assembly)"
_OFFICE_COMPACT = r"for(congress|senate|ushouse|house|california|governor|president|assembly)"

_COMMITTEE_WORDS = {
    "for", "congress", "senate", "u", "s", "us", "house", "ca", "california", "state",
    "governor", "president", "assembly", "committee", "friends", "of", "the", "re",
    "elect", "inc", "pac", "campaign", "citizens", "dr", "mr", "mrs", "ms", "hon",
    "jr", "sr", "ii", "iii", "iv", "md", "district", "representative", "rep",
    "to", "congressman", "congresswoman", "senator",
}


def _other_name_tokens(surname: str, recip: str) -> list[str]:
    """Alphabetic tokens in a committee-style payee other than the candidate's
    surname and generic committee words (i.e. someone else's given name)."""
    sn = set(re.findall(r"[a-z']+", surname.lower()))
    return [t for t in re.findall(r"[a-z']+", recip.lower())
            if t not in sn and t not in _COMMITTEE_WORDS]


def _is_self_payment(candidate_name: str, recipient_name: str) -> bool:
    """True if the recipient is the candidate or their own committee."""
    if not candidate_name or not recipient_name:
        return False
    recip = recipient_name.lower()
    if "personal funds" in recip:
        return True
    parts = [p.strip() for p in candidate_name.lower().split(",")]
    surname = parts[0]
    given = re.findall(r"[a-z']+", parts[1]) if len(parts) > 1 else []
    first = given[0] if given else ""
    if not surname:
        return False
    recip_c = _normalize_name(recip)
    surname_c = _normalize_name(surname)
    if surname not in recip and surname_c not in recip_c:
        return False
    # Own committee ("<NAME> FOR CONGRESS", or without spaces). It only counts
    # as the candidate's own if no one else's name appears in it: "JOSH
    # LOWENTHAL FOR ASSEMBLY" is a different person's committee, not Alan's.
    if re.search(r"\bfor " + _OFFICE, recip):
        if _first_name_matches(first, recip) or not _other_name_tokens(surname, recip):
            return True
    elif re.search(_OFFICE_COMPACT, recip_c):
        return True
    # Surname + first name (or nickname) = the candidate themselves
    if surname in recip and _first_name_matches(first, recip):
        return True
    return False


def _dedupe_disbursements(disbursements: list[dict]) -> list[dict]:
    """Drop repeated records of the same disbursement (amended filings).

    Uses the API's sub_id when present, otherwise a composite key.
    """
    seen = set()
    deduped = []
    for d in disbursements:
        key = d.get("sub_id") or (
            d.get("recipient_name"),
            d.get("disbursement_amount"),
            d.get("disbursement_date"),
            d.get("disbursement_description"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)
    return deduped


def _is_refund(txn: dict) -> bool:
    """Contribution refunds go to donors (who may share a surname with the
    candidate) and are not treated as same-surname payees."""
    desc = (txn.get("disbursement_description") or "").lower()
    cat = (txn.get("disbursement_purpose_category") or "").lower()
    return "refund" in desc or "refund" in cat


def flag_disbursements(
    disbursements: list[dict],
    config: dict,
    candidate_name: str | None = None,
    staff_names: list[str] | None = None,
) -> CommitteeFlagReport:
    """Flag one committee's disbursements.

    disbursements: Schedule B records from FECClient.get_disbursements
    config: parsed vendor_categories.yaml
    candidate_name, staff_names: surnames used for the shared-surname checks
    """
    categories = config["categories"]
    peer_categories = config.get("peer_comparison_categories", {})
    card_keywords = categories.get("credit_card_payment", {}).get("keywords", [])

    disbursements = _dedupe_disbursements(disbursements)

    committee_id = disbursements[0]["committee_id"] if disbursements else "unknown"
    total_disbursed = sum(float(d.get("disbursement_amount") or 0) for d in disbursements)

    report = CommitteeFlagReport(committee_id=committee_id, total_disbursed=total_disbursed)

    # Hits so far per category, for escalation.
    category_hit_counts: dict[str, int] = defaultdict(int)

    surnames = set()
    if candidate_name:
        surnames |= _extract_surname_candidates(candidate_name)
    for s in (staff_names or []):
        surnames |= _extract_surname_candidates(s)

    for txn in disbursements:
        recipient = txn.get("recipient_name") or ""
        description = txn.get("disbursement_description") or ""
        amount = float(txn.get("disbursement_amount") or 0)
        combined_text = f"{recipient} {description}"
        is_self = _is_self_payment(candidate_name or "", recipient)
        is_refund = _is_refund(txn)
        is_card = _matches_keywords(recipient, card_keywords)
        # Not a shared-surname signal: self-payments, donor refunds, and card issuers
        # whose names happen to contain the cardholder's surname.
        skip_surname = is_self or is_refund or is_card

        for cat_key, cat_def in categories.items():
            if cat_key == "shared_surname_payee":
                if skip_surname:
                    continue
                if _is_shared_surname_payee(surnames, recipient):
                    _apply_flag(report, category_hit_counts, cat_key, cat_def, txn,
                                reason=f"Recipient name overlaps candidate/staff surname: '{recipient}'")
                continue
            if cat_key == "shared_surname_committee":
                if skip_surname:
                    continue
                if surnames and _surname_hit(surnames, recipient) and _is_committee_payee(recipient):
                    _apply_flag(report, category_hit_counts, cat_key, cat_def, txn,
                                reason=f"Payment to campaign committee sharing candidate/staff surname: '{recipient}'")
                continue

            # Card payments match on the payee only; hotel-chain names
            # ("Hotels & Resorts") are not resort stays.
            text = recipient if cat_key == "credit_card_payment" else combined_text
            if cat_key == "luxury_travel":
                text = _CHAIN_RE.sub(" ", text)
            if not _matches_keywords(text, cat_def.get("keywords", [])):
                continue
            if cat_key == "vague_high_dollar" and is_self:
                continue  # repaying the candidate is a specific disclosure
            if amount < cat_def.get("per_transaction_flag_usd", 0):
                continue

            _apply_flag(report, category_hit_counts, cat_key, cat_def, txn,
                        reason=f"Matched category '{cat_def['label']}' (${amount:,.2f} at '{recipient}')")

        # Peer-comparison totals, whether or not the payment was flagged.
        for pcat_key, pcat_def in peer_categories.items():
            if pcat_key == "shared_surname_spend":
                if not skip_surname and _is_shared_surname_payee(surnames, recipient):
                    report.category_totals[pcat_key] = report.category_totals.get(pcat_key, 0) + amount
                continue
            if _matches_keywords(combined_text, pcat_def.get("keywords", [])):
                report.category_totals[pcat_key] = report.category_totals.get(pcat_key, 0) + amount

    return report


def _apply_flag(report: CommitteeFlagReport, category_hit_counts: dict[str, int],
                cat_key: str, cat_def: dict, txn: dict, reason: str) -> None:
    category_hit_counts[cat_key] += 1
    base_weight = cat_def.get("weight", 0.3)
    if cat_def.get("escalation") and category_hit_counts[cat_key] > 1:
        # Repeat hits in one category compound (e.g. the same kind of charge
        # again and again) instead of counting as independent events.
        multiplier = 1 + 0.25 * (category_hit_counts[cat_key] - 1)
    else:
        multiplier = 1.0
    contribution = base_weight * multiplier
    report.flags.append(
        TransactionFlag(
            category=cat_key,
            label=cat_def["label"],
            transaction=txn,
            reason=reason,
            score_contribution=contribution,
        )
    )
