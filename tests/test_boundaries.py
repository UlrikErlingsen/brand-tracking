from pathlib import Path


ROOT = Path(__file__).parents[1]

NEUTRAL_ORIGINALITY = (
    "It does not reproduce lecture slides, notes, cases, exercises, diagrams, assessment material, "
    "datasets, questionnaire wording, or institution-specific frameworks; general topics encountered "
    "in education only define the problem domain."
)


def _product_text() -> str:
    paths = [ROOT / "app.py", ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_docs_reject_universal_score_and_use_neutral_originality_phrasing() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sources = (ROOT / "docs" / "sources-and-originality.md").read_text(encoding="utf-8")
    assert "does **not** manufacture a universal" in readme
    assert NEUTRAL_ORIGINALITY in readme
    assert NEUTRAL_ORIGINALITY in sources
    # Built by concatenation so a repository-wide grep for the school name stays clean.
    school_name = "Norwegian" + " Business" + " School"
    assert school_name not in _product_text()


def test_exact_product_and_package_name_are_consistent() -> None:
    from tracksignal import __version__

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "tracksignal"' in pyproject
    assert f'version = "{__version__}"' in pyproject
    assert "TrackSignal" in (ROOT / "README.md").read_text(encoding="utf-8")
    # Built by concatenation so a repository-wide grep for the old working name stays clean.
    old_name = "Pulse" + "Signal"
    assert old_name not in _product_text()


def test_name_is_not_presented_as_legally_cleared() -> None:
    text = _product_text().lower()
    screen = (ROOT / "docs" / "name-screen.md").read_text(encoding="utf-8")
    assert "not legally cleared" in text
    assert "not legal advice" in text or "not a trademark opinion" in text
    assert "it is not legally cleared" in screen
    assert "Screen date: 17 July 2026." in screen
