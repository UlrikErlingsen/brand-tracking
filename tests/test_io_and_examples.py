from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tracksignal import limits
from tracksignal.analysis import summarize_tracking
from tracksignal.design import TrackingContract, validate_tracking_data
from tracksignal.errors import DataProblem, friendly_message
from tracksignal.examples import make_demo_data, make_starter_template
from tracksignal.io import build_evidence_workbook, dataframe_csv_bytes, read_table


ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"


def test_examples_are_deterministic_and_committed_files_are_current() -> None:
    expected = make_demo_data()
    pd.testing.assert_frame_equal(expected, make_demo_data())
    pd.testing.assert_frame_equal(
        pd.read_csv(EXAMPLES / "tracksignal-fictional-tracker.csv"),
        expected,
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(EXAMPLES / "tracksignal-starter-template.csv"),
        make_starter_template(),
        check_dtype=False,
    )


def test_csv_and_xlsx_readers_round_trip() -> None:
    frame = make_starter_template()
    csv_loaded = read_table("tracker.csv", frame.to_csv(index=False).encode())
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    xlsx_loaded = read_table("tracker.xlsx", output.getvalue())
    # CSV text columns arrive as categories (compact for large trackers); the values are unchanged.
    assert all(isinstance(dtype, pd.CategoricalDtype) for dtype in csv_loaded.select_dtypes(exclude="number").dtypes)
    csv_loaded = csv_loaded.astype({column: object for column in csv_loaded.select_dtypes("category").columns})
    pd.testing.assert_frame_equal(csv_loaded, frame, check_dtype=False)
    pd.testing.assert_frame_equal(xlsx_loaded, frame, check_dtype=False)


def test_evidence_workbook_contains_auditable_sheets() -> None:
    simple = pd.DataFrame({"a": [1], "b": [2]})
    payload = build_evidence_workbook(
        metadata={"app": "TrackSignal", "boundary": "no universal score"},
        metric_catalog=simple,
        cell_audit=simple,
        estimates=simple,
        contrasts=simple,
    )
    workbook = pd.ExcelFile(BytesIO(payload))
    assert workbook.sheet_names == ["read_me", "metric_catalog", "cell_audit", "estimates", "contrasts"]
    metadata = pd.read_excel(BytesIO(payload), sheet_name="read_me")
    assert set(metadata["field"]) == {"app", "boundary"}


class _OversizedPayload(bytes):
    """Reports a length just over the demo upload cap without allocating it in the test."""

    def __len__(self) -> int:
        return limits.DEMO_MAX_UPLOAD_MB * 1024 * 1024 + 1


def _wide_csv(columns: int) -> bytes:
    return pd.DataFrame([[1] * columns], columns=[f"c{i}" for i in range(columns)]).to_csv(index=False).encode()


def _big_workbook() -> bytes:
    large = BytesIO()
    pd.DataFrame({"note": [f"{row:06d}" + "a" * 200 for row in range(6000)]}).to_excel(large, index=False)
    return large.getvalue()


def test_local_mode_has_no_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_PUBLIC", raising=False)
    assert not limits.is_public()
    assert limits.max_upload_bytes() is None
    assert limits.max_expanded_workbook_bytes() is None
    assert limits.max_table_rows() is None
    assert limits.max_table_columns() is None
    with pytest.raises(DataProblem, match="empty"):
        read_table("tracker.csv", b"")
    # Beyond every demo cap: more columns, more rows, a bigger workbook, and a payload reported as oversized.
    assert len(read_table("tracker.csv", _wide_csv(limits.DEMO_MAX_TABLE_COLUMNS + 1)).columns) == 201
    monkeypatch.setattr(limits, "DEMO_MAX_TABLE_ROWS", 3)
    monkeypatch.setattr(limits, "DEMO_MAX_EXPANDED_WORKBOOK_MB", 1)
    assert len(read_table("tracker.csv", make_demo_data().head(4).to_csv(index=False).encode())) == 4
    assert len(read_table("tracker.xlsx", _big_workbook())) == 6000
    assert len(read_table("tracker.csv", _OversizedPayload(b"a,b\n1,2\n"))) == 1  # reported size is not capped


def test_public_demo_enforces_its_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_PUBLIC", "1")
    with pytest.raises(DataProblem, match="limited to 50 MB here.*downloaded app has no such limit"):
        read_table("tracker.csv", _OversizedPayload(b"x"))
    with pytest.raises(DataProblem, match="limited to 200 columns here"):
        read_table("tracker.csv", _wide_csv(limits.DEMO_MAX_TABLE_COLUMNS + 1))
    monkeypatch.setattr(limits, "DEMO_MAX_TABLE_ROWS", 3)
    with pytest.raises(DataProblem, match="limited to 3 rows here"):
        read_table("tracker.csv", make_demo_data().head(4).to_csv(index=False).encode())
    monkeypatch.setattr(limits, "DEMO_MAX_EXPANDED_WORKBOOK_MB", 1)
    with pytest.raises(DataProblem, match="expand to at most 1 MB here"):
        read_table("tracker.xlsx", _big_workbook())
    small = BytesIO()
    make_starter_template().to_excel(small, index=False)
    assert len(read_table("tracker.xlsx", small.getvalue())) == len(make_starter_template())


