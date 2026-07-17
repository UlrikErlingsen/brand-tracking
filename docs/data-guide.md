# Data guide

## Unit of observation

Use one row per respondent × wave × segment × brand × metric. A respondent may evaluate several brands and metrics in a wave. The exact key must remain unique; TrackSignal will not silently average repeated records.

## Column roles

| Role | Required | Meaning |
|---|---:|---|
| Respondent ID | Yes | Stable identifier within the comparison scope. Use stable longitudinal IDs only when the same people genuinely return. |
| Wave | Yes | Survey wave, fieldwork period, or comparable tracking occasion. |
| Segment | No | Mutually meaningful analysis segment. Missing role becomes `All respondents`. |
| Brand | Yes | Evaluated brand or competitor. At least two are required. |
| Metric | Yes | Stable metric name. Wording and construction must not change silently between waves. |
| Metric kind | Yes | `binary`, `rating`, or `construct`. |
| Value | Yes | Numeric observation; binary values must be exactly 0 or 1. |
| Weight | No | Positive survey-analysis weight. Missing role becomes 1. |
| Family | No | Display grouping such as Funnel, Associations, or Relationship. |
| Measurement source | Conditional | Required for construct scores; recommended for every metric. |
| Practical threshold | No | Smallest change worth flagging on the metric’s own scale; must be positive. If undeclared (or zero), contrasts report statistical detection only and never a “CLEAR” change. |

## Metric design

Do not use one item label for changing questions. If aided awareness, unaided awareness, prompted familiarity, and category usage have different meanings or bases, give them different metric names and preserve the questionnaire source.

Binary funnel metrics should use a stable eligible base. For example, loyalty among users is not directly comparable with loyalty among all respondents. Either filter to the intended base before import or encode the base in the metric name and evidence notes.

## Construct scores

Item-level attachment, reputation, trust, or quality scales belong in MeasureSignal or another documented measurement workflow. TrackSignal expects the resulting score plus a measurement-evidence reference. It does not assess factor structure, reliability, validity, scoring invariance, or item drift.

## Weights and sample design

Weights must be finite and positive. The current release uses Kish effective sample size for approximate weighted intervals. It does not model strata, clusters, replicate weights, finite-population corrections, raking uncertainty, or weight-estimation uncertainty. Use specialist survey software when the design requires those features.

## Longitudinal IDs

Use the same respondent ID across waves only when it is the same person. TrackSignal never pairs on overlapping IDs by itself: paired analysis requires you to confirm explicitly (a checkbox in the app, `paired_ids=True` in the API) that IDs are stable and identify the same people. Recycled panel IDs, household IDs, serial IDs reissued each wave, or unstable device identifiers would otherwise create false pairing, so do not confirm pairing unless the panel design genuinely guarantees stable IDs. When pairing is used, unmatched respondents are dropped from the paired rows and the app reports how many.

## Questionnaire and fieldwork continuity

Record and investigate changes to wording, response scales, item order, mode, sampling frame, quotas, fieldwork dates, weighting, market coverage, and competitor set. A narrow confidence interval does not make incomparable waves comparable.

