"""Peer comparison: flag candidates whose spending mix is an outlier.

Candidates are grouped by office, state, party, incumbency and cycle. For
each spending category, a candidate's share of total spending is compared
with the peer group using the median and MAD (median absolute deviation).

- Shares, not dollars, so campaign size does not confound the comparison.
- Median and MAD, not mean and standard deviation: campaign spending is
  right-skewed, and a few large spenders would otherwise mask everyone else.
- Groups smaller than MIN_PEER_GROUP_SIZE are relaxed (incumbency, then party)
  and, if still too small, not scored.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_PEER_GROUP_SIZE = 5
MAD_CONSTANT = 1.4826  # makes MAD comparable to a standard deviation if data are normal
# Stand-in z-score when peers show no spread at all and the candidate is above them.
ZERO_SPREAD_Z = 10.0


@dataclass
class CandidateSpendProfile:
    candidate_id: str
    candidate_name: str
    committee_id: str
    office: str
    state: str
    party: str
    incumbent_challenge: str  # 'I', 'C', 'O'
    cycle: int
    total_disbursed: float
    category_totals: dict[str, float]  # from CommitteeFlagReport.category_totals

    def category_share(self, category: str) -> float:
        if self.total_disbursed <= 0:
            return 0.0
        return self.category_totals.get(category, 0.0) / self.total_disbursed


@dataclass
class PeerAnomalyResult:
    candidate_id: str
    category: str
    candidate_share: float
    peer_median_share: float
    peer_mad: float
    robust_z: float
    peer_group_size: int
    peer_group_key: tuple


def _peer_group_key(profile: CandidateSpendProfile) -> tuple:
    return (profile.office, profile.state, profile.party, profile.incumbent_challenge, profile.cycle)


def build_peer_groups(profiles: list[CandidateSpendProfile]) -> dict[tuple, list[CandidateSpendProfile]]:
    groups: dict[tuple, list[CandidateSpendProfile]] = {}
    for p in profiles:
        key = _peer_group_key(p)
        groups.setdefault(key, []).append(p)
    return groups


def _relax_peer_group_key(key: tuple) -> tuple | None:
    """Loosen a peer-group key: drop incumbency first, then party.

    Office, state and cycle always stay fixed, since geography and office
    drive costs and campaign scale. Returns None when nothing is left to drop.
    """
    office, state, party, incumbent_challenge, cycle = key
    if incumbent_challenge is not None:
        return (office, state, party, None, cycle)
    if party is not None:
        return (office, state, None, None, cycle)
    return None


def compute_peer_anomalies(
    profiles: list[CandidateSpendProfile],
    categories: list[str],
) -> list[PeerAnomalyResult]:
    groups = build_peer_groups(profiles)
    results: list[PeerAnomalyResult] = []

    for profile in profiles:
        key = _peer_group_key(profile)
        peer_group = groups.get(key, [])

        # Widen the peer group if the exact match is too small.
        while len(peer_group) < MIN_PEER_GROUP_SIZE:
            relaxed_key = _relax_peer_group_key(key)
            if relaxed_key is None:
                break
            key = relaxed_key
            peer_group = [
                p for p in profiles
                if _peer_group_key(p)[:1] == key[:1]  # office match always required
                and (key[1] is None or _peer_group_key(p)[1] == key[1])
                and (key[2] is None or _peer_group_key(p)[2] == key[2])
                and (key[3] is None or _peer_group_key(p)[3] == key[3])
                and _peer_group_key(p)[4] == key[4]
            ]

        if len(peer_group) < MIN_PEER_GROUP_SIZE:
            continue  # too few peers for a meaningful comparison

        for category in categories:
            shares = np.array([p.category_share(category) for p in peer_group])
            median = float(np.median(shares))
            mad = float(np.median(np.abs(shares - median))) * MAD_CONSTANT

            candidate_share = profile.category_share(category)

            if mad == 0:
                # Peers show no spread: any excess over the median is notable,
                # but avoid dividing by zero.
                robust_z = ZERO_SPREAD_Z if candidate_share > median else 0.0
            else:
                robust_z = (candidate_share - median) / mad

            results.append(
                PeerAnomalyResult(
                    candidate_id=profile.candidate_id,
                    category=category,
                    candidate_share=candidate_share,
                    peer_median_share=median,
                    peer_mad=mad,
                    robust_z=robust_z,
                    peer_group_size=len(peer_group),
                    peer_group_key=key,
                )
            )

    return results


def anomalies_to_dataframe(results: list[PeerAnomalyResult]) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in results])
