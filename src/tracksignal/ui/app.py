"""Track Signal Streamlit UI.

Everything that draws the app runs inside ``render()`` (or the functions it calls), so it runs on every rerun,
both in the standalone ``app.py`` and inside Signal Hub. Module-level code here only defines constants and
functions. ``render()`` never calls ``st.set_page_config`` or ``st.navigation``.
"""

from __future__ import annotations

import os
import traceback

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tracksignal import __version__
from tracksignal.analysis import compare_groups, summarize_tracking
from tracksignal.design import TrackingContract, order_labels, validate_tracking_data
from tracksignal.errors import DataProblem, friendly_message
from tracksignal.examples import make_demo_data, make_starter_template
from tracksignal.io import build_evidence_workbook, dataframe_csv_bytes, read_table
from tracksignal.ui import signal_theme as sig


NS = "track"


def k(name: str) -> str:
    """Namespace a session-state or widget key with the app slug, so apps can share one Hub session."""
    return f"{NS}:{name}"


NAME_NOTE = (
    "The Track Signal name (screened as the exact string “TrackSignal”) passed an informal availability screen "
    "on 17 July 2026: no active company or software product using the exact name was found. That screen is "
    "practical, not legal advice — the name is not legally cleared and this is not a trademark opinion. "
    "See docs/name-screen.md."
)
SIDEBAR_TAGLINE = "Brand movement without the magic equity score."
MASTHEAD_KICKER = "TRACK → COMPARE → INTERPRET"
MASTHEAD_PROMISES = ["Separate measures", "Visible uncertainty", "Local evidence"]
FOOTER_LINE = "estimates change, not cause"


STANDARD_CONTRACT = TrackingContract(
    respondent_column="respondent_id",
    wave_column="wave",
    segment_column="segment",
    brand_column="brand",
    metric_column="metric",
    value_column="value",
    kind_column="metric_kind",
    weight_column="weight",
    family_column="family",
    source_column="measurement_source",
    threshold_column="practical_threshold",
)


@st.cache_data(show_spinner=False)
def _demo() -> pd.DataFrame:
    # One generator call with default settings everywhere: the in-app demo, the downloadable
    # demo CSV, and the committed example files all contain identical data.
    return make_demo_data()


def _validate_and_store(frame: pd.DataFrame, contract: TrackingContract) -> None:
    audit = validate_tracking_data(frame, contract)
    st.session_state[k("raw_data")] = frame
    st.session_state[k("contract")] = contract
    st.session_state[k("audit")] = audit
    st.session_state.pop(k("last_contrast"), None)


def _ensure_state() -> None:
    if k("raw_data") not in st.session_state:
        _validate_and_store(_demo(), STANDARD_CONTRACT)


