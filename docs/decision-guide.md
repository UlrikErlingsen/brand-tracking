# Decision guide

## Read results in this order

1. **Contract:** Is the metric definition, eligible base, response scale, and measurement source stable?
2. **Coverage:** Are both groups represented with adequate effective sample size?
3. **Effect:** How large is `comparison − reference` on the original scale?
4. **Interval:** Which values remain compatible with sampling uncertainty?
5. **Multiplicity:** Does the result survive BH adjustment within the displayed family?
6. **Practical threshold:** Is the estimated change large enough to matter operationally?
7. **External evidence:** Did questionnaire, sample, weighting, market conditions, or brand activity change?

## Status language

- `CLEAR INCREASE` / `CLEAR DECREASE`: direction, multiplicity, and the declared positive practical threshold align under the selected approximation.
- `DETECTED — NO PRACTICAL THRESHOLD DECLARED`: the interval excludes zero and the q-value survives BH control, but no positive practical threshold was declared for this metric (unmapped, blank, or zero). The app can report statistical detection only; it cannot say whether the change is large enough to matter. Declare a threshold on the metric’s own scale to enable the `CLEAR` labels.
- `CLEAR BUT BELOW PRACTICAL THRESHOLD`: direction is statistically clear but the point estimate is smaller than the declared materiality threshold.
- `NOT ROBUST TO MULTIPLE-COMPARISON CONTROL`: the unadjusted interval excludes zero, but the displayed family does not support the same conclusion after BH adjustment.
- `UNCERTAIN / COMPATIBLE WITH NO CHANGE`: the interval includes zero.
- `INSUFFICIENT PRECISION`: the analysis lacks enough information for a usable interval or p-value.

## What to do next

Treat a clear movement as a prompt for investigation, not a ready-made story. Reconcile it with fieldwork, sample composition, questionnaire, competitor activity, distribution, price, product, media, service, and external events. Use ExperimentSignal or another credible identification design for causal claims.

If several relationship constructs move together, inspect MeasureSignal evidence before comparing scores across waves. TrackSignal can track a prespecified attribute-ownership item, but association structure and competitive positioning belong in PositionSignal rather than stretching this tracker into a perceptual-map tool.
