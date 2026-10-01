from pathlib import Path

from streamlit.testing.v1 import AppTest

from tracksignal import __version__


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")
UI = ROOT / "src" / "tracksignal" / "ui"


def test_shared_signal_shell_renders_with_name_status_note() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    body = "\n".join(str(item.value) for item in app.markdown)
    sidebar = "\n".join(str(item.value) for item in app.sidebar.markdown)
    sidebar_captions = "\n".join(str(item.value) for item in app.sidebar.caption)
    assert "TRACK → COMPARE → INTERPRET" in body
    assert "BRAND-TRACKING EVIDENCE" in body
    assert f"Track Signal v{__version__}" in body
    assert "estimates change, not cause" in body
    assert "Part of the Signal suite" in body
    assert "AGPL-3.0-or-later" in body
    assert "sg-mast" in body  # the shared Signal masthead
    assert "sg-foot" in body  # the shared Signal footer
    assert "Brand movement without the magic equity score" in sidebar
    assert "sg-side" in sidebar  # the shared Signal sidebar lockup
    assert "not legally cleared" in sidebar_captions
    assert "not a trademark opinion" in sidebar_captions


def test_app_uses_shared_signal_theme_instead_of_pasted_styles() -> None:
    standalone = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_source = (UI / "app.py").read_text(encoding="utf-8")
    theme = (UI / "signal_theme.py").read_text(encoding="utf-8")
    assert 'st.set_page_config(**sig.page_config("track"))' in standalone
    assert "sig.apply(NS)" in ui_source
    assert "<style>" not in standalone + ui_source
    for old_colour in ("#173c3a", "#d95b40", "#83d2b4", "#f2c66d", "#17322e", "#102c2a"):
        assert old_colour not in (standalone + ui_source).lower()
    assert (UI / "assets" / "marks" / "tracksignal-mark-64.png").exists()
    assert ":focus-visible" in theme
    assert "@media (max-width:760px)" in theme
    assert "@media (prefers-reduced-motion:reduce)" in theme
    assert "friendly_message" in ui_source


def test_readme_matches_suite_information_architecture() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Signal README template order: readers find the same section in the same place in every repo.
    sections = [
        "## Read this first",
        "## Scope",
        "## Try the demo in three minutes",
        "## Data contract",
        "## Analysis contract",
        "## Methods",
        "## Decision statuses",
        "## Exports",
        "## Run locally",
        "## Privacy",
        "## No install? Give this file to an AI",
        "## Development",
        "## Where this fits in Signal",
        "## References",
        "## Originality and license",
    ]
    positions = [readme.find(f"\n{heading}\n") for heading in sections]
    assert all(position >= 0 for position in positions), dict(zip(sections, positions, strict=True))
    assert positions == sorted(positions)
    assert readme.startswith('<p align="center">\n  <img src="assets/tracksignal-banner.png"')
    assert "assets/tracksignal-banner.svg" not in readme
    assert "Signal-Brand-b2622d" in readme  # family badge in the Brand 600 colour
    assert "github.com/UlrikErlingsen/brand-tracking/actions" in readme  # tests badge
    assert "Open brand-tracking evidence" in readme
    assert "**Track Signal**" in readme
    assert '<img src="assets/tracksignal-mark-64.png"' in readme  # suite footer
    assert "Creator Signal" not in readme
    assert "does **not** manufacture a universal" in readme
    assert "not legal clearance or a trademark opinion" in readme
    for path in ("assets/tracksignal-banner.png", "assets/tracksignal-mark-64.png", "assets/tracksignal-social.png"):
        assert (ROOT / path).exists()


def test_runtime_scaffolding_is_private_and_health_checked() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (ROOT / "run_app.command").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "gatherUsageStats = false" in config
    assert "maxUploadSize = 50" in config
    assert 'base = "light"' in config
    assert 'primaryColor = "#b2622d"' in config  # Signal Brand family, 600 step
    assert "USER tracksignal" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "chown" not in dockerfile
    assert "8586" in dockerfile
    assert "--browser.gatherUsageStats=false" in launcher
    assert "TRACKSIGNAL_PORT" in launcher
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in workflow
