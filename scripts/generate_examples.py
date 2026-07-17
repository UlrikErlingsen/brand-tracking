"""Regenerate TrackSignal's deterministic fictional examples."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracksignal.examples import make_demo_data, make_starter_template  # noqa: E402


def main() -> None:
    examples = ROOT / "examples"
    examples.mkdir(exist_ok=True)
    demo = make_demo_data()
    starter = make_starter_template()
    demo.to_csv(examples / "tracksignal-fictional-tracker.csv", index=False)
    starter.to_csv(examples / "tracksignal-starter-template.csv", index=False)
    with pd.ExcelWriter(examples / "tracksignal-fictional-tracker.xlsx", engine="openpyxl") as writer:
        demo.to_excel(writer, sheet_name="tracking_data", index=False)
    with pd.ExcelWriter(examples / "tracksignal-starter-template.xlsx", engine="openpyxl") as writer:
        starter.to_excel(writer, sheet_name="tracking_data", index=False)
        pd.DataFrame(
            [
                {"metric_kind": "binary", "rule": "Values must be exactly 0 or 1."},
                {"metric_kind": "rating", "rule": "Keep the original declared response scale."},
                {"metric_kind": "construct", "rule": "Add a MeasureSignal or equivalent validation reference."},
            ]
        ).to_excel(writer, sheet_name="metric_kinds", index=False)


if __name__ == "__main__":
    main()
