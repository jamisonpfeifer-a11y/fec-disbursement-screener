"""Combine vendor flags and peer anomalies into one ranked list for review.

The composite is deliberately simple so a reviewer can see exactly why a
candidate scored as they did.
"""
from __future__ import annotations

from dataclasses import dataclass

from .peer_comparison import PeerAnomalyResult
from .vendor_rules import CommitteeFlagReport

# Peer anomalies below this z-score are ignored.
PEER_Z_FLAG_THRESHOLD = 3.0

# Weights in the composite score. A peer deviation is weaker evidence than an
# explicit vendor flag: it suggests a closer look, not behavior of concern.
VENDOR_FLAG_WEIGHT = 1.0
PEER_ANOMALY_WEIGHT = 0.6

# Robust z-scores explode when nearly every peer spends ~0% in a category
# (tiny median and MAD): an ordinary 9% lodging share can come out at z=85.
# So the spread is floored at PEER_MIN_SCALE of total spending, z is capped,
# and only spending above peers counts.
PEER_MIN_SCALE = 0.03  # 3 percentage points of total spend
PEER_Z_CAP = 8.0
_MAD_TO_SIGMA = 1.4826

# Peer score = sum of qualifying z-scores * PEER_SCORE_PER_Z, up to PEER_SCORE_CAP.
PEER_SCORE_PER_Z = 0.1
PEER_SCORE_CAP = 5.0


# A payee flagged for this many committees or more is probably an institution
# (a conference venue, a card issuer, a large vendor), not a one-off.
COMMON_PAYEE_MIN_COMMITTEES = 3
COMMON_PAYEE_FACTOR = 0.5
# Flags tied to the candidate's own name are specific to that candidate.
_NAME_BASED = ("shared_surname_payee", "shared_surname_committee")


@dataclass
class CandidateRiskSummary:
    candidate_id: str
    candidate_name: str
    committee_id: str
    vendor_score: float
    peer_anomaly_score: float
    composite_score: float
    vendor_flags: list[dict]
    peer_anomalies: list[dict]


def _payee_key(flag) -> str:
    return " ".join(str(flag.transaction.get("recipient_name") or "").upper().split())


def damp_common_payees(
    reports: list[CommitteeFlagReport],
    min_committees: int = COMMON_PAYEE_MIN_COMMITTEES,
    factor: float = COMMON_PAYEE_FACTOR,
) -> dict[str, int]:
    """Halve the weight of flags on payees flagged across many committees.

    Returns {payee: committee count} for the payees that were damped.
    Name-based flags are left alone. Safe to call once per scoring run.
    """
    committees: dict[str, set[str]] = {}
    for rep in reports:
        for f in rep.flags:
            if f.category in _NAME_BASED:
                continue
            key = _payee_key(f)
            if key:
                committees.setdefault(key, set()).add(rep.committee_id)
    common = {k: len(v) for k, v in committees.items() if len(v) >= min_committees}
    for rep in reports:
        for f in rep.flags:
            if f.category not in _NAME_BASED and _payee_key(f) in common:
                f.score_contribution *= factor
    return common


def effective_peer_z(r: PeerAnomalyResult) -> float:
    """Robust z with a floored spread and a cap. Zero unless above peers."""
    diff = r.candidate_share - r.peer_median_share
    if diff <= 0:
        return 0.0
    floored_z = diff / (PEER_MIN_SCALE * _MAD_TO_SIGMA)
    return min(abs(r.robust_z), floored_z, PEER_Z_CAP)


def score_candidate(
    candidate_id: str,
    candidate_name: str,
    vendor_report: CommitteeFlagReport,
    peer_results: list[PeerAnomalyResult],
) -> CandidateRiskSummary:
    vendor_score = vendor_report.vendor_risk_score

    notable_peer_hits = [r for r in peer_results if effective_peer_z(r) >= PEER_Z_FLAG_THRESHOLD]
    peer_anomaly_score = min(sum(effective_peer_z(r) for r in notable_peer_hits) * PEER_SCORE_PER_Z, PEER_SCORE_CAP)

    composite = VENDOR_FLAG_WEIGHT * vendor_score + PEER_ANOMALY_WEIGHT * peer_anomaly_score

    return CandidateRiskSummary(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        committee_id=vendor_report.committee_id,
        vendor_score=round(vendor_score, 2),
        peer_anomaly_score=round(peer_anomaly_score, 2),
        composite_score=round(composite, 2),
        vendor_flags=[
            {
                "category": f.category,
                "label": f.label,
                "reason": f.reason,
                "amount": f.transaction.get("disbursement_amount"),
                "recipient": f.transaction.get("recipient_name"),
                "date": f.transaction.get("disbursement_date"),
                "description": f.transaction.get("disbursement_description"),
                "sub_id": f.transaction.get("sub_id"),
                "image_number": f.transaction.get("image_number"),
                "pdf_url": f.transaction.get("pdf_url"),
                "score_contribution": round(f.score_contribution, 2),
            }
            for f in vendor_report.flags
        ],
        peer_anomalies=[
            {
                "category": r.category,
                "candidate_share": round(r.candidate_share, 4),
                "peer_median_share": round(r.peer_median_share, 4),
                "robust_z": round(effective_peer_z(r), 2),
                "raw_robust_z": round(r.robust_z, 2),
                "peer_group_size": r.peer_group_size,
                "peer_group_key": r.peer_group_key,
            }
            for r in notable_peer_hits
        ],
    )


def rank_candidates(summaries: list[CandidateRiskSummary]) -> list[CandidateRiskSummary]:
    return sorted(summaries, key=lambda s: s.composite_score, reverse=True)
