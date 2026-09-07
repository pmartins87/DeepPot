# P4C — single allowed multiway solver correction

Frozen: 2026-09-07, **before any corrected P4C representative rerun**.

## Why the correction is activated

The frozen raw P4C candidate is exact-state CFR+ with the fixed per-N budgets in `ROADMAP.md`. The first completed multiway gates already demonstrate material unilateral-response gaps despite 100% exact policy coverage, including both N=3 representative textures and N=5 monotone. This is consistent with the known limitation that multiplayer rake makes the game general-sum; raw CFR average-policy convergence is not by itself a Nash-equilibrium guarantee.

The roadmap permits exactly **one solver-method correction targeted at response quality**, followed by exactly one rerun of failing representative cases.

## Frozen correction method

Method: `finite_multiplayer_fictitious_response_average`

Representation remains exact:

- no equity buckets;
- no potential buckets;
- no 169-hand collapse;
- only exact global suit-isomorphism reduction.

For each failing N/texture case:

1. rebuild the same deterministic raw CFR consensus with its already-frozen initial budget;
2. run exactly **32** response-refinement rounds;
3. each round learns every seat's pure unilateral best response to the current average policy using the exact public FOLD/STAY tree and sampled chance deals;
4. update every exact behavioral probability toward its seat's response using
   `alpha_t = 1 / (4 + t)` for `t=1..32`;
5. the initial CFR consensus therefore carries prior weight 4;
6. use deterministic seed base **9402026**;
7. after round 32, stop unconditionally and rerun the original frozen P4C holdout gate once.

### Samples per refinement round

- N=3–4: **50,000** sampled chance deals/round;
- N=5–8: **25,000** sampled chance deals/round.

No texture-specific parameters are allowed.

## Corrected gate

The corrected policy is evaluated with exactly the same P4C gate and sample budget already frozen in `ROADMAP.md`:

- N=3–4: 250k learn + 250k independent holdout;
- N=5–8: 100k learn + 100k independent holdout;
- exact policy coverage must be 100%;
- every seat's unilateral-gain 95% upper bound must be <= **0.03 ante**.

## No-tuning rule

After this document is committed:

- no change to 32 rounds;
- no change to per-round sample counts;
- no alpha/prior-weight sweep;
- no alternate seed search;
- no threshold relaxation;
- no additional iteration rung.

If any failing raw case still fails its one corrected rerun, P4C is **BLOCKED under this solver family** and the project follows the roadmap's method-change contingency. We do not run a second refinement configuration.
