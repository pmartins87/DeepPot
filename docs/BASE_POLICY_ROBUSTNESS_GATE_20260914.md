# DeepPot base-policy robustness gate — SEL3500

Date: 2026-09-14

## Purpose

Resolve the production-base question after SEL3500 without assuming that the real KKPoker population plays CFR and without building a population-exploitation database prematurely.

The candidates are:

1. `mixed`: the true SEL3500 average CFR policy;
2. `greedy`: deterministic majority action from SEL3500 average CFR;
3. `hybrid60`: purify only when the CFR majority probability is at least 60%; otherwise retain the CFR mix;
4. `hybrid70`;
5. `hybrid80`;
6. `hybrid90`.

The current live baseline is **SEL3500 greedy**. This gate is read-only and cannot alter that baseline automatically.

## Why this gate exists

The frequency-vs-EV audit against mixed-CFR opponents found strong monotonic alignment between CFR majority frequency and the EV-best pure action:

- 50–55% majority: weak/noisy alignment;
- 60–70%: materially better alignment;
- 70–80%: strong alignment;
- 80–90%: very strong alignment;
- 90–100%: effectively perfect in the sampled confident states.

That result supports the user's hypothesis that CFR majority frequency may be a useful practical proxy for action quality, but it was measured against CFR opponents only. The next finite question is whether greedy/purified policies remain robust when opponents are fixed and non-adaptive but systematically deviate from CFR.

## Fixed opponent families

All families are derived from the SEL3500 average policy and are fixed during a hand; none adapts to Hero.

1. `cfr_mixed` — unchanged SEL3500 average policy;
2. `cfr_greedy` — every opponent action purified at 50%;
3. `tight` — logit(STAY) shifted by -0.60;
4. `loose` — logit(STAY) shifted by +0.60;
5. `sharpened` — logit multiplied by 1.75 (more deterministic around the same side);
6. `flattened` — logit multiplied by 0.60 (more random/less polarized);
7. `early_tight_late_loose` — position-dependent logit shift from -0.60 for the first actor to +0.60 for the last actor;
8. `early_loose_late_tight` — reverse positional shift.

These are **stress-test families**, not claims about the actual KKPoker population.

## Finite sampling protocol

Frozen before results:

- SEL3500 persistent CFR state;
- 4 canonical flop tasks sampled per N for N=2..8 (28 tasks total);
- 1,500 common-random chance deals per task;
- same chance deals reused across all opponent families within each task;
- provisional gross rake remains 2%;
- observed Hero cashback is added as 0.70% of Hero contribution for policy-comparison EV;
- Hero position is averaged equally across actors inside each N/task;
- output is EV delta in ante/hand relative to true mixed CFR Hero.

No CFR state, RNG, snapshot, DLL, TXT or runtime bitset may be modified by this gate.

## Metrics

For each candidate:

- mean EV delta vs mixed across sampled task/population cells;
- worst opponent-family mean;
- worst N mean;
- fraction of cells with positive delta;
- fraction of cells with statistically significant positive/negative delta;
- mean and maximum candidate regret relative to the best candidate in each sampled environment;
- full breakdown by population family and N.

## Predeclared interpretation rule

This is a robustness screen, not a proof about the real population.

- If greedy has positive overall mean and no materially negative population/N aggregate (approximately worse than mixed by >0.01 ante/hand), retain greedy as preferred practical base.
- If a hybrid materially improves the worst-population or candidate-regret profile without sacrificing more than about 0.01 ante/hand of overall mean, prefer the hybrid for a second confirmation gate.
- If deterministic/purified policies show a material negative tail while mixed does not, retain mixed as the robustness reference.
- If differences are all economically tiny (roughly within ±0.01 ante/hand at aggregate level), retain SEL3500 greedy live because it is already operationally validated and simpler; do not create further tests solely to chase sub-cent noise.

No automatic release change is authorized by this script. A policy change requires explicit review of the output.

## Population exploitation decision

Do **not** open a full population-exploitation project before this base-policy gate is resolved.

A proper exploit layer would require a structured database with actions, public scenario, board, position, revealed showdown cards and censored-fold treatment. OpenHoldem logs alone are not sufficient to reconstruct population ranges. If a later database demonstrates stable, material population deviations, exploitation can be added conservatively on top of the frozen base with fallback to base.
