# Changelog

## 1.2.0 — 2026-10-03

Larger datasets: Track Signal now handles trackers from large organizations. The statistics, data contract and exports are unchanged; the same data give the same estimates and contrasts.

### Larger datasets

- Upload limit raised from 50 MB to 1,000 MB (one constant, `MAX_UPLOAD_MB`), the row limit from 500,000 to 20,000,000, and the expanded-workbook guard from 200 MB to 5,000 MB. The column limit stays at 200. Error messages state the new limits.
- `run_app.bat` and `run_app.command` read `TRACKSIGNAL_MAX_UPLOAD_MB` (default 1000) and pass it to `--server.maxUploadSize`; the Dockerfile sets `STREAMLIT_SERVER_MAX_UPLOAD_SIZE=1000` instead of a command-line flag. Signal Hub keeps its public demo at 50 MB, and the upload caption shows the limit that actually applies.
- CSV text columns are parsed straight into categories, and validated labels are stored as categories, so millions of repeated wave, brand and metric labels no longer hold one Python string per cell.
- Validation works on distinct labels and grouped checks instead of per-row string conversions; cell estimates are computed in one vectorized pass instead of a loop over cells; contrasts split each group once instead of filtering for every cell. No step samples the data.
- Measured on a 5,000,000-row, 490 MB tracker (6,000 cells): read 2.5 s, validate 4.1 s, all estimates 1.1 s, a wave contrast 0.3 s; peak memory 1.1 GB including the uploaded file (1.1.0 needed 21 s to validate, 5.7 s per contrast and 2.6 GB). A compact 20,000,000-row file validates in about 21 s with 3.6 GB peak memory.
- Reading and validation show a spinner. Exports also neutralize formulas in categorical columns.
- New tests: a 520,000-row file (over the old cap) reads and validates, the limit messages, the expanded-workbook guard, launcher and Docker settings, and vectorized estimates matching the per-cell formulas on categorical and text labels.

### Suite

- Suite: Rival, Reach, Learn and Blueprint Signal added to the suite table (README and the shared theme), and the local Streamlit upload cap in `.streamlit/config.toml` is 1000 MB.

## 1.1.0 — 2026-10-02

Signal brand refresh and Signal Hub entry point. The analysis, statistics, data contract and exports are unchanged.

### Brand

- Display name written **Track Signal** (with a space) in the app, README, docs, launchers and metadata. Package, file and environment-variable names stay `tracksignal` / `TRACKSIGNAL_*`. The name screen still covers the exact string “TrackSignal” only; no new clearance is claimed.
- The app uses the shared `signal_theme` module (Organic Signal design, Brand family colour `#b2622d`, Figtree): sidebar lockup, masthead, hero, cards, notes, footer, Plotly template and the mark as favicon replace the pasted styles.
- New banner, social preview and marks in `assets/`; the old banner SVG is removed. `.streamlit/config.toml` uses the family colours.
- README follows the Signal template; bug-report and feature-request issue templates added.

### Signal Hub contract

- `tracksignal.ui` exposes `APP_INFO` and `render()`, so Signal Hub can embed the app; `app.py` is now a thin standalone entry point.
- All session-state and widget keys are namespaced `track:` (including the page selector).
- `streamlit` and `plotly` moved to a `ui` extra (also in `test`); the analysis core installs without them. `requirements.txt` still lists everything.
- New tests: no Streamlit/Plotly import outside `tracksignal.ui`, `render()` runs from a script without a page config, and every widget key is namespaced.

## 1.0.0 — 2026-07-17

First release, published as **TrackSignal** (never released under any earlier working name).

### Application

- Long-format brand-tracking contract and audit with separate binary, rating, and documented construct metrics.
- Wilson, Newcombe–Wilson, paired, and Welch uncertainty methods; approximate positive-weight support with explicit Kish limitations.
- Brand, segment, and wave comparisons with Benjamini–Hochberg q-values and declared practical thresholds.
- Synthetic deterministic examples, formula-injection-safe evidence-pack export, AI analyst protocol, and methods documentation.
- Unified Signal-suite shell: SVG lockup, masthead, responsive welcome hero, accessible focus states, canonical local-first footer, friendly top-level error handling, explicit no-telemetry settings, a non-root health-checked container, CI, and resilient local launchers.

### Statistical honesty fixes folded into this release

- Practical thresholds must be declared and positive. An undeclared or zero threshold no longer silently degenerates the “CLEAR” labels into a bare significance test; such contrasts are labelled `DETECTED — NO PRACTICAL THRESHOLD DECLARED` with visible warnings at validation, contrast, and UI layers.
- Paired analysis now requires explicit confirmation that respondent IDs identify the same people (checkbox, off by default; `paired_ids=True` in the API). Overlapping IDs alone never trigger pairing, and paired rows report pairs used plus respondents dropped from each group, on screen and in the export.
- Independent unweighted binary contrasts pair the Newcombe–Wilson interval with an unpooled z test so the interval and p-value describe the same comparison; the paired-binary McNemar/interval hybrid is labelled explicitly.
- Wave labels sort naturally (numeric-aware), so “Wave 2” precedes “Wave 10”, with a visible reminder to verify fieldwork order.
- The downloadable demo CSV is generated by the same call as the preloaded in-app demo, so downloaded numbers reproduce on-screen numbers.

### Security hardening folded into this release

- All CSV and XLSX export cells and headers are sanitized against spreadsheet formula injection, and control characters are stripped.
- `defusedxml.defuse_stdlib()` is applied before any Excel parsing.
- Upload limits enforced in code: 50 MB per file, 200 MB expanded workbook size, 500,000 rows, 200 columns. `.xlsm` uploads are no longer accepted.
- The Docker image keeps application code root-owned; the runtime user gets only a writable home directory.

### Naming

- Released under the name TrackSignal after an informal availability screen on 17 July 2026 (no active exact-name product found; not legal clearance and not a trademark opinion — see `docs/name-screen.md`).
