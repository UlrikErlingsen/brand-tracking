import numpy as np
import pandas as pd
import pytest

from tracksignal.design import TrackingContract, natural_sort_key, order_labels, validate_tracking_data
from tracksignal.errors import DataProblem
from tracksignal.examples import make_demo_data


CONTRACT = TrackingContract(
    respondent_column="respondent_id",
    wave_column="wave",
    segment_column="segment",
    brand_column="brand",
    metric_column="metric",
    value_column="value",
    kind_column="metric_kind",
    weight_column="weight",
    family_column="family",
    source_column="measurement_source",
    threshold_column="practical_threshold",
)


def test_demo_contract_creates_canonical_audit() -> None:
    frame = make_demo_data(respondents_per_wave=12)
    result = validate_tracking_data(frame, CONTRACT)

    assert result.summary["waves"] == 3
    assert result.summary["segments"] == 2
    assert result.summary["brands"] == 3
    assert result.summary["metrics"] == 12
    assert result.summary["construct_metrics"] == 1
    assert result.summary["weighted"] is True
    assert set(result.cleaned["metric_kind"]) == {"binary", "rating", "construct"}
    assert not result.metric_catalog.duplicated("metric").any()
    assert (result.cell_audit["effective_n"] > 0).all()
    assert any("universal brand-equity score" in warning for warning in result.warnings)


def test_binary_values_must_be_zero_or_one() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    index = frame.index[frame["metric_kind"].eq("binary")][0]
    frame.loc[index, "value"] = 0.5

    with pytest.raises(DataProblem, match="only 0 and 1"):
        validate_tracking_data(frame, CONTRACT)


def test_construct_requires_measurement_provenance() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    frame.loc[frame["metric_kind"].eq("construct"), "measurement_source"] = ""

    with pytest.raises(DataProblem, match="measurement-evidence reference"):
        validate_tracking_data(frame, CONTRACT)


def test_duplicate_respondent_metric_records_are_rejected() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)

    with pytest.raises(DataProblem, match="duplicate"):
        validate_tracking_data(frame, CONTRACT)


def test_metric_definition_must_remain_stable() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    awareness = frame.index[frame["metric"].eq("Awareness")]
    frame.loc[awareness[0], "practical_threshold"] = 0.04

    with pytest.raises(DataProblem, match="stable practical threshold"):
        validate_tracking_data(frame, CONTRACT)


def test_negative_thresholds_are_rejected() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    frame["practical_threshold"] = -0.05

    with pytest.raises(DataProblem, match="positive"):
        validate_tracking_data(frame, CONTRACT)


def test_unmapped_threshold_column_becomes_undeclared_with_warning() -> None:
    contract = TrackingContract(
        respondent_column="respondent_id",
        wave_column="wave",
        segment_column="segment",
        brand_column="brand",
        metric_column="metric",
        value_column="value",
        kind_column="metric_kind",
        weight_column="weight",
        family_column="family",
        source_column="measurement_source",
        threshold_column=None,
    )
    result = validate_tracking_data(make_demo_data(respondents_per_wave=4), contract)
    assert result.cleaned["practical_threshold"].isna().all()
    assert any("no declared positive practical-change threshold" in warning for warning in result.warnings)


def test_zero_thresholds_become_undeclared_not_free_significance() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    frame["practical_threshold"] = 0.0
    result = validate_tracking_data(frame, CONTRACT)
    assert result.cleaned["practical_threshold"].isna().all()
    assert np.isnan(result.metric_catalog["practical_threshold"]).all()
    assert any("no declared positive practical-change threshold" in warning for warning in result.warnings)


def test_contract_roles_cannot_reuse_one_column() -> None:
    frame = make_demo_data(respondents_per_wave=4)
    invalid = TrackingContract(
        respondent_column="respondent_id",
        wave_column="wave",
        brand_column="brand",
        metric_column="metric",
        value_column="value",
        kind_column="metric_kind",
        family_column="metric_kind",
    )
    with pytest.raises(DataProblem, match="different source column"):
        validate_tracking_data(frame, invalid)


def test_wave_labels_sort_naturally_so_wave_2_precedes_wave_10() -> None:
    labels = pd.Series(["Wave 10", "Wave 2", "Wave 1", "Wave 21", "Wave 3"])
    assert order_labels(labels) == ["Wave 1", "Wave 2", "Wave 3", "Wave 10", "Wave 21"]
    assert natural_sort_key("Wave 2") < natural_sort_key("Wave 10")
    # Mixed and non-numeric labels still order deterministically and case-insensitively.
    assert order_labels(pd.Series(["q4 2025", "Q1 2026", "Q3 2025"])) == ["Q1 2026", "Q3 2025", "q4 2025"]
