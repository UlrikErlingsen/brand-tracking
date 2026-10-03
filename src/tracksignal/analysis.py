"""Transparent estimates and contrasts for longitudinal brand tracking."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from .design import label_mask
from .errors import DataProblem


CANONICAL_DIMENSIONS = ("wave", "segment", "brand", "metric")


@dataclass(frozen=True)
class SummaryResult:
    estimates: pd.DataFrame
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ContrastResult:
    contrasts: pd.DataFrame
    warnings: tuple[str, ...]


def _weighted_stats(values: pd.Series, weights: pd.Series) -> dict[str, float | int]:
    x = pd.to_numeric(values, errors="coerce").to_numpy(float)
    w = pd.to_numeric(weights, errors="coerce").to_numpy(float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]
    n = len(x)
    if n == 0:
        return {"estimate": np.nan, "se": np.nan, "n": 0, "effective_n": 0.0, "variance": np.nan}
    estimate = float(np.average(x, weights=w))
    effective_n = float(w.sum() ** 2 / np.square(w).sum())
    denominator = float(w.sum() - np.square(w).sum() / w.sum())
    variance = float(np.sum(w * np.square(x - estimate)) / denominator) if denominator > 0 else np.nan
    se = math.sqrt(variance / effective_n) if effective_n > 1 and np.isfinite(variance) else np.nan
    return {"estimate": estimate, "se": se, "n": n, "effective_n": effective_n, "variance": variance}


def _wilson_interval(proportion: float, n: float, alpha: float) -> tuple[float, float]:
    if not np.isfinite(proportion) or n <= 0:
        return np.nan, np.nan
    z = float(stats.norm.ppf(1 - alpha / 2))
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    radius = z / denominator * math.sqrt(max(proportion * (1 - proportion) / n + z * z / (4 * n * n), 0))
    return max(0.0, center - radius), min(1.0, center + radius)


def _summary_frame(frame: pd.DataFrame, group_columns: list[str], alpha: float) -> pd.DataFrame:
    """Vectorized per-cell estimates; numerically the same statistics as ``_weighted_stats`` per group.

    Large trackers have thousands of cells and millions of rows, so the per-cell sums are accumulated with one
    pass over integer group codes instead of a Python loop over groups.
    """
    grouped = frame.groupby(group_columns, observed=True, sort=True)
    keys = grouped.size().index.to_frame(index=False)
    group_count = len(keys)
    group_ids = grouped.ngroup().to_numpy()
    keyed = ~pd.isna(group_ids)
    ids = group_ids[keyed].astype(np.int64)

    x = pd.to_numeric(frame["value"], errors="coerce").to_numpy(float)[keyed]
    w = pd.to_numeric(frame["weight"], errors="coerce").to_numpy(float)[keyed]
    valid = np.isfinite(x) & np.isfinite(w) & (w > 0)
    wv = np.where(valid, w, 0.0)
    xv = np.where(valid, x, 0.0)

    n = np.bincount(ids, weights=valid.astype(float), minlength=group_count)
    weight_sum = np.bincount(ids, weights=wv, minlength=group_count)
    weight_sq_sum = np.bincount(ids, weights=wv * wv, minlength=group_count)
    weighted_x = np.bincount(ids, weights=wv * xv, minlength=group_count)
    has_rows = n > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        estimate = np.where(has_rows, weighted_x / weight_sum, np.nan)
        squared_dev = np.bincount(ids, weights=wv * np.square(xv - np.nan_to_num(estimate)[ids]), minlength=group_count)
        effective_n = np.where(has_rows, np.square(weight_sum) / weight_sq_sum, 0.0)
        denominator = weight_sum - weight_sq_sum / weight_sum
        variance = np.where(has_rows & (denominator > 0), squared_dev / denominator, np.nan)
        se = np.where((effective_n > 1) & np.isfinite(variance), np.sqrt(variance / effective_n), np.nan)

    # np.allclose(weights, 1.0) per group: every |w - 1| <= 1e-8 + 1e-5; a nonfinite weight counts as weighted.
    all_weights = pd.to_numeric(frame["weight"], errors="coerce").to_numpy(float)[keyed]
    deviation = np.where(np.isfinite(all_weights), np.abs(all_weights - 1.0), np.inf)
    max_deviation = pd.Series(deviation).groupby(ids).max().reindex(range(group_count), fill_value=0.0).to_numpy()
    weighted = max_deviation > 1e-8 + 1e-5

    kinds = keys["metric_kind"].astype(str).to_numpy()
    binary = kinds == "binary"
    z = float(stats.norm.ppf(1 - alpha / 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        wilson_ok = np.isfinite(estimate) & (effective_n > 0)
        denom = 1 + z * z / effective_n
        center = (estimate + z * z / (2 * effective_n)) / denom
        radius = z / denom * np.sqrt(
            np.maximum(estimate * (1 - estimate) / effective_n + z * z / (4 * effective_n * effective_n), 0)
        )
        wilson_low = np.where(wilson_ok, np.maximum(0.0, center - radius), np.nan)
        wilson_high = np.where(wilson_ok, np.minimum(1.0, center + radius), np.nan)
        df = effective_n - 1
        critical = np.full(group_count, np.nan)
        positive_df = df > 0
        critical[positive_df] = stats.t.ppf(1 - alpha / 2, df[positive_df])
        t_low = estimate - critical * se
        t_high = estimate + critical * se
    ci_low = np.where(binary, wilson_low, t_low)
    ci_high = np.where(binary, wilson_high, t_high)
    method = np.where(
        binary,
        np.where(weighted, "Kish-adjusted Wilson score", "Wilson score"),
        np.where(weighted, "weighted t interval (Kish n)", "t interval"),
    )

    estimates = keys[group_columns].copy()
    for column in group_columns:
        estimates[column] = estimates[column].astype(object)
    estimates["estimate"] = estimate
    estimates["se"] = se
    estimates["n"] = n.astype(np.int64)
    estimates["effective_n"] = effective_n
    estimates["variance"] = variance
    estimates["ci_low"] = ci_low
    estimates["ci_high"] = ci_high
    estimates["interval_method"] = method.astype(object)
    estimates["confidence_level"] = 1 - alpha
    return estimates


def summarize_tracking(frame: pd.DataFrame, *, alpha: float = 0.05) -> SummaryResult:
    """Estimate each metric separately by wave, segment, and brand."""
    if not 0 < alpha < 1:
        raise DataProblem("Alpha must be between zero and one.")
    required = {"wave", "segment", "brand", "metric", "metric_kind", "value", "weight", "family"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataProblem("Validated tracking data are missing: " + ", ".join(missing))
    group_columns = ["wave", "segment", "brand", "family", "metric", "metric_kind"]
    estimates = _summary_frame(frame, group_columns, alpha)
    warnings = (
        "Intervals quantify sampling uncertainty under the declared sampling approximation; they do not cover measurement error, nonresponse bias, questionnaire changes, or causal identification.",
        "Binary estimates are proportions. Rating and construct estimates retain their original response scale.",
    )
    return SummaryResult(estimates=estimates, warnings=warnings)


def _benjamini_hochberg(p_values: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(p_values), dtype=float)
    adjusted = np.full(values.shape, np.nan)
    valid = np.isfinite(values)
    if not valid.any():
        return adjusted
    valid_values = values[valid]
    order = np.argsort(valid_values)
    ranked = valid_values[order]
    m = len(ranked)
    scaled = ranked * m / np.arange(1, m + 1)
    monotone = np.minimum.accumulate(scaled[::-1])[::-1]
    restored = np.empty(m)
    restored[order] = np.clip(monotone, 0, 1)
    adjusted[np.flatnonzero(valid)] = restored
    return adjusted


def _independent_contrast(left: pd.DataFrame, right: pd.DataFrame, kind: str, alpha: float) -> dict[str, object]:
    left_stats = _weighted_stats(left["value"], left["weight"])
    right_stats = _weighted_stats(right["value"], right["weight"])
    reference = float(left_stats["estimate"])
    comparison = float(right_stats["estimate"])
    difference = comparison - reference
    weighted = not (
        np.allclose(left["weight"].to_numpy(float), 1.0)
        and np.allclose(right["weight"].to_numpy(float), 1.0)
    )
    if kind == "binary" and not weighted:
        left_low, left_high = _wilson_interval(reference, float(left_stats["n"]), alpha)
        right_low, right_high = _wilson_interval(comparison, float(right_stats["n"]), alpha)
        low = difference - math.sqrt((comparison - right_low) ** 2 + (left_high - reference) ** 2)
        high = difference + math.sqrt((right_high - comparison) ** 2 + (reference - left_low) ** 2)
        left_n = float(left_stats["n"])
        right_n = float(right_stats["n"])
        # The z statistic uses the unpooled standard error so the p-value and the Newcombe-Wilson
        # interval come from the same unpooled comparison of two proportions.
        se_unpooled = math.sqrt(
            max(reference * (1 - reference) / left_n + comparison * (1 - comparison) / right_n, 0)
        )
        statistic = difference / se_unpooled if se_unpooled > 0 else np.nan
        p_value = float(2 * stats.norm.sf(abs(statistic))) if np.isfinite(statistic) else np.nan
        method = "independent Newcombe-Wilson interval + unpooled z test"
    else:
        left_variance = float(left_stats["se"]) ** 2
        right_variance = float(right_stats["se"]) ** 2
        difference_se = math.sqrt(left_variance + right_variance)
        df_denominator = (
            left_variance**2 / (float(left_stats["effective_n"]) - 1)
            + right_variance**2 / (float(right_stats["effective_n"]) - 1)
            if float(left_stats["effective_n"]) > 1 and float(right_stats["effective_n"]) > 1
            else np.nan
        )
        df = (left_variance + right_variance) ** 2 / df_denominator if df_denominator > 0 else np.nan
        critical = float(stats.t.ppf(1 - alpha / 2, df)) if np.isfinite(df) else np.nan
        low = difference - critical * difference_se if np.isfinite(critical) else np.nan
        high = difference + critical * difference_se if np.isfinite(critical) else np.nan
        statistic = difference / difference_se if difference_se > 0 else np.nan
        p_value = float(2 * stats.t.sf(abs(statistic), df)) if np.isfinite(statistic) and np.isfinite(df) else np.nan
        method = "independent weighted Welch difference" if weighted else "independent Welch difference"
    return {
        "reference_estimate": reference,
        "comparison_estimate": comparison,
        "difference": difference,
        "ci_low": max(-1.0, low) if kind == "binary" and np.isfinite(low) else low,
        "ci_high": min(1.0, high) if kind == "binary" and np.isfinite(high) else high,
        "p_value": p_value,
        "reference_n": int(left_stats["n"]),
        "comparison_n": int(right_stats["n"]),
        "paired_n": 0,
        "reference_dropped_n": 0,
        "comparison_dropped_n": 0,
        "method": method,
    }


def _paired_contrast(left: pd.DataFrame, right: pd.DataFrame, kind: str, alpha: float) -> dict[str, object] | None:
    left_pairs = left[["respondent_id", "value", "weight"]].rename(
        columns={"value": "value_reference", "weight": "weight_reference"}
    )
    right_pairs = right[["respondent_id", "value", "weight"]].rename(
        columns={"value": "value_comparison", "weight": "weight_comparison"}
    )
    pairs = left_pairs.merge(right_pairs, on="respondent_id", how="inner", validate="one_to_one")
    if len(pairs) < 2:
        return None
    if not np.allclose(
        pairs["weight_reference"].to_numpy(float),
        pairs["weight_comparison"].to_numpy(float),
        rtol=1e-7,
        atol=1e-10,
    ):
        return None
    pairs["difference"] = pairs["value_comparison"] - pairs["value_reference"]
    pairs["pair_weight"] = (pairs["weight_reference"] + pairs["weight_comparison"]) / 2
    weighted = not np.allclose(pairs["pair_weight"].to_numpy(float), 1.0)
    difference_stats = _weighted_stats(pairs["difference"], pairs["pair_weight"])
    reference_stats = _weighted_stats(pairs["value_reference"], pairs["pair_weight"])
    comparison_stats = _weighted_stats(pairs["value_comparison"], pairs["pair_weight"])
    df = float(difference_stats["effective_n"]) - 1
    critical = float(stats.t.ppf(1 - alpha / 2, df)) if df > 0 else np.nan
    difference = float(difference_stats["estimate"])
    difference_se = float(difference_stats["se"])
    low = difference - critical * difference_se if np.isfinite(critical) else np.nan
    high = difference + critical * difference_se if np.isfinite(critical) else np.nan
    statistic = difference / difference_se if difference_se > 0 else np.nan
    if kind == "binary" and not weighted:
        gained = int(((pairs["value_reference"] == 0) & (pairs["value_comparison"] == 1)).sum())
        lost = int(((pairs["value_reference"] == 1) & (pairs["value_comparison"] == 0)).sum())
        discordant = gained + lost
        p_value = (
            float(stats.binomtest(min(gained, lost), discordant, 0.5, alternative="two-sided").pvalue)
            if discordant
            else 1.0
        )
        method = "paired-difference t-style interval + exact McNemar p (hybrid, labelled)"
    else:
        p_value = float(2 * stats.t.sf(abs(statistic), df)) if np.isfinite(statistic) and df > 0 else np.nan
        method = "paired weighted difference" if weighted else "paired difference"
    return {
        "reference_estimate": float(reference_stats["estimate"]),
        "comparison_estimate": float(comparison_stats["estimate"]),
        "difference": difference,
        "ci_low": max(-1.0, low) if kind == "binary" and np.isfinite(low) else low,
        "ci_high": min(1.0, high) if kind == "binary" and np.isfinite(high) else high,
        "p_value": p_value,
        "reference_n": int(reference_stats["n"]),
        "comparison_n": int(comparison_stats["n"]),
        "paired_n": int(len(pairs)),
        "reference_dropped_n": int(len(left) - len(pairs)),
        "comparison_dropped_n": int(len(right) - len(pairs)),
        "method": method,
    }


def _cell_key(key: object) -> tuple[object, ...]:
    return tuple(key) if isinstance(key, tuple) else (key,)


def compare_groups(
    frame: pd.DataFrame,
    *,
    dimension: str,
    reference: str,
    comparison: str,
    by: tuple[str, ...] = ("metric",),
    alpha: float = 0.05,
    paired_ids: bool = False,
) -> ContrastResult:
    """Contrast two waves, brands, or segments.

    Paired analysis is used only when ``paired_ids=True`` — an explicit confirmation that
    respondent IDs identify the same people in both groups — AND the IDs actually overlap.
    Overlapping IDs alone are never treated as evidence of a panel design, because serial or
    recycled IDs would otherwise fabricate pairs and silently discard unmatched respondents.
    """
    if dimension not in {"wave", "segment", "brand"}:
        raise DataProblem("Contrast dimension must be wave, segment, or brand.")
    if reference == comparison:
        raise DataProblem("Reference and comparison values must differ.")
    if dimension in by or not by:
        raise DataProblem("Contrast grouping must be nonempty and cannot include the contrast dimension.")
    unsupported_by = sorted(set(by) - set(CANONICAL_DIMENSIONS))
    if unsupported_by:
        raise DataProblem("Unsupported contrast grouping: " + ", ".join(unsupported_by))
    required = {dimension, *by, "respondent_id", "metric_kind", "value", "weight", "practical_threshold"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataProblem("Validated tracking data are missing: " + ", ".join(missing))

    left_all = frame.loc[label_mask(frame[dimension], reference)]
    right_all = frame.loc[label_mask(frame[dimension], comparison)]
    if left_all.empty or right_all.empty:
        raise DataProblem("Both declared comparison groups need usable rows.")

    rows: list[dict[str, object]] = []
    pairing_withheld_for_weights = 0
    overlap_without_confirmation = 0
    combined_keys = pd.concat([left_all[list(by)], right_all[list(by)]], ignore_index=True).drop_duplicates()
    # Split each side once instead of filtering the whole group for every contrast cell (large trackers).
    left_cells = {_cell_key(key): cell for key, cell in left_all.groupby(list(by), observed=True, sort=False)}
    right_cells = {_cell_key(key): cell for key, cell in right_all.groupby(list(by), observed=True, sort=False)}
    for key_values in combined_keys.itertuples(index=False, name=None):
        keys = (key_values,) if len(by) == 1 and not isinstance(key_values, tuple) else tuple(key_values)
        left = left_cells.get(_cell_key(keys))
        right = right_cells.get(_cell_key(keys))
        if left is None or right is None or left.empty or right.empty:
            continue
        if left["metric_kind"].nunique() != 1 or right["metric_kind"].nunique() != 1:
            raise DataProblem("Each contrast cell must contain one metric kind.")
        kind = str(left["metric_kind"].iloc[0])
        if kind != str(right["metric_kind"].iloc[0]):
            raise DataProblem("Metric kind changed between comparison groups.")
        if left["respondent_id"].duplicated().any() or right["respondent_id"].duplicated().any():
            raise DataProblem(
                "A contrast cell contains more than one row per respondent. Filter or group by the remaining wave, "
                "segment, brand, and metric dimensions before comparison."
            )
        overlap_n = len(set(left["respondent_id"]) & set(right["respondent_id"]))
        paired = None
        if paired_ids and overlap_n >= 2:
            paired = _paired_contrast(left, right, kind, alpha)
            if paired is None:
                pairing_withheld_for_weights += 1
        elif not paired_ids and overlap_n >= 2:
            overlap_without_confirmation += 1
        result = paired if paired is not None else _independent_contrast(left, right, kind, alpha)
        row = dict(zip(by, keys, strict=True))
        threshold_values = pd.concat([left["practical_threshold"], right["practical_threshold"]]).dropna().unique()
        if len(threshold_values) > 1:
            raise DataProblem("Each contrasted metric needs one stable practical threshold.")
        row.update(result)
        row["metric_kind"] = kind
        row["practical_threshold"] = float(threshold_values[0]) if len(threshold_values) == 1 else float("nan")
        row["contrast"] = f"{comparison} − {reference}"
        rows.append(row)

    contrasts = pd.DataFrame(rows)
    if contrasts.empty:
        raise DataProblem("No matched analysis cells exist across the declared groups.")
    contrasts["q_value_bh"] = _benjamini_hochberg(contrasts["p_value"])

    def classify(row: pd.Series) -> str:
        low = float(row["ci_low"])
        high = float(row["ci_high"])
        difference = float(row["difference"])
        threshold = float(row["practical_threshold"])
        q_value = float(row["q_value_bh"])
        if not all(np.isfinite(value) for value in (low, high, difference, q_value)):
            return "INSUFFICIENT PRECISION"
        direction_clear = low > 0 or high < 0
        threshold_declared = np.isfinite(threshold) and threshold > 0
        if direction_clear and q_value <= alpha:
            if not threshold_declared:
                # Without a declared positive threshold a "CLEAR" label would just restate the
                # significance test as if it were business relevance. Report detection only.
                return "DETECTED — NO PRACTICAL THRESHOLD DECLARED"
            if abs(difference) >= threshold:
                return "CLEAR INCREASE" if difference > 0 else "CLEAR DECREASE"
            return "CLEAR BUT BELOW PRACTICAL THRESHOLD"
        if direction_clear and q_value > alpha:
            return "NOT ROBUST TO MULTIPLE-COMPARISON CONTROL"
        return "UNCERTAIN / COMPATIBLE WITH NO CHANGE"

    contrasts["evidence_status"] = contrasts.apply(classify, axis=1)
    contrasts.insert(0, "dimension", dimension)
    contrasts.insert(1, "reference", reference)
    contrasts.insert(2, "comparison", comparison)
    paired_mask = contrasts["paired_n"].gt(0)
    paired_rows = int(paired_mask.sum())
    warnings: list[str] = [
        "Benjamini-Hochberg q-values control the false-discovery rate within this displayed contrast family; they do not rescue an unplanned or biased design.",
        "A confidence interval describes sampling uncertainty under the selected model, not questionnaire drift, nonresponse, coverage error, or causality.",
    ]
    undeclared_threshold_rows = int(
        (~(np.isfinite(contrasts["practical_threshold"].to_numpy(float)) & contrasts["practical_threshold"].gt(0))).sum()
    )
    if undeclared_threshold_rows:
        warnings.append(
            f"{undeclared_threshold_rows} contrast rows have no declared positive practical threshold. Without a "
            "threshold Track Signal can only report statistical detection (“DETECTED — NO PRACTICAL THRESHOLD "
            "DECLARED”); it cannot judge whether a detected change is large enough to matter."
        )
    if paired_rows:
        pairs_used = int(contrasts.loc[paired_mask, "paired_n"].sum())
        reference_dropped = int(contrasts.loc[paired_mask, "reference_dropped_n"].sum())
        comparison_dropped = int(contrasts.loc[paired_mask, "comparison_dropped_n"].sum())
        warnings.append(
            f"{paired_rows} contrast rows used confirmed respondent pairing: {pairs_used} pairs analyzed in total; "
            f"{reference_dropped} reference and {comparison_dropped} comparison respondents without a matched partner "
            "were excluded from those rows. Binary paired intervals use a transparent paired-difference approximation "
            "and unweighted binary p-values use the exact McNemar test."
        )
    if overlap_without_confirmation:
        warnings.append(
            f"{overlap_without_confirmation} contrast rows had overlapping respondent IDs, but pairing was not "
            "confirmed as a stable panel/respondent design, so independent methods were used and the overlap was "
            "ignored. Confirm stable IDs to enable paired analysis."
        )
    if pairing_withheld_for_weights:
        warnings.append(
            f"{pairing_withheld_for_weights} contrast rows had overlapping respondent IDs but different group weights; "
            "the app used an independent weighted approximation instead of inventing a paired weighting rule."
        )
    if (contrasts["method"].str.contains("weighted")).any():
        warnings.append("Weighted contrast intervals use Kish effective sample sizes and do not represent a full complex-survey variance estimator.")
    return ContrastResult(contrasts=contrasts, warnings=tuple(warnings))
