from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")


def test_shared_signal_shell_renders_with_name_status_note() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    body = "\n".join(str(item.value) for item in app.markdown)
    sidebar = "\n".join(str(item.value) for item in app.sidebar.markdown)
    sidebar_captions = "\n".join(str(item.value) for item in app.sidebar.caption)
    assert "TRACK → COMPARE → INTERPRET" in body
    assert "BRAND-TRACKING EVIDENCE" in body
    assert "TrackSignal v1.0.0" in body
    assert "estimates change, not cause" in body
    assert "Part of the Signal suite" in body
    assert "AGPL-3.0-or-later" in body
    assert "Brand movement without the magic equity score" in sidebar
    assert "not legally cleared" in sidebar_captions
    assert "not a trademark opinion" in sidebar_captions


def test_app_source_contains_responsive_accessible_suite_styles() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "#173c3a" in source
    assert "#d95b40" in source
    assert "#83d2b4" in source
    assert "#f2c66d" in source
    assert ":focus-visible" in source
    assert "@media (max-width:760px)" in source
    assert "@media (prefers-reduced-motion:reduce)" in source
    assert "friendly_message" in source


def test_readme_matches_suite_information_architecture() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "assets/tracksignal-banner.svg",
        "Open brand-tracking evidence",
        "## Read this first",
        "## Try the fictional demo in three minutes",
        "## Data contract",
        "## Methods and decision language",
        "## Evidence pack",
        "## Run locally",
        "## Privacy",
        "## Development checks",
        "## Relationship to the Signal suite",
        "## Academic independence and originality",
        "## License",
    ]
    for text in required:
        assert text in readme
    assert "does **not** manufacture a universal" in readme
    assert "not legal clearance or a trademark opinion" in readme
    assert "github.com/UlrikErlingsen/brand-tracking/actions" not in readme


def test_runtime_scaffolding_is_private_and_health_checked() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (ROOT / "run_app.command").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "gatherUsageStats = false" in config
    assert "maxUploadSize = 50" in config
    assert 'base = "light"' in config
    assert "USER tracksignal" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "chown" not in dockerfile
    assert "8586" in dockerfile
    assert "--browser.gatherUsageStats=false" in launcher
    assert "TRACKSIGNAL_PORT" in launcher
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in workflow
