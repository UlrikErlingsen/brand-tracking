"""Data limits: none when Track Signal runs locally; hard caps only in a public demo.

Run on someone's own computer (standalone, a local Signal Hub, or an internal company deployment), the app has no
built-in limit on file size, rows or columns: memory and processor are the limit. A public demo sets
``SIGNAL_PUBLIC=1`` (Signal Hub's public Docker image does), and then the caps below protect the shared server.
Every cap lives in this module and is read at call time, so the environment decides.
"""

from __future__ import annotations

import os

DEMO_MAX_UPLOAD_MB = 50
DEMO_MAX_EXPANDED_WORKBOOK_MB = 200
DEMO_MAX_TABLE_ROWS = 500_000
DEMO_MAX_TABLE_COLUMNS = 200

DEMO_NOTE = "This is a limit of the public demo; the downloaded app has no such limit."
MEMORY_MESSAGE = (
    "There is not enough memory for this file on this computer. Close other programs, keep only the columns the "
    "tracker needs, or split the file by wave and try again."
)


def is_public() -> bool:
    """True only in a public demo deployment (``SIGNAL_PUBLIC=1``)."""
    return os.environ.get("SIGNAL_PUBLIC") == "1"


def _cap(value: int) -> int | None:
    return value if is_public() else None


def max_upload_bytes() -> int | None:
    return _cap(DEMO_MAX_UPLOAD_MB * 1024 * 1024)


def max_expanded_workbook_bytes() -> int | None:
    return _cap(DEMO_MAX_EXPANDED_WORKBOOK_MB * 1024 * 1024)


def max_table_rows() -> int | None:
    return _cap(DEMO_MAX_TABLE_ROWS)


def max_table_columns() -> int | None:
    return _cap(DEMO_MAX_TABLE_COLUMNS)


def exceeds(value: int, limit: int | None) -> bool:
    return limit is not None and value > limit


def demo_message(what: str) -> str:
    """A capped message: names the demo limit and says the downloaded app has none."""
    return f"{what} {DEMO_NOTE}"
