from __future__ import annotations

from .fast_solver import FastChanceSampledCFR, FastSampledDeal
from .solver import InfoNode, SolveResult


class FastChanceSampledCFRV2(FastChanceSampledCFR):
    """Second exact Python fast-kernel candidate.

    Pot Fold's public tree is strictly sequential: actor 0 acts at most once,
    then actor 1, and so on. Therefore, when an actor is reached, that actor's
    own reach probability is always exactly 1.0; only prior actors contribute
    to counterfactual reach.

    The reference solver materializes a full reach vector and, at every node,
    multiplies all opponent entries to reconstruct counterfactual reach. V2
    carries that already-ordered prior-path product as one scalar instead.

    This is an implementation optimization only. It preserves:
      * the same exact chance/RNG trajectory;
      * the same public/private state mapping;
      * FOLD-before-STAY traversal;
      * the same CFR+ updates;
      * the same global linear-average weights;
      * the same terminal utilities.

    Differential tests must remain bit/numerically exact against the reference
    solver before this candidate can be used by continuous production.
    """

    def _cfr_fast_v2(
        self,
        sid: int,
        deal: FastSampledDeal,
        prior_path_reach: float,
        iteration_weight: float,
    ) -> tuple[float, ...]:
        actor = self._fast_actor_by_sid[sid]
        key = sid * self.hole_state_count + deal.hole_state_ids[actor]
        node = self.nodes.get(key)
        if node is None:
            node = InfoNode()
            self.nodes[key] = node

        r0 = node.regrets[0]
        r1 = node.regrets[1]
        p0 = r0 if r0 > 0.0 else 0.0
        p1 = r1 if r1 > 0.0 else 0.0
        total = p0 + p1
        if total <= 0.0:
            s0 = 0.5
            s1 = 0.5
        else:
            s0 = p0 / total
            s1 = p1 / total
        node.visits += 1

        # Reference traversal order is FOLD first, STAY second. Because each
        # player acts at most once, the next actor's counterfactual reach is
        # exactly the current prior-path product times this actor's action prob.
        child0 = self._fast_fold_child[sid]
        if child0 >= 0:
            util0 = self._cfr_fast_v2(
                child0,
                deal,
                prior_path_reach * s0,
                iteration_weight,
            )
        else:
            util0 = self._terminal_fast(child0, deal)

        child1 = self._fast_stay_child[sid]
        if child1 >= 0:
            util1 = self._cfr_fast_v2(
                child1,
                deal,
                prior_path_reach * s1,
                iteration_weight,
            )
        else:
            util1 = self._terminal_fast(child1, deal)

        node_util = tuple(s0 * util0[p] + s1 * util1[p] for p in range(self.num_players))
        actor_util = node_util[actor]

        nr0 = node.regrets[0] + prior_path_reach * (util0[actor] - actor_util)
        nr1 = node.regrets[1] + prior_path_reach * (util1[actor] - actor_util)
        if self.cfr_plus:
            if nr0 < 0.0:
                nr0 = 0.0
            if nr1 < 0.0:
                nr1 = 0.0
        node.regrets[0] = nr0
        node.regrets[1] = nr1

        # In this strictly sequential one-decision-per-player tree,
        # reach[actor] in the reference implementation is always 1.0 here.
        node.strategy_sum[0] += iteration_weight * s0
        node.strategy_sum[1] += iteration_weight * s1
        return node_util

    def _run_iterations(self, iterations: int, *, iteration_offset: int) -> SolveResult:
        if iterations <= 0:
            raise ValueError("iterations must be > 0")
        if iteration_offset < 0:
            raise ValueError("iteration_offset must be >= 0")
        root_sid = 0
        for local_iteration in range(1, iterations + 1):
            iteration = iteration_offset + local_iteration
            deal = self._sample_fast_deal()
            self._cfr_fast_v2(root_sid, deal, 1.0, float(iteration))
        return SolveResult(
            iterations=iteration_offset + iterations,
            seed=self.seed,
            nodes=self.nodes,
            hole_state_count=self.hole_state_count,
            flop_key=self.exact_index.flop_key,
        )
