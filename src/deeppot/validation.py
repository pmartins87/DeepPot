from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from statistics import mean, pstdev
from typing import Mapping, Sequence

Policy = Mapping[str, tuple[float, float]]


@dataclass(frozen=True)
class PairwisePolicyAudit:
    seed_a: int
    seed_b: int
    shared_infosets: int
    union_infosets: int
    shared_coverage: float
    mean_abs_diff_stay: float
    p95_abs_diff_stay: float
    max_abs_diff_stay: float
    greedy_agreement: float


@dataclass(frozen=True)
class ConsensusPolicyAudit:
    shared_all_infosets: int
    union_infosets: int
    shared_all_coverage: float
    mean_std_stay: float
    p95_std_stay: float
    max_std_stay: float
    greedy_agreement_all: float
    stability_hint: str
    stability_reason: str


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def compare_policies(seed_a: int, a: Policy, seed_b: int, b: Policy) -> PairwisePolicyAudit:
    ka, kb = set(a), set(b)
    shared = sorted(ka & kb)
    union = ka | kb
    diffs = [abs(a[k][1] - b[k][1]) for k in shared]
    agree = [((a[k][1] >= 0.5) == (b[k][1] >= 0.5)) for k in shared]
    return PairwisePolicyAudit(
        seed_a=seed_a,
        seed_b=seed_b,
        shared_infosets=len(shared),
        union_infosets=len(union),
        shared_coverage=(len(shared) / len(union)) if union else 1.0,
        mean_abs_diff_stay=mean(diffs) if diffs else 0.0,
        p95_abs_diff_stay=_percentile(diffs, 0.95),
        max_abs_diff_stay=max(diffs) if diffs else 0.0,
        greedy_agreement=(sum(agree) / len(agree)) if agree else 1.0,
    )


def build_consensus(seed_policies: Mapping[int, Policy]) -> tuple[list[PairwisePolicyAudit], ConsensusPolicyAudit]:
    items = sorted(seed_policies.items())
    pairwise = [compare_policies(sa, pa, sb, pb) for (sa, pa), (sb, pb) in combinations(items, 2)]
    if not items:
        return pairwise, ConsensusPolicyAudit(0, 0, 1.0, 0.0, 0.0, 0.0, 1.0, "insufficient", "No solves supplied.")
    key_sets = [set(p) for _, p in items]
    union = set().union(*key_sets)
    shared_all = set.intersection(*key_sets)
    stds = []
    unanimous = []
    for key in shared_all:
        probs = [p[key][1] for _, p in items]
        stds.append(pstdev(probs))
        greedy = [x >= 0.5 for x in probs]
        unanimous.append(all(x == greedy[0] for x in greedy))

    mean_pair = mean([p.mean_abs_diff_stay for p in pairwise]) if pairwise else 0.0
    p95_pair = mean([p.p95_abs_diff_stay for p in pairwise]) if pairwise else 0.0
    max_pair = max([p.max_abs_diff_stay for p in pairwise], default=0.0)
    greedy_pair = mean([p.greedy_agreement for p in pairwise]) if pairwise else 1.0
    coverage = len(shared_all) / len(union) if union else 1.0
    mean_std = mean(stds) if stds else 0.0
    p95_std = _percentile(stds, 0.95)
    max_std = max(stds, default=0.0)

    if len(items) < 2:
        hint, reason = "insufficient", "Fewer than two solves."
    elif coverage >= 0.99 and mean_pair <= 0.02 and p95_pair <= 0.05 and max_pair <= 0.15 and greedy_pair >= 0.95:
        hint, reason = "stable", "High shared coverage and close cross-seed policies."
    elif coverage >= 0.95 and mean_pair <= 0.05 and p95_pair <= 0.12 and max_pair <= 0.35 and greedy_pair >= 0.88:
        hint, reason = "moderate", "Partial convergence; more sampling/refinement is required."
    else:
        hint, reason = "unstable", "Cross-seed policy differences remain too large for a base reference."

    return pairwise, ConsensusPolicyAudit(
        shared_all_infosets=len(shared_all),
        union_infosets=len(union),
        shared_all_coverage=coverage,
        mean_std_stay=mean_std,
        p95_std_stay=p95_std,
        max_std_stay=max_std,
        greedy_agreement_all=(sum(unanimous) / len(unanimous)) if unanimous else 1.0,
        stability_hint=hint,
        stability_reason=reason,
    )


def audit_to_dict(x: PairwisePolicyAudit | ConsensusPolicyAudit) -> dict:
    return asdict(x)
