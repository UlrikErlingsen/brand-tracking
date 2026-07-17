import numpy as np
import pandas as pd
import pytest

from tracksignal.analysis import compare_groups, summarize_tracking
from tracksignal.design import TrackingContract, validate_tracking_data
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


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    return validate_tracking_data(frame, CONTRACT).cleaned


def test_summary_keeps_binary_and_rating_metrics_separate() -> None:
    cleaned = _clean(make_demo_data(respondents_per_wave=25))
    result = summarize_tracking(cleaned)

    binary = result.estimates.loc[result.estimates["metric_kind"].eq("binary")]
    ratings = result.estimates.loc[result.estimates["metric_kind"].isin(["rating", "construct"])]
    assert binary["estimate"].between(0, 1).all()
    assert binary["ci_low"].between(0, 1).all()
    assert binary["ci_high"].between(0, 1).all()
    assert ratings["estimate"].between(1, 7).all()
    assert set(binary["interval_method"]) == {"Kish-adjusted Wilson score"}
    assert set(ratings["interval_method"]) == {"weighted t interval (Kish n)"}


def _simple_binary_waves(*, with_threshold: bool = True) -> pd.DataFrame:
    rows = []
    for wave, successes in (("Before", 20), ("After", 50)):
        for respondent in range(80):
            row = {
                "respondent_id": f"{wave}-{respondent}",
                "wave": wave,
                "segment": "All",
                "brand": "A",
                "metric": "Awareness",
                "metric_kind": "binary",
                "family": "Funnel",
                "value": int(respondent < successes),
                "weight": 1.0,
                "measurement_source": "Owned item",
            }
            if with_threshold:
                row["practical_threshold"] = 0.05
            rows.append(row)
    # The product contract requires a comparative brand set, even though this test scopes to A.
    duplicate = pd.DataFrame(rows).assign(brand="B", respondent_id=lambda data: data["respondent_id"] + "-B")
    return pd.concat([pd.DataFrame(rows), duplicate], ignore_index=True)


def test_independent_binary_wave_contrast_uses_newcombe_and_finds_large_change() -> None:
    cleaned = _clean(_simple_binary_waves())
    scoped = cleaned.loc[cleaned["brand"].eq("A")]
    result = compare_groups(
        scoped,
        dimension="wave",
        reference="Before",
        comparison="After",
        by=("brand", "metric"),
    )
    row = result.contrasts.iloc[0]
    assert row["difference"] == pytest.approx(0.375)
    assert row["ci_low"] > 0
    assert row["q_value_bh"] < 0.05
    assert row["evidence_status"] == "CLEAR INCREASE"
    assert row["method"] == "independent Newcombe-Wilson interval + unpooled z test"
    assert row["paired_n"] == 0


def test_independent_binary_p_value_uses_unpooled_z_matching_the_interval_family() -> None:
    cleaned = _clean(_simple_binary_waves())
    scoped = cleaned.loc[cleaned["brand"].eq("A")]
    result = compare_groups(
        scoped,
        dimension="wave",
        reference="Before",
        comparison="After",
        by=("brand", "metric"),
    )
    row = result.contrasts.iloc[0]
    p1, p2, n = 20 / 80, 50 / 80, 80.0
    se_unpooled = np.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    from scipy import stats

    expected_p = 2 * stats.norm.sf(abs((p2 - p1) / se_unpooled))
    assert row["p_value"] == pytest.approx(expected_p, rel=1e-9)


def _paired_rating_rows() -> pd.DataFrame:
    rows = []
    for respondent in range(50):
        for brand in ("A", "B"):
            rows.append(
                {
                    "respondent_id": f"R{respondent}",
                    "wave": "W1",
                    "segment": "All",
                    "brand": brand,
                    "metric": "Quality",
                    "metric_kind": "rating",
                    "family": "Relationship",
                    "value": 3.0 + respondent / 100 + (0.6 if brand == "B" else 0),
                    "weight": 1.0,
                    "practical_threshold": 0.2,
                    "measurement_source": "Owned item",
                }
            )
    return pd.DataFrame(rows)


def test_brand_contrast_uses_pairing_only_when_confirmed() -> None:
    cleaned = _clean(_paired_rating_rows())
    result = compare_groups(
        cleaned,
        dimension="brand",
        reference="A",
        comparison="B",
        by=("metric",),
        paired_ids=True,
    )
    row = result.contrasts.iloc[0]
    assert row["paired_n"] == 50
    assert row["reference_dropped_n"] == 0
    assert row["comparison_dropped_n"] == 0
    assert row["difference"] == pytest.approx(0.6)
    assert row["method"] == "paired difference"
    assert row["evidence_status"] == "CLEAR INCREASE"
    assert any("confirmed respondent pairing" in warning for warning in result.warnings)


def test_overlapping_ids_without_confirmation_never_pair_and_warn() -> None:
    cleaned = _clean(_paired_rating_rows())
    result = compare_groups(
        cleaned,
        dimension="brand",
        reference="A",
        comparison="B",
        by=("metric",),
    )
    row = result.contrasts.iloc[0]
    assert row["paired_n"] == 0
    assert row["method"] == "independent Welch difference"
    assert any("pairing was not confirmed" in warning for warning in result.warnings)
    assert not any("confirmed respondent pairing" in warning for warning in result.warnings)


