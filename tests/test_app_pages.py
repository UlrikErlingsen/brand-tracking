from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")
EXAMPLES = ROOT / "examples"
PAGES = [
    "Welcome",
    "1 · Data & contract",
    "2 · Current pulse",
    "3 · Change over time",
    "4 · Brand & segment compare",
    "5 · Evidence pack",
    "Methods & boundaries",
]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_with_fictional_demo(page: str) -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == page
    assert "brand-tracking evidence" in " ".join(str(item.value).lower() for item in app.sidebar.caption)


def test_welcome_preserves_product_boundaries_and_name_status() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    body = "\n".join(str(markdown.value) for markdown in app.markdown)
    assert "universal brand-equity score" in body
    assert "MeasureSignal" in body
    assert "PositionSignal" in body
    assert "not legally cleared" in body
    assert "not a trademark opinion" in body


def test_wave_contrast_runs_from_demo() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value("3 · Change over time").run()
    button = next(button for button in app.button if button.label == "Estimate wave changes")
    button.click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["last_contrast"] is not None
    assert not app.session_state["last_contrast"].contrasts.empty


def test_pairing_requires_explicit_confirmation_in_the_ui() -> None:
    source = Path(APP).read_text(encoding="utf-8")
    assert "paired_ids=panel_ids" in source
    assert "paired_ids=same_respondents" in source
    assert '"Respondent IDs are stable panel IDs across waves"' in source

    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value("3 · Change over time").run()
    checkbox = next(box for box in app.checkbox if "panel IDs" in box.label)
    assert checkbox.value is False


def test_in_app_demo_matches_downloadable_and_committed_demo() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    session_demo = app.session_state["raw_data"]
    committed = pd.read_csv(EXAMPLES / "tracksignal-fictional-tracker.csv")
    pd.testing.assert_frame_equal(
        session_demo.reset_index(drop=True), committed.reset_index(drop=True), check_dtype=False
    )
    # The download button must use the same generator call as the in-app demo: no divergent
    # respondents_per_wave override anywhere in the app.
    source = Path(APP).read_text(encoding="utf-8")
    assert "respondents_per_wave" not in source
    assert "dataframe_csv_bytes(_demo())" in source
