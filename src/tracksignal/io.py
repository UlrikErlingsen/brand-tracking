"""Local file input and auditable evidence-pack export."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

import defusedxml
import pandas as pd

from . import limits
from .errors import DataProblem

defusedxml.defuse_stdlib()

# Run locally there are no size limits (validation, estimates and contrasts are vectorized or aggregate per cell);
# a public demo (SIGNAL_PUBLIC=1) applies the caps in limits.py.
# Text columns are detected on this many leading rows and then parsed straight into categories, so a file with
# millions of repeated wave, brand and metric labels does not hold one Python string per cell.
_TYPE_SAMPLE_ROWS = 10_000
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _safe_cell(value: object) -> object:
    if isinstance(value, str):
        cleaned = _ILLEGAL_XML.sub("", value)
        if cleaned.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + cleaned
        return cleaned
    return value


def safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Neutralize spreadsheet formulas in object cells and column headers."""
    result = frame.copy()
    for column in result.select_dtypes(include=["object", "string", "category"]).columns:
        result[column] = result[column].astype(object).map(_safe_cell)
    result.columns = [_safe_cell(str(column)) for column in result.columns]
    return result


def _read_csv(payload: bytes) -> pd.DataFrame:
    """Parse a CSV with pandas' usual type inference, but store text columns as categories."""
    sample = pd.read_csv(BytesIO(payload), nrows=_TYPE_SAMPLE_ROWS)
    text_columns = {column: "category" for column in sample.columns if sample[column].dtype == object}
    if not text_columns:
        return pd.read_csv(BytesIO(payload))
    return pd.read_csv(BytesIO(payload), dtype=text_columns)


def read_table(filename: str, payload: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if not payload:
        raise DataProblem("This file is empty.")
    if limits.exceeds(len(payload), limits.max_upload_bytes()):
        raise DataProblem(limits.demo_message(f"Uploads are limited to {limits.DEMO_MAX_UPLOAD_MB} MB here."))
    try:
        if suffix == ".csv":
            frame = _read_csv(payload)
        elif suffix == ".xlsx":
            with zipfile.ZipFile(BytesIO(payload)) as workbook_zip:
                expanded = sum(member.file_size for member in workbook_zip.infolist())
            if limits.exceeds(expanded, limits.max_expanded_workbook_bytes()):
                raise DataProblem(
                    limits.demo_message(
                        f"Workbooks may expand to at most {limits.DEMO_MAX_EXPANDED_WORKBOOK_MB} MB here."
                    )
                )
            frame = pd.read_excel(BytesIO(payload), sheet_name=0)
        else:
            raise DataProblem("Upload a CSV or XLSX file.")
    except DataProblem:
        raise
    except MemoryError as exc:
        raise DataProblem(limits.MEMORY_MESSAGE) from exc
    except Exception as exc:  # pragma: no cover - parser messages differ by dependency version
        raise DataProblem(f"Could not read {filename}: {exc}") from exc
    if limits.exceeds(len(frame), limits.max_table_rows()):
        raise DataProblem(limits.demo_message(f"Trackers are limited to {limits.DEMO_MAX_TABLE_ROWS:,} rows here."))
    if limits.exceeds(len(frame.columns), limits.max_table_columns()):
        raise DataProblem(limits.demo_message(f"Trackers are limited to {limits.DEMO_MAX_TABLE_COLUMNS} columns here."))
    return frame


def build_evidence_workbook(
    *,
    metadata: dict[str, object],
    metric_catalog: pd.DataFrame,
    cell_audit: pd.DataFrame,
    estimates: pd.DataFrame,
    contrasts: pd.DataFrame | None = None,
) -> bytes:
    output = BytesIO()
    metadata_rows = [
        {"field": key, "value": json.dumps(value) if isinstance(value, (dict, list, tuple)) else value}
        for key, value in metadata.items()
    ]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe_frame(pd.DataFrame(metadata_rows)).to_excel(writer, sheet_name="read_me", index=False)
        safe_frame(metric_catalog).to_excel(writer, sheet_name="metric_catalog", index=False)
        safe_frame(cell_audit).to_excel(writer, sheet_name="cell_audit", index=False)
        safe_frame(estimates).to_excel(writer, sheet_name="estimates", index=False)
        if contrasts is not None and not contrasts.empty:
            safe_frame(contrasts).to_excel(writer, sheet_name="contrasts", index=False)
    return output.getvalue()


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    return safe_frame(frame).to_csv(index=False).encode("utf-8")