def test_confirmed_pairing_reports_pairs_used_and_respondents_dropped() -> None:
    rows = []
    reference_ids = [f"P{index}" for index in range(40)]  # 30 shared + 10 only in Before
    comparison_ids = [f"P{index}" for index in range(30)] + [f"N{index}" for index in range(5)]
    for wave, ids in (("Before", reference_ids), ("After", comparison_ids)):
        for respondent_id in ids:
            for brand in ("A", "B"):
                rows.append(
                    {
                        "respondent_id": respondent_id,
                        "wave": wave,
                        "segment": "All",
                        "brand": brand,
                        "metric": "Trust",
                        "metric_kind": "rating",
                        "family": "Relationship",
                        "value": 4.0 + (0.4 if wave == "After" else 0.0) + int(respondent_id[1:]) / 100,
                        "weight": 1.0,
                        "practical_threshold": 0.2,
                        "measurement_source": "Owned item",
                    }
                )
    cleaned = _clean(pd.DataFrame(rows))
    result = compare_groups(
        cleaned,
        dimension="wave",
        reference="Before",
        comparison="After",
        by=("brand", "metric"),
        paired_ids=True,
    )
    for _, row in result.contrasts.iterrows():
        assert row["paired_n"] == 30
        assert row["reference_dropped_n"] == 10
        assert row["comparison_dropped_n"] == 5
    pairing_warning = next(warning for warning in result.warnings if "confirmed respondent pairing" in warning)
    assert "60 pairs" in pairing_warning
    assert "20 reference" in pairing_warning
    assert "10 comparison" in pairing_warning


def test_exact_mcnemar_p_value_is_used_for_unweighted_paired_binary_data() -> None:
    rows = []
    for respondent in range(40):
        for brand in ("A", "B"):
            value = int(respondent < (10 if brand == "A" else 30))
            rows.append(
                {
                    "respondent_id": f"R{respondent}",
                    "wave": "W1",
                    "segment": "All",
                    "brand": brand,
                    "metric": "Consideration",
                    "metric_kind": "binary",
                    "family": "Funnel",
                    "value": value,
                    "weight": 1.0,
                    "practical_threshold": 0.05,
                    "measurement_source": "Owned item",
                }
            )
    result = compare_groups(
        _clean(pd.DataFrame(rows)),
        dimension="brand",
        reference="A",
        comparison="B",
        by=("metric",),
        paired_ids=True,
    )
    row = result.contrasts.iloc[0]
    assert row["method"] == "paired-difference t-style interval + exact McNemar p (hybrid, labelled)"
    assert row["p_value"] < 0.001
    assert row["difference"] == pytest.approx(0.5)


def test_pairing_is_withheld_when_group_weights_differ() -> None:
    rows = []
    for respondent in range(30):
        for brand in ("A", "B"):
            rows.append(
                {
                    "respondent_id": f"R{respondent}",
                    "wave": "W1",
                    "segment": "All",
                    "brand": brand,
                    "metric": "Trust",
                    "metric_kind": "rating",
                    "family": "Relationship",
                    "value": 3 + respondent / 30 + (0.3 if brand == "B" else 0),
                    "weight": 1.0 if brand == "A" else 1.2,
                    "practical_threshold": 0.2,
                    "measurement_source": "Owned item",
                }
            )
    result = compare_groups(
        _clean(pd.DataFrame(rows)),
        dimension="brand",
        reference="A",
        comparison="B",
        by=("metric",),
        paired_ids=True,
    )
    row = result.contrasts.iloc[0]
    assert row["paired_n"] == 0
    assert row["method"] == "independent weighted Welch difference"
    assert any("different group weights" in warning for warning in result.warnings)


def test_missing_practical_threshold_never_produces_clear_labels() -> None:
    contract_without_threshold = TrackingContract(
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
    frame = _simple_binary_waves(with_threshold=False)
    audit = validate_tracking_data(frame, contract_without_threshold)
    assert any("no declared positive practical-change threshold" in warning for warning in audit.warnings)
    scoped = audit.cleaned.loc[audit.cleaned["brand"].eq("A")]
    result = compare_groups(
        scoped,
        dimension="wave",
        reference="Before",
        comparison="After",
        by=("brand", "metric"),
    )
    row = result.contrasts.iloc[0]
    # This change is unmistakably detected, yet must never be promoted to a "CLEAR" label.
    assert row["ci_low"] > 0
    assert row["q_value_bh"] < 0.05
    assert row["evidence_status"] == "DETECTED — NO PRACTICAL THRESHOLD DECLARED"
    assert not result.contrasts["evidence_status"].str.startswith("CLEAR").any()
    assert np.isnan(row["practical_threshold"])
    assert any("no declared positive practical threshold" in warning for warning in result.warnings)


def test_explicit_zero_threshold_is_treated_as_undeclared() -> None:
    frame = _simple_binary_waves()
    frame["practical_threshold"] = 0.0
    audit = validate_tracking_data(frame, CONTRACT)
    assert audit.cleaned["practical_threshold"].isna().all()
    scoped = audit.cleaned.loc[audit.cleaned["brand"].eq("A")]
    result = compare_groups(
        scoped,
        dimension="wave",
        reference="Before",
        comparison="After",
        by=("brand", "metric"),
    )
    assert result.contrasts["evidence_status"].iloc[0] == "DETECTED — NO PRACTICAL THRESHOLD DECLARED"
    assert not result.contrasts["evidence_status"].str.startswith("CLEAR").any()


def test_bh_values_are_monotone_and_bounded() -> None:
    cleaned = _clean(make_demo_data(respondents_per_wave=40))
    scoped = cleaned.loc[cleaned["segment"].eq("Core category buyers")]
    result = compare_groups(
        scoped,
        dimension="wave",
        reference="2025 Q3",
        comparison="2026 Q1",
        by=("brand", "metric"),
    )
    assert result.contrasts["q_value_bh"].dropna().between(0, 1).all()
    ordered = result.contrasts.dropna(subset=["p_value", "q_value_bh"]).sort_values("p_value")
    assert np.all(np.diff(ordered["q_value_bh"]) >= -1e-12)