def show_error(exc: Exception) -> None:
    """Render a useful error while keeping tracebacks opt-in."""
    st.error(friendly_message(exc))
    if not isinstance(exc, (DataProblem, ValueError)) and os.getenv("TRACKSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def _warnings(messages: tuple[str, ...] | list[str]) -> None:
    for message in messages:
        st.warning(message)


def _ordered(series: pd.Series) -> list[str]:
    # Natural (numeric-aware) order, so "Wave 2" precedes "Wave 10".
    return order_labels(series)


def _optional_column(label: str, columns: list[str], preferred: str, key: str) -> str | None:
    choices = ["[None]", *columns]
    default = choices.index(preferred) if preferred in choices else 0
    selected = st.selectbox(label, choices, index=default, key=key)
    return None if selected == "[None]" else selected


def _required_column(label: str, columns: list[str], preferred: str, key: str) -> str:
    default = columns.index(preferred) if preferred in columns else 0
    return st.selectbox(label, columns, index=default, key=key)


def _scope_data(frame: pd.DataFrame, *, wave: str | None = None, segment: str | None = None, brand: str | None = None) -> pd.DataFrame:
    scoped = frame
    for column, value in (("wave", wave), ("segment", segment), ("brand", brand)):
        if value is not None:
            scoped = scoped.loc[scoped[column].astype(str).eq(str(value))]
    return scoped


def page_welcome() -> None:
    sig.hero(
        NS,
        eyebrow="BRAND-TRACKING EVIDENCE",
        title="Is the brand moving—or is the tracker",
        em="just noisy?",
        body=(
            "Compare noticeability, consideration, choice, loyalty, associations, and relationship measures across "
            "brands, segments, and waves—without manufacturing a universal brand-equity score."
        ),
        pills=[
            "binary & rating measures",
            "wave contrasts",
            "brand comparisons",
            "segment comparisons",
            "paired analysis",
            "confidence intervals",
            "auditable exports",
        ],
    )
    sig.note("muted", f"**Name status:** {NAME_NOTE}")
    sig.cards(
        [
            (
                "01 · SEPARATE",
                "Keep each signal legible",
                "Awareness, familiarity, consideration, usage, loyalty, association, trust, quality, attachment, and "
                "reputation retain their own meaning and scale—never ingredients in an opaque score.",
            ),
            (
                "02 · COMPARE",
                "Show magnitude with uncertainty",
                "Wave, brand, and segment contrasts report the effect, interval, practical threshold, and "
                "multiplicity-adjusted evidence status.",
            ),
            (
                "03 · RESPECT",
                "Honor the measurement work",
                "Construct scores require a Measure Signal or equivalent validation reference. Perceptual maps and "
                "multivariate positioning remain in Position Signal.",
            ),
        ]
    )
    st.markdown("### Workflow")
    st.markdown(
        "1. Validate the long-format tracking contract.\n"
        "2. Inspect the current profile.\n"
        "3. Compare waves.\n"
        "4. Compare brands or segments.\n"
        "5. Export an auditable evidence pack."
    )
    sig.note(
        "boundary",
        "**Interpretation boundary:** movement can reflect sampling variation, questionnaire or mode changes, "
        "weighting, coverage, seasonality, or real population change. Track Signal estimates differences; it does "
        "not identify why they occurred.",
    )


def page_data_contract() -> None:
    sig.header(
        "Step 1",
        "Data and measurement contract",
        "Declare what each column and metric means before looking at movement. The app uses one row per respondent × wave × segment × brand × metric.",
    )
    top_left, top_right = st.columns([1.15, 1])
    with top_left:
        uploaded = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], key=k("tracker_upload"))
        if uploaded is not None and st.button("Read uploaded file", type="primary", key=k("read_upload")):
            try:
                frame = read_table(uploaded.name, uploaded.getvalue())
                st.session_state[k("candidate_data")] = frame
                st.success(f"Read {len(frame):,} rows and {len(frame.columns)} columns. Map the roles below.")
            except DataProblem as exc:
                show_error(exc)
    with top_right:
        demo_bytes = dataframe_csv_bytes(_demo())
        st.download_button(
            "Download fictional demo CSV",
            demo_bytes,
            "tracksignal-fictional-tracker.csv",
            "text/csv",
            key=k("download_demo"),
        )
        st.download_button(
            "Download starter template CSV",
            dataframe_csv_bytes(make_starter_template()),
            "tracksignal-starter-template.csv",
            "text/csv",
            key=k("download_template"),
        )
        if st.button("Restore in-app fictional demo", key=k("restore_demo")):
            _validate_and_store(_demo(), STANDARD_CONTRACT)
            st.session_state.pop(k("candidate_data"), None)
            st.success("Fictional demo restored.")

    candidate = st.session_state.get(k("candidate_data"), st.session_state[k("raw_data")])
    columns = candidate.columns.astype(str).tolist()
    if not columns:
        st.error("The candidate file has no columns.")
        return
    st.markdown("### Column roles")
    row1 = st.columns(3)
    with row1[0]:
        respondent = _required_column("Respondent ID", columns, "respondent_id", k("map_respondent"))
    with row1[1]:
        wave = _required_column("Survey wave", columns, "wave", k("map_wave"))
    with row1[2]:
        segment = _optional_column("Segment (optional)", columns, "segment", k("map_segment"))
    row2 = st.columns(3)
    with row2[0]:
        brand = _required_column("Brand", columns, "brand", k("map_brand"))
    with row2[1]:
        metric = _required_column("Metric name", columns, "metric", k("map_metric"))
    with row2[2]:
        value = _required_column("Observed value", columns, "value", k("map_value"))
    row3 = st.columns(3)
    with row3[0]:
        kind = _required_column("Metric kind", columns, "metric_kind", k("map_kind"))
    with row3[1]:
        family = _optional_column("Metric family", columns, "family", k("map_family"))
    with row3[2]:
        weight = _optional_column("Survey weight", columns, "weight", k("map_weight"))
    row4 = st.columns(2)
    with row4[0]:
        source = _optional_column("Measurement evidence/source", columns, "measurement_source", k("map_source"))
    with row4[1]:
        threshold = _optional_column("Practical-change threshold", columns, "practical_threshold", k("map_threshold"))
        st.caption(
            "Without a declared positive threshold, contrasts can only report statistical detection "
            "(“DETECTED — NO PRACTICAL THRESHOLD DECLARED”), never a practically “CLEAR” change."
        )
    if st.button("Validate tracking contract", type="primary", key=k("validate_contract")):
        try:
            contract = TrackingContract(
                respondent_column=respondent,
                wave_column=wave,
                segment_column=segment,
                brand_column=brand,
                metric_column=metric,
                value_column=value,
                kind_column=kind,
                weight_column=weight,
                family_column=family,
                source_column=source,
                threshold_column=threshold,
            )
            _validate_and_store(candidate, contract)
            st.success("Tracking contract accepted. Analysis pages now use this validated dataset.")
        except DataProblem as exc:
            show_error(exc)

    audit = st.session_state[k("audit")]
    st.markdown("### Current validated dataset")
    summary_columns = st.columns(6)
    for column, (label, key) in zip(
        summary_columns,
        (("Rows", "source_rows"), ("Respondents", "respondents"), ("Waves", "waves"), ("Segments", "segments"), ("Brands", "brands"), ("Metrics", "metrics")),
        strict=True,
    ):
        column.metric(label, f"{int(audit.summary[key]):,}")
    _warnings(audit.warnings)
    st.markdown("#### Metric registry")
    st.dataframe(audit.metric_catalog, width="stretch", hide_index=True)
    with st.expander("Cell-size audit"):
        st.dataframe(audit.cell_audit, width="stretch", hide_index=True)