def test_memory_errors_become_a_plain_message() -> None:
    assert "not enough memory" in friendly_message(MemoryError())


def test_a_tracker_above_the_old_row_cap_reads_and_validates() -> None:
    """The 1.1 release refused anything over 500,000 rows; locally that file now passes import and validation."""
    rows = 520_000
    per_respondent = 4 * 5  # brands x metrics
    respondents = rows // per_respondent
    respondent = np.repeat(np.arange(respondents), per_respondent)
    brand = np.tile(np.repeat(np.arange(4), 5), respondents)
    metric = np.tile(np.arange(5), respondents * 4)
    frame = pd.DataFrame(
        {
            "respondent_id": respondent,
            "wave": np.where(respondent % 2 == 0, "W1", "W2"),
            "brand": np.array(["A", "B", "C", "D"])[brand],
            "metric": np.array(["m1", "m2", "m3", "m4", "m5"])[metric],
            "metric_kind": np.where(metric < 3, "binary", "rating"),
            "value": np.where(metric < 3, (respondent + metric) % 2, (respondent + brand) % 7 + 1),
        }
    )
    payload = frame.to_csv(index=False).encode()
    loaded = read_table("tracker.csv", payload)
    assert len(loaded) == rows > 500_000
    contract = TrackingContract(
        respondent_column="respondent_id",
        wave_column="wave",
        brand_column="brand",
        metric_column="metric",
        value_column="value",
        kind_column="metric_kind",
    )
    audit = validate_tracking_data(loaded, contract)
    assert audit.summary["source_rows"] == rows
    assert audit.summary["respondents"] == respondents
    estimates = summarize_tracking(audit.cleaned).estimates
    assert len(estimates) == 2 * 4 * 5
    assert int(estimates["n"].sum()) == rows


def test_xlsm_and_other_extensions_are_rejected() -> None:
    frame = make_starter_template()
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    for filename in ("tracker.xlsm", "tracker.xls", "tracker.parquet"):
        with pytest.raises(DataProblem, match="CSV or XLSX"):
            read_table(filename, output.getvalue())


HOSTILE = '=cmd|" /C calc"!A0'


def _hostile_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "brand": [HOSTILE, "+SUM(A1:A9)", "-2+3", "@harmless", "Safe brand"],
            "metric": ["Awareness"] * 5,
            "=evil_header": [1, 2, 3, 4, 5],
            "note": ["control\x00char", "fine", "fine", "fine", "fine"],
        }
    )


def test_csv_export_neutralizes_formula_injection_and_control_characters() -> None:
    payload = dataframe_csv_bytes(_hostile_frame()).decode("utf-8")
    reloaded = pd.read_csv(BytesIO(payload.encode("utf-8")))
    assert reloaded.columns[2] == "'=evil_header"
    assert reloaded["brand"].iloc[0] == "'" + HOSTILE
    assert reloaded["brand"].iloc[1] == "'+SUM(A1:A9)"
    assert reloaded["brand"].iloc[2] == "'-2+3"
    assert reloaded["brand"].iloc[3] == "'@harmless"
    assert reloaded["brand"].iloc[4] == "Safe brand"
    assert reloaded["note"].iloc[0] == "controlchar"


def test_workbook_export_neutralizes_formula_injection_in_every_sheet() -> None:
    hostile = _hostile_frame()
    payload = build_evidence_workbook(
        metadata={"app": "TrackSignal", HOSTILE: HOSTILE},
        metric_catalog=hostile,
        cell_audit=hostile,
        estimates=hostile,
        contrasts=hostile,
    )
    for sheet in ("read_me", "metric_catalog", "cell_audit", "estimates", "contrasts"):
        loaded = pd.read_excel(BytesIO(payload), sheet_name=sheet)
        text = "\n".join(str(value) for value in [*loaded.columns, *loaded.to_numpy().ravel()])
        for line in text.splitlines():
            assert not line.lstrip().startswith(("=", "+", "@")), (sheet, line)
    metadata = pd.read_excel(BytesIO(payload), sheet_name="read_me")
    assert ("'" + HOSTILE) in set(metadata["field"])
    assert ("'" + HOSTILE) in set(metadata["value"])


def test_exports_neutralize_formulas_in_categorical_columns() -> None:
    hostile = _hostile_frame().astype({"brand": "category", "note": "category"})
    reloaded = pd.read_csv(BytesIO(dataframe_csv_bytes(hostile)))
    assert reloaded["brand"].iloc[0] == "'" + HOSTILE
    assert reloaded["note"].iloc[0] == "controlchar"
