# Methods

## Separate metrics, not a universal score

TrackSignal treats each declared measure as its own estimand. This prevents an analyst-chosen weighting scheme from disguising movement in awareness, consideration, loyalty, associations, trust, quality, attachment, or reputation. Any multi-item construct must arrive as a documented externally validated score.

## Cell estimates

For a binary observation `x ∈ {0,1}`, the estimate is the sample proportion. Unweighted 95% intervals use the Wilson score method. When weights are supplied, the weighted proportion is combined with Kish effective sample size,

`n_eff = (Σw)² / Σw²`,

and a Wilson-style interval. This is an approximation, not a design-based complex-survey interval.

For rating and construct observations, the estimate is the weighted or unweighted mean. The variance uses the finite-sample weighted denominator and the standard error uses `n_eff`; the interval uses a t critical value with approximately `n_eff − 1` degrees of freedom.

## Contrasts

TrackSignal computes `comparison − reference` on the original metric scale.

- Independent, unweighted binary contrasts use a Newcombe interval assembled from the two Wilson score intervals, with a z test based on the unpooled standard error of the same two proportions, so the interval and the p-value describe the same unpooled comparison.
- Independent rating/construct contrasts use a Welch–Satterthwaite interval, with the p-value from the same Welch t statistic.
- Weighted independent contrasts use the weighted Welch approximation for both the interval and the p-value.
- Paired analysis is used only when the analyst explicitly confirms that respondent IDs identify the same people in both groups (`paired_ids=True`; in the app, a checkbox that is off by default) **and** at least two IDs overlap in the analysis cell. Overlapping IDs alone never trigger pairing: serial or recycled IDs (for example `1..N` reissued each wave) would otherwise fabricate pairs and silently discard every unmatched respondent.

For paired contrasts, only respondents observed in both groups contribute. The displayed reference and comparison estimates therefore describe the paired subset, not every respondent in each group; each paired row reports the number of pairs used and the number of respondents dropped from the reference and comparison groups, both on screen and in the export. If the same respondent receives different weights in the two compared groups, TrackSignal withholds pairing and uses the independent weighted approximation instead of inventing a paired weighting rule.

For unweighted paired binary data, the p-value comes from the exact McNemar test on discordant pairs while the interval uses the transparent paired-mean-difference approximation. These are two different but individually standard components; the hybrid is deliberate and is labelled explicitly in the method column (`paired-difference t-style interval + exact McNemar p (hybrid, labelled)`) rather than presented as one unified procedure. For paired rating/construct data both the interval and the p-value come from the same paired t computation.

## Multiple comparisons

The app applies the Benjamini–Hochberg procedure to p-values within the complete displayed contrast family. The resulting q-values target false-discovery-rate control under the method’s assumptions. They do not turn exploratory comparisons into preregistered confirmatory evidence.

## Evidence status

A row receives `CLEAR INCREASE` or `CLEAR DECREASE` only when:

1. its interval excludes zero;
2. its BH q-value is at most `.05`; and
3. its absolute difference reaches the declared **positive** practical threshold.

When no practical threshold is declared for a metric — the threshold role is unmapped, the cell is blank, or the declared value is zero — condition 3 cannot be evaluated. In that case a statistically detected change is labelled `DETECTED — NO PRACTICAL THRESHOLD DECLARED`, never `CLEAR INCREASE` or `CLEAR DECREASE`. A zero threshold would make “practically large” identical to “statistically detectable” and would quietly re-badge a bare significance test as business relevance, so TrackSignal refuses to treat zero as a threshold and warns visibly instead.

A statistically clear change smaller than a declared threshold is labelled `CLEAR BUT BELOW PRACTICAL THRESHOLD`. A result that loses support after multiplicity control is also labelled separately. Status labels summarize the displayed inputs; analysts should report estimates and intervals directly.

## What intervals omit

The intervals cover sampling uncertainty under the declared approximation. They do not cover nonresponse bias, undercoverage, questionnaire drift, interviewer or mode effects, respondent conditioning, bad weights, measurement error, construct noninvariance, seasonality, competitor changes, or causal attribution.

## Interpretation

Brand, segment, and wave differences are descriptive unless the sampling and identification design supports a stronger claim. A movement cannot by itself show that advertising, product changes, publicity, pricing, or any other intervention caused it.