def page_dashboard() -> None:
    sig.header(
        "Step 2",
        "Current brand pulse",
        "Inspect one metric at a time, then use the complete table to see the wider pattern. No across-metric aggregation is performed.",
    )
    audit = st.session_state[k("audit")]
    cleaned = audit.cleaned
    waves = _ordered(cleaned["wave"])
    segments = _ordered(cleaned["segment"])
    families = _ordered(cleaned["family"])
    selectors = st.columns(3)
    with selectors[0]:
        wave = st.selectbox("Wave", waves, index=len(waves) - 1, key=k("dashboard_wave"))
    with selectors[1]:
        segment = st.selectbox("Segment", segments, key=k("dashboard_segment"))
    with selectors[2]:
        family = st.selectbox("Metric family", families, key=k("dashboard_family"))
    st.caption(
        "Waves are ordered numerically where labels contain numbers (so “Wave 2” precedes “Wave 10”). "
        "Check that the listed order matches your fieldwork order before reading the latest wave."
    )
    scoped = _scope_data(cleaned, wave=wave, segment=segment)
    family_metrics = _ordered(scoped.loc[scoped["family"].eq(family), "metric"])
    if not family_metrics:
        st.info("No metrics exist in this scope.")
        return
    metric = st.selectbox("Metric", family_metrics, key=k("dashboard_metric"))
    summary = summarize_tracking(scoped)
    selected = summary.estimates.loc[summary.estimates["metric"].eq(metric)].sort_values("estimate")
    kind = str(selected["metric_kind"].iloc[0])
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=selected["brand"],
            x=selected["estimate"],
            orientation="h",
            marker_color=sig.app(NS)["fam"]["600"],
            error_x={
                "type": "data",
                "symmetric": False,
                "array": selected["ci_high"] - selected["estimate"],
                "arrayminus": selected["estimate"] - selected["ci_low"],
            },
            customdata=np.column_stack([selected["ci_low"], selected["ci_high"], selected["effective_n"]]),
            hovertemplate="%{y}<br>Estimate %{x:.3f}<br>95% CI [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>Effective n %{customdata[2]:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        template=sig.template(NS),
        title=f"{metric} · {wave} · {segment}",
        xaxis_title="Proportion" if kind == "binary" else "Mean on original scale",
        yaxis_title="",
        height=max(360, 80 * len(selected)),
        margin={"l": 30, "r": 25, "t": 65, "b": 45},
    )
    if kind == "binary":
        fig.update_xaxes(range=[0, 1], tickformat=".0%")
    sig.chart(NS, fig, key=k("dashboard_chart"))
    st.caption(f"Interval method: {selected['interval_method'].iloc[0]}. Error bars are {(1 - 0.05) * 100:.0f}% confidence intervals.")
    st.markdown("### Complete profile—still separate metrics")
    profile = summary.estimates[
        ["family", "metric", "metric_kind", "brand", "estimate", "ci_low", "ci_high", "n", "effective_n", "interval_method"]
    ].sort_values(["family", "metric", "brand"])
    st.dataframe(profile, width="stretch", hide_index=True)
    _warnings(summary.warnings)


