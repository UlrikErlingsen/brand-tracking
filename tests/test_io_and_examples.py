from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from tracksignal.errors import DataProblem
from tracksignal.examples import make_demo_data, make_starter_template
from tracksignal.io import (
    MAX_TABLE_COLUMNS,
    MAX_UPLOAD_BYTES,
    build_evidence_workbook,
    dataframe_csv_bytes,
    read_table,
)


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


def test_upload_size_row_and_column_caps_are_enforced() -> None:
    with pytest.raises(DataProblem, match="empty"):
        read_table("tracker.csv", b"")
    with pytest.raises(DataProblem, match="50 MB"):
        read_table("tracker.csv", b"x" * (MAX_UPLOAD_BYTES + 1))
    wide = pd.DataFrame([[1] * (MAX_TABLE_COLUMNS + 1)], columns=[f"c{i}" for i in range(MAX_TABLE_COLUMNS + 1)])
    with pytest.raises(DataProblem, match="column safety limit"):
        read_table("tracker.csv", wide.to_csv(index=False).encode())


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
