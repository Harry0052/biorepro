# Office-wellness oracle

Fixture id `office-wellness`. Generation seed `20261123`. DOI: none. These counts are original synthetic group totals for a methods example about workplace step programs. They are not observations of real people.

Estimand: pooled mean daily steps within an arm, `sum(steps_sum) / sum(n_people)`, in steps per person per day. The analysis does not use a random number generator. `rng_seed` is null.

## Hand calculation

| Arm | Groups | People | Step sum | Mean |
| --- | --- | --- | --- | --- |
| walk_challenge | g1 12 people, 78480 steps; g2 8 people, 52320 steps | 20 | 130800 | 130800 / 20 = 6540 exactly, printed `6540.00` |
| standing_break | g3 10 people, 60000 steps; g4 10 people, 62410 steps | 20 | 122410 | 122410 / 20 = 6120.5 exactly, printed `6120.50` |
| control | g5 15 people, 90000 steps; g6 5 people, 29765 steps | 20 | 119765 | 119765 / 20 = 5988.25 exactly, printed `5988.25` |

`12 * 6540 = 78480` and `8 * 6540 = 52320`. `6120.50 * 20 = 122410`. `5988.25 * 20 = 119765`.

The clean oracle lists those three means. Absolute tolerance on `mean_steps` is `0.01`. Relative tolerance is `0`.

## Perturbed oracle

`oracle/perturbed.csv` changes only `walk_challenge` `mean_steps` from `6540.00` to `6540.25`. The difference `0.25` is outside the absolute tolerance. Every other cell matches the clean oracle. The input file and the script are unchanged; the perturbation is in the comparison target.
