"""Tracking-data contracts, validation, and audit tables."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

from .errors import DataProblem


METRIC_KINDS = ("binary", "rating", "construct")

_DIGIT_RUN = re.compile(r"(\d+)")


def natural_sort_key(label: object) -> tuple[tuple[int, object], ...]:
    """Numeric-aware sort key so that 'Wave 2' orders before 'Wave 10'."""
    parts = _DIGIT_RUN.split(str(label))
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in parts if part != "")


def order_labels(series: pd.Series) -> list[str]:
    """Order label values naturally: digit runs compare as numbers, text case-insensitively."""
    return sorted(series.dropna().astype(str).unique().tolist(), key=natural_sort_key)


@dataclass(frozen=True)
class TrackingContract:
    respondent_column: str
    wave_column: str
    brand_column: str
    metric_column: str
    value_column: str
    kind_column: str
    segment_column: str | None = None
    weight_column: str | None = None
    family_column: str | None = None
    source_column: str | None = None
    threshold_column: str | None = None


@dataclass(frozen=True)
class TrackingAudit:
    cleaned: pd.DataFrame
    summary: dict[str, object]
    metric_catalog: pd.DataFrame
    cell_audit: pd.DataFrame
    warnings: tuple[str, ...]


def _clean_label(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _selected_columns(contract: TrackingContract) -> dict[str, str]:
    required = {
        "respondent_id": contract.respondent_column,
        "wave": contract.wave_column,
        "brand": contract.brand_column,
        "metric": contract.metric_column,
        "value": contract.value_column,
        "metric_kind": contract.kind_column,
    }
    optional = {
        "segment": contract.segment_column,
        "weight": contract.weight_column,
        "family": contract.family_column,
        "measurement_source": contract.source_column,
        "practical_threshold": contract.threshold_column,
    }
    required.update({key: value for key, value in optional.items() if value})
    return required


def validate_tracking_data(frame: pd.DataFrame, contract: TrackingContract) -> TrackingAudit:
    """Normalize a long brand-tracking file and enforce its declared measurement contract."""
    if frame.empty:
        raise DataProblem("The tracking dataset has no rows.")
    mapping = _selected_columns(contract)
    source_columns = list(mapping.values())
    if len(source_columns) != len(set(source_columns)):
        raise DataProblem("Each contract role must use a different source column.")
    missing = [column for column in source_columns if column not in frame.columns]
    if missing:
        raise DataProblem("These selected columns are missing: " + ", ".join(missing))

    clean = frame[source_columns].rename(columns={value: key for key, value in mapping.items()}).copy()
    if "segment" not in clean:
        clean["segment"] = "All respondents"
    if "weight" not in clean:
        clean["weight"] = 1.0
    if "family" not in clean:
        clean["family"] = "Unassigned"
    if "measurement_source" not in clean:
        clean["measurement_source"] = ""
    if "practical_threshold" not in clean:
        # No threshold declared. Keep the column, but mark it as undeclared (NaN) instead of
        # injecting 0, which would silently turn every significance test into "practically large".
        clean["practical_threshold"] = np.nan

    label_columns = ["respondent_id", "wave", "segment", "brand", "metric", "metric_kind", "family"]
    for column in label_columns:
        clean[column] = _clean_label(clean[column])
    clean["measurement_source"] = clean["measurement_source"].fillna("").astype(str).str.strip()
    clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
    clean["weight"] = pd.to_numeric(clean["weight"], errors="coerce")
    clean["practical_threshold"] = pd.to_numeric(clean["practical_threshold"], errors="coerce")

    identity_columns = ["respondent_id", "wave", "segment", "brand", "metric", "metric_kind", "family"]
    missing_identity = clean[identity_columns].isna() | clean[identity_columns].eq("")
    missing_identity_rows = int(missing_identity.any(axis=1).sum())
    if missing_identity_rows:
        raise DataProblem(
            f"{missing_identity_rows} rows have a missing respondent, wave, segment, brand, metric, kind, or family label."
        )
    if clean["value"].isna().any():
        raise DataProblem(f"{int(clean['value'].isna().sum())} rows have a missing or nonnumeric value.")
    if clean["weight"].isna().any() or (clean["weight"] <= 0).any():
        raise DataProblem("Survey weights must be finite and strictly positive.")
    if not np.isfinite(clean[["value", "weight"]].to_numpy(float)).all():
        raise DataProblem("Values and weights must be finite.")
    if (clean["practical_threshold"] < 0).any():
        raise DataProblem("Practical-change thresholds must be positive numbers on the metric's own scale.")
    zero_thresholds = clean["practical_threshold"].eq(0)
    if zero_thresholds.any():
        # A threshold of exactly 0 would make "practically large" identical to "statistically
        # detectable". Treat it as undeclared and say so, rather than laundering significance
        # into business relevance.
        clean.loc[zero_thresholds, "practical_threshold"] = np.nan
    if contract.threshold_column and clean["practical_threshold"].isna().all() and not zero_thresholds.any():
        raise DataProblem(
            f"The mapped practical-threshold column '{contract.threshold_column}' contains no numeric values."
        )

    kinds = clean["metric_kind"].str.lower()
    unsupported = sorted(set(kinds) - set(METRIC_KINDS))
    if unsupported:
        raise DataProblem("Metric kind must be binary, rating, or construct; unsupported: " + ", ".join(unsupported))
    clean["metric_kind"] = kinds
    inconsistent_kind = clean.groupby("metric", observed=True)["metric_kind"].nunique()
    if (inconsistent_kind > 1).any():
        metrics = inconsistent_kind.index[inconsistent_kind > 1].astype(str).tolist()
        raise DataProblem("Each metric needs one stable kind; inconsistent metrics: " + ", ".join(metrics))
    inconsistent_family = clean.groupby("metric", observed=True)["family"].nunique()
    if (inconsistent_family > 1).any():
        metrics = inconsistent_family.index[inconsistent_family > 1].astype(str).tolist()
        raise DataProblem("Each metric needs one stable family; inconsistent metrics: " + ", ".join(metrics))

    binary = clean["metric_kind"].eq("binary")
    invalid_binary = binary & ~clean["value"].isin([0.0, 1.0])
    if invalid_binary.any():
        bad_metrics = sorted(clean.loc[invalid_binary, "metric"].unique().tolist())
        raise DataProblem("Binary metrics must contain only 0 and 1: " + ", ".join(bad_metrics))

    construct_metrics = sorted(clean.loc[clean["metric_kind"].eq("construct"), "metric"].unique().tolist())
    missing_construct_sources = [
        metric
        for metric in construct_metrics
        if not clean.loc[clean["metric"].eq(metric), "measurement_source"].str.strip().ne("").all()
    ]
    if missing_construct_sources:
        raise DataProblem(
            "Construct scores require a measurement-evidence reference from MeasureSignal or another documented "
            "validation workflow: " + ", ".join(missing_construct_sources)
        )

    duplicate_key = ["respondent_id", "wave", "segment", "brand", "metric"]
    duplicates = clean.duplicated(duplicate_key, keep=False)
    if duplicates.any():
        raise DataProblem(
            f"{int(duplicates.sum())} rows duplicate the respondent-wave-segment-brand-metric key. "
            "Resolve repeated records rather than averaging them silently."
        )

    if clean["brand"].nunique() < 2:
        raise DataProblem("TrackSignal needs at least two brands for a comparative tracker.")
    if clean["wave"].nunique() < 1 or clean["metric"].nunique() < 1:
        raise DataProblem("The contract needs at least one wave and one metric.")

    threshold_counts = clean.groupby("metric", observed=True)["practical_threshold"].nunique(dropna=False)
    if (threshold_counts > 1).any():
        metrics = threshold_counts.index[threshold_counts > 1].astype(str).tolist()
        raise DataProblem(
            "Each metric needs one stable practical threshold (declared everywhere or nowhere): " + ", ".join(metrics)
        )
    source_counts = clean.groupby("metric", observed=True)["measurement_source"].nunique()
    if (source_counts > 1).any():
        metrics = source_counts.index[source_counts > 1].astype(str).tolist()
        raise DataProblem("Each metric needs one stable measurement-source note: " + ", ".join(metrics))

    metric_catalog = (
        clean[["metric", "family", "metric_kind", "practical_threshold", "measurement_source"]]
        .drop_duplicates()
        .sort_values(["family", "metric"], key=lambda values: values.astype(str).str.casefold())
        .reset_index(drop=True)
    )
    cell_keys = ["wave", "segment", "brand", "metric", "metric_kind"]
    cell_audit = (
        clean.groupby(cell_keys, observed=True)
        .agg(source_rows=("value", "size"), respondent_n=("respondent_id", "nunique"), weight_sum=("weight", "sum"))
        .reset_index()
    )
    effective_sizes = (
        clean.assign(weight_squared=np.square(clean["weight"]))
        .groupby(cell_keys, observed=True)
        .agg(weight_sum=("weight", "sum"), weight_squared_sum=("weight_squared", "sum"))
        .eval("weight_sum ** 2 / weight_squared_sum")
        .rename("effective_n")
        .reset_index()
    )
    cell_audit = cell_audit.merge(effective_sizes, on=cell_keys, how="left", validate="one_to_one")

    warnings: list[str] = []
    if not np.allclose(clean["weight"].to_numpy(float), 1.0):
        warnings.append(
            "Weighted intervals use a Kish effective-sample-size approximation; clustering, strata, calibration, and "
            "replicate weights are not modeled."
        )
    small_cells = int((cell_audit["effective_n"] < 30).sum())
    if small_cells:
        warnings.append(f"{small_cells} tracking cells have effective n below 30; their estimates may be unstable.")
    if clean["wave"].nunique() == 1:
        warnings.append("Only one wave is present, so change-over-time analysis is unavailable.")
    undeclared_threshold_metrics = int(
        clean.groupby("metric", observed=True)["practical_threshold"].apply(lambda values: values.isna().all()).sum()
    )
    if undeclared_threshold_metrics:
        warnings.append(
            f"{undeclared_threshold_metrics} of {int(clean['metric'].nunique())} metrics have no declared positive "
            "practical-change threshold. Without a threshold the app can only report statistical detection "
            "(“DETECTED — NO PRACTICAL THRESHOLD DECLARED”); it cannot label a change as practically clear."
        )
    warnings.append(
        "TrackSignal reports metrics separately. It does not calculate a universal brand-equity score or infer causality."
    )

    summary = {
        "source_rows": int(len(clean)),
        "respondents": int(clean["respondent_id"].nunique()),
        "waves": int(clean["wave"].nunique()),
        "segments": int(clean["segment"].nunique()),
        "brands": int(clean["brand"].nunique()),
        "metrics": int(clean["metric"].nunique()),
        "construct_metrics": len(construct_metrics),
        "weighted": bool(not np.allclose(clean["weight"].to_numpy(float), 1.0)),
    }
    return TrackingAudit(
        cleaned=clean.reset_index(drop=True),
        summary=summary,
        metric_catalog=metric_catalog,
        cell_audit=cell_audit,
        warnings=tuple(warnings),
    )
