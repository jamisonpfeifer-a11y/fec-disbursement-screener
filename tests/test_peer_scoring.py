import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.risk_scoring import effective_peer_z, score_candidate
from src.peer_comparison import PeerAnomalyResult
from src.vendor_rules import CommitteeFlagReport
def R(share, med, z, cat="lodging"):
    return PeerAnomalyResult("X", cat, share, med, 0.0007, z, 88, ("H","CA","REP","I",2024))
# Duarte: 9% lodging vs median 0.07%, raw z 85 -> should NOT be flagged now
assert effective_peer_z(R(0.0903, 0.0007, 85.58)) < 3, effective_peer_z(R(0.0903, 0.0007, 85.58))
# Conway 10.3% lodging raw z 97.8
assert effective_peer_z(R(0.103, 0.0007, 97.77)) < 3.5
# Lofgren: 28% catering vs 1% median -> strong, flagged
z = effective_peer_z(R(0.2838, 0.01, 18.38, "catering_events")); assert z > 5, z
# Issa 17% catering vs 0.3%
z = effective_peer_z(R(0.1723, 0.0032, 35.35, "catering_events")); assert 3 < z < 8, z
# spending LESS than peers is never an anomaly
assert effective_peer_z(R(0.01, 0.28, -18.0, "catering_events")) == 0.0
# cap
assert effective_peer_z(R(0.9, 0.0, 500.0)) == 8.0
rep = CommitteeFlagReport("C1", 1000.0)
s = score_candidate("X", "TEST, A", rep, [R(0.0903, 0.0007, 85.58)])
assert s.peer_anomaly_score == 0 and s.composite_score == 0, (s.peer_anomaly_score, s.composite_score)
s = score_candidate("X", "TEST, A", rep, [R(0.2838, 0.01, 18.38, "catering_events")])
assert s.peer_anomaly_score > 0 and s.peer_anomalies[0]["raw_robust_z"] == 18.38
print("peer scoring tests ok", round(s.peer_anomaly_score, 2))