def _contrast_table(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "dimension", "reference", "comparison", "brand", "metric", "metric_kind",
        "reference_estimate", "comparison_estimate", "difference", "ci_low", "ci_high",
        "practical_threshold", "q_value_bh", "evidence_status", "paired_n",
        "reference_dropped_n", "comparison_dropped_n", "method",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame[available]


def page_wave_change() -> None:
    sig.header(
        "Step 3",
        "Change over time",
        "Contrast two waves within a declared segment. The result separates estimated movement, sampling uncertainty, practical magnitude, and multiplicity control.",
    )
    cleaned = st.session_state[k("audit")].cleaned
    waves = _ordered(cleaned["wave"])
    if len(waves) < 2:
        st.info("At least two waves are required.")
        return
    segments = _ordered(cleaned["segment"])
    controls = st.columns(3)
    with controls[0]:
        reference = st.selectbox("Reference wave", waves, index=max(0, len(waves) - 2), key=k("wave_reference"))
    with controls[1]:
        comparison = st.selectbox("Comparison wave", waves, index=len(waves) - 1, key=k("wave_comparison"))
    with controls[2]:
        segment = st.selectbox("Segment", segments, key=k("wave_segment"))
    st.caption(
        "Waves are ordered numerically where labels contain numbers (so “Wave 2” precedes “Wave 10”). "
        "Check that the wave order matches your fieldwork order before contrasting."
    )
    panel_ids = st.checkbox(
        "Respondent IDs are stable panel IDs across waves",
        value=False,
        key=k("wave_panel_ids"),
        help=(
            "Tick only when the same people genuinely return with the same ID in both waves. "
            "Paired analysis is then used where IDs overlap, and only matched respondents contribute. "
            "Serial or recycled IDs would otherwise fabricate pairs, so this is off by default."
        ),
    )
    if st.button("Estimate wave changes", type="primary", key=k("estimate_wave")):
        try:
            scoped = _scope_data(cleaned, segment=segment)
            result = compare_groups(
                scoped,
                dimension="wave",
                reference=reference,
                comparison=comparison,
                by=("brand", "metric"),
                paired_ids=panel_ids,
            )
            st.session_state[k("last_contrast")] = result
        except DataProblem as exc:
            show_error(exc)
    result = st.session_state.get(k("last_contrast"))
    if result is None or result.contrasts["dimension"].iloc[0] != "wave":
        st.info("Choose two waves and run the contrast.")
        return
    statuses = result.contrasts["evidence_status"].value_counts()
    summary_columns = st.columns(min(4, len(statuses))) if len(statuses) else []
    for column, (status, count) in zip(summary_columns, statuses.items(), strict=False):
        column.metric(str(status).title(), int(count))
    st.dataframe(_contrast_table(result.contrasts), width="stretch", hide_index=True)
    st.download_button(
        "Download wave contrast CSV",
        dataframe_csv_bytes(result.contrasts),
        "tracksignal-wave-contrast.csv",
        "text/csv",
        key=k("download_wave_contrast"),
    )
    _warnings(result.warnings)


def page_comparisons() -> None:
    sig.header(
        "Step 4",
        "Brand and segment comparisons",
        "Compare two brands—within the same respondents when you confirm the IDs identify the same people—or two segments as independent groups. These are descriptive survey contrasts—not positioning maps or causal effects.",
    )
    cleaned = st.session_state[k("audit")].cleaned
    waves = _ordered(cleaned["wave"])
    segments = _ordered(cleaned["segment"])
    brands = _ordered(cleaned["brand"])
    brand_tab, segment_tab = st.tabs(["Brand contrast", "Segment contrast"])
    with brand_tab:
        controls = st.columns(4)
        with controls[0]:
            wave = st.selectbox("Wave", waves, index=len(waves) - 1, key=k("brand_wave"))
        with controls[1]:
            segment = st.selectbox("Segment", segments, key=k("brand_segment"))
        with controls[2]:
            reference_brand = st.selectbox("Reference brand", brands, key=k("brand_reference"))
        comparison_options = [brand for brand in brands if brand != reference_brand]
        with controls[3]:
            comparison_brand = st.selectbox("Comparison brand", comparison_options, key=k("brand_comparison"))
        same_respondents = st.checkbox(
            "Respondent IDs identify the same people for both brands in this wave",
            value=False,
            key=k("brand_paired_ids"),
            help=(
                "Tick only when each respondent rated both brands (not a monadic design with separate samples "
                "per brand). Paired within-respondent analysis is then used where IDs overlap; unmatched "
                "respondents are dropped from paired rows and reported."
            ),
        )
        if st.button("Estimate brand contrast", type="primary", key=k("estimate_brand")):
            try:
                scoped = _scope_data(cleaned, wave=wave, segment=segment)
                result = compare_groups(
                    scoped,
                    dimension="brand",
                    reference=reference_brand,
                    comparison=comparison_brand,
                    by=("metric",),
                    paired_ids=same_respondents,
                )
                st.session_state[k("brand_contrast")] = result
                st.session_state[k("last_contrast")] = result
            except DataProblem as exc:
                show_error(exc)
        brand_result = st.session_state.get(k("brand_contrast"))
        if brand_result is not None:
            st.dataframe(_contrast_table(brand_result.contrasts), width="stretch", hide_index=True)
            _warnings(brand_result.warnings)
    with segment_tab:
        if len(segments) < 2:
            st.info("At least two segments are required.")
        else:
            controls = st.columns(4)
            with controls[0]:
                wave = st.selectbox("Wave", waves, index=len(waves) - 1, key=k("segment_wave"))
            with controls[1]:
                brand = st.selectbox("Brand", brands, key=k("segment_brand"))
            with controls[2]:
                reference_segment = st.selectbox("Reference segment", segments, key=k("segment_reference"))
            comparison_options = [segment for segment in segments if segment != reference_segment]
            with controls[3]:
                comparison_segment = st.selectbox("Comparison segment", comparison_options, key=k("segment_comparison"))
            if st.button("Estimate segment contrast", type="primary", key=k("estimate_segment")):
                try:
                    scoped = _scope_data(cleaned, wave=wave, brand=brand)
                    result = compare_groups(
                        scoped,
                        dimension="segment",
                        reference=reference_segment,
                        comparison=comparison_segment,
                        by=("metric",),
                    )
                    st.session_state[k("segment_contrast")] = result
                    st.session_state[k("last_contrast")] = result
                except DataProblem as exc:
                    show_error(exc)
            segment_result = st.session_state.get(k("segment_contrast"))
            if segment_result is not None:
                st.dataframe(_contrast_table(segment_result.contrasts), width="stretch", hide_index=True)
                _warnings(segment_result.warnings)


def page_evidence_pack() -> None:
    sig.header(
        "Step 5",
        "Evidence pack",
        "Export the declared metric registry, cell audit, all tracking estimates, and the most recently displayed contrast so another analyst can inspect the work.",
    )
    audit = st.session_state[k("audit")]
    summary = summarize_tracking(audit.cleaned)
    latest = st.session_state.get(k("last_contrast"))
    contrast_frame = latest.contrasts if latest is not None else None
    metadata = {
        "app": "Track Signal",
        "version": __version__,
        "public_name_status": "Informal availability screen passed (17 July 2026); not legally cleared; not a trademark opinion.",
        "analysis_boundary": "Separate metric estimates and descriptive contrasts; no universal equity score and no causal claim.",
        "source_rows": audit.summary["source_rows"],
        "respondents": audit.summary["respondents"],
        "waves": audit.summary["waves"],
        "segments": audit.summary["segments"],
        "brands": audit.summary["brands"],
        "metrics": audit.summary["metrics"],
        "weighted": audit.summary["weighted"],
        "audit_warnings": audit.warnings,
        "summary_warnings": summary.warnings,
        "contrast_warnings": latest.warnings if latest is not None else (),
    }
    workbook = build_evidence_workbook(
        metadata=metadata,
        metric_catalog=audit.metric_catalog,
        cell_audit=audit.cell_audit,
        estimates=summary.estimates,
        contrasts=contrast_frame,
    )
    st.download_button(
        "Download Track Signal evidence pack",
        workbook,
        "tracksignal-evidence-pack.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key=k("download_evidence_pack"),
    )
    st.markdown("### Included")
    st.write("- Release and interpretation metadata\n- Metric registry and measurement provenance\n- Cell sizes and effective sample sizes\n- Separate estimates with confidence intervals\n- Latest wave, brand, or segment contrast, when one has been run")
    st.info("The workbook intentionally excludes a universal brand-equity score and does not turn descriptive movement into a causal story.")


def page_methods() -> None:
    sig.header(
        "Methods and boundaries",
        "What Track Signal calculates",
        "The app is deliberately narrower than a general survey package: it handles repeated brand-tracking estimates and transparent pairwise contrasts.",
    )
    st.markdown("### Estimates")
    st.write("Binary metrics use Wilson score intervals. Weighted binary metrics use a clearly labelled Kish effective-sample-size approximation. Ratings and externally validated construct scores use t intervals on their original scales.")
    st.markdown("### Comparisons")
    st.write("Independent unweighted binary contrasts use a Newcombe–Wilson difference interval with a matching unpooled z test. Continuous contrasts use Welch intervals. Paired analysis is used only when you explicitly confirm that respondent IDs identify the same people in both groups and the IDs overlap; overlapping IDs alone never trigger pairing, and paired rows report how many pairs were used and how many respondents were dropped from each group. For unweighted paired binary data the p-value comes from the exact McNemar test while the interval uses a paired-difference approximation; the method column labels this hybrid. Benjamini–Hochberg q-values control false-discovery rate within the displayed contrast family.")
    st.markdown("### Decision language")
    st.write("A change is labelled clear only when its interval excludes zero, its BH q-value is at most 0.05, and its absolute size reaches the declared positive practical threshold. When no practical threshold is declared (or the declared value is zero), the app cannot judge business relevance: a detected change is labelled “DETECTED — NO PRACTICAL THRESHOLD DECLARED” instead of “CLEAR”. The full estimate and interval remain primary; the label is an audit aid, not a verdict.")
    st.markdown("### Product boundaries")
    st.write("- Multi-item item-level validation belongs in Measure Signal. Track Signal accepts only the resulting documented score.\n- Track Signal may track a prespecified attribute-ownership item over time. Perceptual maps, association geometry, and POP/POD mapping remain in Position Signal.\n- Driver models belong in Driver Signal. Experiments belong in Experiment Signal. Text-derived metrics belong in Text Signal.\n- Complex survey designs require specialist variance estimation; this release does not model strata, clusters, finite-population corrections, or replicate weights.\n- The app estimates population differences under a sampling model. It does not identify causes.")
    st.markdown("### Sources")
    st.write("The implementation is independently written from public statistical and brand-measurement literature. Full references and originality notes are bundled in the repository documentation.")


PAGES = {
    "Welcome": page_welcome,
    "1 · Data & contract": page_data_contract,
    "2 · Current pulse": page_dashboard,
    "3 · Change over time": page_wave_change,
    "4 · Brand & segment compare": page_comparisons,
    "5 · Evidence pack": page_evidence_pack,
    "Methods & boundaries": page_methods,
}


def _sidebar() -> str:
    """Draw the sidebar lockup, page selector and status captions; return the selected page."""
    sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
    with st.sidebar:
        st.caption(f"Brand-tracking evidence · v{__version__}")
        page = st.radio("Workflow", list(PAGES), key=k("page"))
        st.markdown("---")
        audit = st.session_state[k("audit")]
        st.caption(
            f"Validated: {audit.summary['waves']} waves · {audit.summary['brands']} brands · "
            f"{audit.summary['metrics']} separate metrics"
        )
        st.caption(
            "Name status: informally screened (17 July 2026); not legally cleared and not a trademark opinion."
        )
        st.caption("Local mode · no telemetry · no external AI calls · uploads stay in this Python process")
    return page


def render() -> None:
    """Draw the whole Track Signal app on the current page. Never calls st.set_page_config or st.navigation."""
    sig.apply(NS)
    _ensure_state()
    page = _sidebar()
    sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)
    try:
        PAGES[page]()
    except Exception as exc:
        show_error(exc)
    sig.footer(NS, __version__, FOOTER_LINE)
