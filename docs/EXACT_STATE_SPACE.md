# DeepPot exact state space — no strategic card abstraction

Reference date: 2026-09-07

## Decision

The production research path is now **exact-state first**.

DeepPot will not introduce equity buckets, potential buckets, rank-class buckets, or any other strategically lossy card abstraction merely because the first 10k-iteration pilot was sparse. Suit isomorphism is retained because it is an exact game symmetry: relabeling clubs/diamonds/hearts/spades does not change poker strategy. This is canonicalization, not strategic abstraction.

A lossy abstraction becomes a fallback only if a measured exact-state implementation proves computationally infeasible after evaluator, storage, batching, variance-reduction and parallelization work.

## Why `1,755 flops x 169 hands` is not actually 100% exact

There are 1,755 NLH flop classes modulo suit relabeling. However, the familiar 169 preflop hand classes are not sufficient once the flop is visible.

Example on `Qh 7h 2c`:

- `Ah Kh` is AKs and has a nut-heart flush draw;
- `Ac Kc` is also AKs but does not have that heart draw.

They are the same 169-class label but strategically different flop states. The same issue appears with blockers, backdoor suits and board-relative suit structure.

Therefore a truly lossless DeepPot state must preserve the exact relationship between the two hole cards and the three flop cards, while quotienting only globally equivalent suit renamings.

## Exact count

Before suit isomorphism there are:

`C(52,3) * C(49,2) = 22,100 * 1,176 = 25,989,600`

partitioned `(flop, hero hole)` states.

Using Burnside's lemma over the 24 suit permutations, the exact number of strategically distinct flop+hole states is:

**1,286,792**

The fixed-state counts by S4 conjugacy class are:

| Suit permutation type | Multiplicity | Fixed partitioned states |
|---|---:|---:|
| identity `(1,1,1,1)` | 1 | 25,989,600 |
| one swap `(2,1,1)` | 6 | 797,056 |
| two swaps `(2,2)` | 3 | 0 |
| 3-cycle `(3,1)` | 8 | 13,884 |
| 4-cycle `(4)` | 6 | 0 |

Burnside:

`(25,989,600 + 6*797,056 + 8*13,884) / 24 = 1,286,792`.

The code that derives this count lives in `src/deeppot/state_space.py` and is regression-tested.

## Comparison with the 169-class idea

`1,755 * 169 = 296,595` states.

The exact suit-isomorphic state space is only about **4.34x larger**:

`1,286,792 / 296,595 = 4.33855`.

That is a very important result. Exactness is more expensive than a 169-class-per-flop representation, but not by orders of magnitude.

Across the 1,755 canonical flops, the number of exact hero-hole orbits per flop is not constant. Exact enumeration gives this distribution:

| Exact hole states on the canonical flop | Number of canonical flops |
|---:|---:|
| 344 | 286 |
| 378 | 13 |
| 721 | 1,014 |
| 744 | 156 |
| 1,176 | 286 |

Total: **1,286,792**, average **733.215 exact hole states per canonical flop**.

## Public FOLD/STAY histories

For `N` dealt players, every actor before BTN may face all binary histories of previous actions. BTN does not act in the single history where every prior player folded because the hand has already ended.

The number of nonterminal public decision scenarios is therefore:

`2^N - 2`.

| Players | Public decision scenarios | Dense exact infoset upper count over all flops |
|---:|---:|---:|
| 2 | 2 | 2,573,584 |
| 3 | 6 | 7,720,752 |
| 4 | 14 | 18,015,088 |
| 5 | 30 | 38,603,760 |
| 6 | 62 | 79,781,104 |
| 7 | 126 | 162,135,792 |
| 8 | 254 | 326,845,168 |

These are dense upper counts: a production solver can process one canonical flop at a time, keep only the current flop's nodes in RAM, checkpoint/export the solved policy, and move on. We therefore do **not** need hundreds of millions of Python dictionary nodes resident simultaneously.

## What “100% precision” can and cannot mean

There are two different concepts:

1. **100% state fidelity:** no strategically distinct flop/hole state is merged with another. This is the target and is achievable with the 1,286,792 exact suit-isomorphic states.
2. **exact equilibrium to infinite numerical precision:** no iterative/sampled solver can literally guarantee this with finite compute. The numerical solution still needs convergence tolerances, cross-seed stability and response/exploitability validation.

DeepPot will target the first absolutely and push the second as far as practical with measured convergence criteria.

## Why the first pilot does not justify abstraction

The A72r HU pilot used only 10,000 sampled deals per seed. The observed median of roughly 8 visits per exact infoset follows directly from the state count of that flop. Instability at 8 visits is expected; it is not evidence that the exact state space is too large.

Before considering any lossy abstraction, the exact path must test:

1. a much faster evaluator and terminal payoff path;
2. batched/vectorized deal generation and regret updates, borrowing the successful DeepKK architecture;
3. multiprocessing across canonical flops;
4. checkpoint/resume and per-flop work scheduling;
5. variance reduction / better CFR sampling schemes that preserve exact infosets;
6. dense integer-indexed arrays instead of Python string-key dictionaries where possible;
7. exact HU validation and then staged 3w/4w/.../8w scaling;
8. workload estimates from measured visits-per-second, not from the 10k smoke pilot.

## Production policy principle

Default:

`exact flop+hole state -> exact public history -> exact player-count mode -> FOLD/STAY policy`

Only global suit relabeling is collapsed.

No equity/potential clustering is part of the production plan unless the exact route fails an explicit computational feasibility gate.