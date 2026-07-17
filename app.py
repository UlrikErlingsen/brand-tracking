"""TrackSignal Streamlit application."""

from __future__ import annotations

import os

# Keep Arrow serialization stable on macOS. This must be set before Streamlit imports Arrow.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracksignal import __version__
from tracksignal.analysis import compare_groups, summarize_tracking
from tracksignal.design import TrackingContract, order_labels, validate_tracking_data
from tracksignal.errors import DataProblem, friendly_message
from tracksignal.examples import make_demo_data, make_starter_template
from tracksignal.io import build_evidence_workbook, dataframe_csv_bytes, read_table


COLORS = {
    "ink": "#17322E",
    "deep": "#102C2A",
    "teal": "#173C3A",
    "coral": "#D95B40",
    "mint": "#83D2B4",
    "gold": "#F2C66D",
    "paper": "#F8F5ED",
    "muted": "#59716C",
}
NAME_NOTE = (
    "The TrackSignal name passed an informal availability screen on 17 July 2026: no active company or software "
    "product using the exact name was found. That screen is practical, not legal advice — the name is not legally "
    "cleared and this is not a trademark opinion. See docs/name-screen.md."
)
mark_path = ROOT / "assets" / "tracksignal-mark.svg"
MARK_URI = (
    "data:image/svg+xml;base64," + base64.b64encode(mark_path.read_bytes()).decode("ascii")
    if mark_path.exists()
    else ""
)


st.set_page_config(page_title="TrackSignal | Brand-tracking evidence", page_icon="◉", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --ps-ink:#17322e; --ps-deep:#102c2a; --ps-teal:#173c3a;
        --ps-coral:#d95b40; --ps-mint:#83d2b4; --ps-gold:#f2c66d;
        --ps-paper:#f8f5ed; --ps-line:rgba(23,50,46,.14);
    }
    [data-testid="stAppViewContainer"] {
        background:radial-gradient(circle at 94% 2%,rgba(131,210,180,.17),transparent 28rem),
                   radial-gradient(circle at 3% 93%,rgba(242,198,109,.14),transparent 25rem),
                   linear-gradient(180deg,#fbf9f3 0%,var(--ps-paper) 100%);
    }
    [data-testid="stHeader"] { background:rgba(248,245,237,.78); }
    [data-testid="stSidebar"] { background:linear-gradient(165deg,#173c3a 0%,#102c2a 65%,#0c2422 100%); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span { color:#f8f5ed; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#b9cbc5; }
    [data-testid="stSidebar"] [data-testid="stAlert"] { background:rgba(242,198,109,.12); }
    [data-testid="stSidebar"] button {
        background:rgba(255,255,255,.08); color:#f8f5ed !important; border-color:rgba(255,255,255,.23);
    }
    [data-testid="stSidebar"] button:hover { background:rgba(242,198,109,.14); border-color:rgba(242,198,109,.48); }
    [data-testid="stSidebar"] button * { color:#f8f5ed !important; }
    .block-container { max-width:1240px; padding-top:4.4rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--ps-ink); letter-spacing:-.025em; }
    a { color:#9b3e2b; }
    [data-testid="stMetric"] {
        background:rgba(255,255,255,.75); border:1px solid var(--ps-line); border-radius:16px;
        padding:1rem 1.05rem; box-shadow:0 8px 28px rgba(23,50,46,.045);
    }
    [data-testid="stMetricValue"] { color:var(--ps-ink); font-size:clamp(1.35rem,2.3vw,1.9rem); }
    .stButton > button[kind="primary"] {
        background:linear-gradient(135deg,#e26748,#c94c34); color:white; border:0;
        box-shadow:0 8px 20px rgba(217,91,64,.22); font-weight:750;
    }
    .stButton > button[kind="primary"]:hover { background:linear-gradient(135deg,#c94c34,#b63f2b); color:white; }
    button:focus-visible,a:focus-visible,input:focus-visible,[role="radio"]:focus-visible {
        outline:3px solid #f2c66d !important; outline-offset:2px;
    }
    [data-testid="stExpander"],[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"] { border-radius:14px; }
    .ps-lockup { display:flex; align-items:center; gap:.65rem; }
    .ps-mark { width:38px; height:38px; }
    .ps-name { color:white; font-size:1.28rem; line-height:1; font-weight:850; letter-spacing:-.04em; }
    .ps-name span { color:#f2c66d !important; }
    .ps-tag { margin:.55rem 0 0 !important; color:#b9cbc5 !important; font-size:.77rem; line-height:1.4; }
    .ps-masthead {
        display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.72rem 1rem .72rem .78rem;
        margin-bottom:1.35rem; background:rgba(255,255,255,.65); border:1px solid var(--ps-line);
        border-radius:18px; box-shadow:0 10px 36px rgba(23,50,46,.05);
    }
    .ps-masthead .ps-mark { width:48px; height:48px; }
    .ps-wordmark { color:var(--ps-ink); font-weight:850; letter-spacing:-.045em; font-size:1.55rem; line-height:1; }
    .ps-wordmark span { color:var(--ps-coral); }
    .ps-kicker { margin-top:.32rem; color:#59716c; font-size:.67rem; font-weight:800; letter-spacing:.13em; }
    .ps-promise { color:#47645e; font-size:.78rem; font-weight:700; white-space:nowrap; }
    .ps-promise span { color:var(--ps-coral); padding:0 .3rem; }
    .ps-hero {
        position:relative; overflow:hidden; padding:clamp(1.7rem,4vw,3.4rem); margin-bottom:1.3rem;
        background:linear-gradient(135deg,#173c3a 0%,#102c2a 75%); border-radius:26px;
        box-shadow:0 18px 50px rgba(23,50,46,.17);
    }
    .ps-hero:after {
        content:""; position:absolute; width:330px; height:330px; right:-105px; top:-148px;
        border-radius:50%; border:56px solid rgba(131,210,180,.12);
    }
    .ps-eyebrow { color:#83d2b4; font-size:.72rem; font-weight:850; letter-spacing:.16em; }
    .ps-hero h1 { color:white; font-size:clamp(2.25rem,5vw,4.7rem); line-height:.97; margin:.75rem 0 1rem; max-width:960px; }
    .ps-hero h1 em { color:#f2c66d; font-style:normal; }
    .ps-hero p { color:#d7e3df; font-size:1.06rem; line-height:1.6; max-width:820px; }
    .ps-pills { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.15rem; }
    .ps-pill {
        padding:.4rem .72rem; border:1px solid rgba(255,255,255,.16); border-radius:999px;
        color:#f8f5ed; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.055);
    }
    .ps-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; margin:1.2rem 0 1.5rem; }
    .ps-card {
        height:100%; padding:1.2rem 1.2rem 1rem; background:rgba(255,255,255,.68);
        border:1px solid var(--ps-line); border-radius:18px;
    }
    .ps-card b { color:var(--ps-coral); font-size:.72rem; letter-spacing:.12em; }
    .ps-card h3 { margin:.4rem 0 .5rem; }
    .ps-card p { color:#59716c; font-size:.9rem; line-height:1.55; }
    .pulse-kicker {font-size:.72rem;font-weight:800;letter-spacing:.14em;color:var(--ps-coral);text-transform:uppercase;}
    .pulse-title {font-size:2.15rem;line-height:1.08;font-weight:850;color:var(--ps-ink);margin:.2rem 0 .6rem;}
    .pulse-subtitle {font-size:1.02rem;color:#526a65;max-width:850px;margin-bottom:1.2rem;line-height:1.55;}
    .boundary {border-left:4px solid var(--ps-mint);background:rgba(255,255,255,.62);border-radius:0 14px 14px 0;padding:1rem 1.1rem;color:#47645e;}
    .warning-box {border-left:4px solid var(--ps-gold);background:rgba(242,198,109,.17);border-radius:0 14px 14px 0;padding:1rem 1.1rem;color:#604b1f;}
    .small-note {font-size:.86rem;color:#617670;}
    .ps-footer { margin-top:3.2rem; padding-top:1rem; border-top:1px solid var(--ps-line); color:#617670; font-size:.76rem; text-align:center; }
    .ps-footer span { color:var(--ps-coral); padding:0 .38rem; }
    @media (max-width:1050px) { .ps-grid{grid-template-columns:1fr} }
    @media (max-width:760px) { .ps-promise{display:none}.ps-hero{border-radius:20px}.block-container{padding-top:3.5rem} }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; transition:none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


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
    st.session_state["raw_data"] = frame
    st.session_state["contract"] = contract
    st.session_state["audit"] = audit
    st.session_state.pop("last_contrast", None)


def _ensure_state() -> None:
    if "raw_data" not in st.session_state:
        _validate_and_store(_demo(), STANDARD_CONTRACT)


def show_error(exc: Exception) -> None:
    """Render a useful error while keeping tracebacks opt-in."""
    st.error(friendly_message(exc))
    if not isinstance(exc, (DataProblem, ValueError)) and os.getenv("TRACKSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def masthead() -> None:
    mark = f'<img class="ps-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f"""
        <div class="ps-masthead">
          <div class="ps-lockup">{mark}<div><div class="ps-wordmark">Track<span>Signal</span></div>
          <div class="ps-kicker">TRACK → COMPARE → INTERPRET</div></div></div>
          <div class="ps-promise">Separate measures <span>◆</span> Visible uncertainty <span>◆</span> Local evidence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        f'<div class="ps-footer">TrackSignal v{__version__} <span>◆</span> estimates change, not cause '
        '<span>◆</span> Part of the Signal suite <span>◆</span> AGPL-3.0-or-later</div>',
        unsafe_allow_html=True,
    )


def _header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="pulse-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-subtitle">{subtitle}</div>', unsafe_allow_html=True)


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
    st.markdown(
        """
        <section class="ps-hero">
          <div class="ps-eyebrow">BRAND-TRACKING EVIDENCE</div>
          <h1>Is the brand moving—or is the tracker <em>just noisy?</em></h1>
          <p>Compare noticeability, consideration, choice, loyalty, associations, and relationship measures across
          brands, segments, and waves—without manufacturing a universal brand-equity score.</p>
          <div class="ps-pills"><span class="ps-pill">binary & rating measures</span>
          <span class="ps-pill">wave contrasts</span><span class="ps-pill">brand comparisons</span>
          <span class="ps-pill">segment comparisons</span><span class="ps-pill">paired analysis</span>
          <span class="ps-pill">confidence intervals</span><span class="ps-pill">auditable exports</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="small-note"><strong>Name status:</strong> {NAME_NOTE}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="ps-grid">
          <div class="ps-card"><b>01 · SEPARATE</b><h3>Keep each signal legible</h3><p>Awareness, familiarity,
          consideration, usage, loyalty, association, trust, quality, attachment, and reputation retain their own
          meaning and scale—never ingredients in an opaque score.</p></div>
          <div class="ps-card"><b>02 · COMPARE</b><h3>Show magnitude with uncertainty</h3><p>Wave, brand, and segment
          contrasts report the effect, interval, practical threshold, and multiplicity-adjusted evidence status.</p></div>
          <div class="ps-card"><b>03 · RESPECT</b><h3>Honor the measurement work</h3><p>Construct scores require a
          MeasureSignal or equivalent validation reference. Perceptual maps and multivariate positioning remain in
          PositionSignal.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Workflow")
    st.markdown(
        "1. Validate the long-format tracking contract.\n"
        "2. Inspect the current profile.\n"
        "3. Compare waves.\n"
        "4. Compare brands or segments.\n"
        "5. Export an auditable evidence pack."
    )
    st.markdown(
        '<div class="boundary"><strong>Interpretation boundary:</strong> movement can reflect sampling variation, questionnaire or mode changes, weighting, coverage, seasonality, or real population change. TrackSignal estimates differences; it does not identify why they occurred.</div>',
        unsafe_allow_html=True,
    )


def page_data_contract() -> None:
    _header(
        "Step 1",
        "Data and measurement contract",
        "Declare what each column and metric means before looking at movement. The app uses one row per respondent × wave × segment × brand × metric.",
    )
    top_left, top_right = st.columns([1.15, 1])
    with top_left:
        uploaded = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], key="tracker_upload")
        if uploaded is not None and st.button("Read uploaded file", type="primary"):
            try:
                frame = read_table(uploaded.name, uploaded.getvalue())
                st.session_state["candidate_data"] = frame
                st.success(f"Read {len(frame):,} rows and {len(frame.columns)} columns. Map the roles below.")
            except DataProblem as exc:
                show_error(exc)
    with top_right:
        demo_bytes = dataframe_csv_bytes(_demo())
        st.download_button("Download fictional demo CSV", demo_bytes, "tracksignal-fictional-tracker.csv", "text/csv")
        st.download_button(
            "Download starter template CSV",
            dataframe_csv_bytes(make_starter_template()),
            "tracksignal-starter-template.csv",
            "text/csv",
        )
        if st.button("Restore in-app fictional demo"):
            _validate_and_store(_demo(), STANDARD_CONTRACT)
            st.session_state.pop("candidate_data", None)
            st.success("Fictional demo restored.")

    candidate = st.session_state.get("candidate_data", st.session_state["raw_data"])
    columns = candidate.columns.astype(str).tolist()
    if not columns:
        st.error("The candidate file has no columns.")
        return
    st.markdown("### Column roles")
    row1 = st.columns(3)
    with row1[0]:
        respondent = _required_column("Respondent ID", columns, "respondent_id", "map_respondent")
    with row1[1]:
        wave = _required_column("Survey wave", columns, "wave", "map_wave")
    with row1[2]:
        segment = _optional_column("Segment (optional)", columns, "segment", "map_segment")
    row2 = st.columns(3)
    with row2[0]:
        brand = _required_column("Brand", columns, "brand", "map_brand")
    with row2[1]:
        metric = _required_column("Metric name", columns, "metric", "map_metric")
    with row2[2]:
        value = _required_column("Observed value", columns, "value", "map_value")
    row3 = st.columns(3)
    with row3[0]:
        kind = _required_column("Metric kind", columns, "metric_kind", "map_kind")
    with row3[1]:
        family = _optional_column("Metric family", columns, "family", "map_family")
    with row3[2]:
        weight = _optional_column("Survey weight", columns, "weight", "map_weight")
    row4 = st.columns(2)
    with row4[0]:
        source = _optional_column("Measurement evidence/source", columns, "measurement_source", "map_source")
    with row4[1]:
        threshold = _optional_column("Practical-change threshold", columns, "practical_threshold", "map_threshold")
        st.caption(
            "Without a declared positive threshold, contrasts can only report statistical detection "
            "(“DETECTED — NO PRACTICAL THRESHOLD DECLARED”), never a practically “CLEAR” change."
        )
    if st.button("Validate tracking contract", type="primary"):
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

    audit = st.session_state["audit"]
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
    _header(
        "Step 2",
        "Current brand pulse",
        "Inspect one metric at a time, then use the complete table to see the wider pattern. No across-metric aggregation is performed.",
    )
    audit = st.session_state["audit"]
    cleaned = audit.cleaned
    waves = _ordered(cleaned["wave"])
    segments = _ordered(cleaned["segment"])
    families = _ordered(cleaned["family"])
    selectors = st.columns(3)
    with selectors[0]:
        wave = st.selectbox("Wave", waves, index=len(waves) - 1, key="dashboard_wave")
    with selectors[1]:
        segment = st.selectbox("Segment", segments, key="dashboard_segment")
    with selectors[2]:
        family = st.selectbox("Metric family", families, key="dashboard_family")
    st.caption(
        "Waves are ordered numerically where labels contain numbers (so “Wave 2” precedes “Wave 10”). "
        "Check that the listed order matches your fieldwork order before reading the latest wave."
    )
    scoped = _scope_data(cleaned, wave=wave, segment=segment)
    family_metrics = _ordered(scoped.loc[scoped["family"].eq(family), "metric"])
    if not family_metrics:
        st.info("No metrics exist in this scope.")
        return
    metric = st.selectbox("Metric", family_metrics, key="dashboard_metric")
    summary = summarize_tracking(scoped)
    selected = summary.estimates.loc[summary.estimates["metric"].eq(metric)].sort_values("estimate")
    kind = str(selected["metric_kind"].iloc[0])
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=selected["brand"],
            x=selected["estimate"],
            orientation="h",
            marker_color=COLORS["coral"],
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
        title=f"{metric} · {wave} · {segment}",
        xaxis_title="Proportion" if kind == "binary" else "Mean on original scale",
        yaxis_title="",
        height=max(360, 80 * len(selected)),
        margin={"l": 30, "r": 25, "t": 65, "b": 45},
    )
    if kind == "binary":
        fig.update_xaxes(range=[0, 1], tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
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
    _header(
        "Step 3",
        "Change over time",
        "Contrast two waves within a declared segment. The result separates estimated movement, sampling uncertainty, practical magnitude, and multiplicity control.",
    )
    cleaned = st.session_state["audit"].cleaned
    waves = _ordered(cleaned["wave"])
    if len(waves) < 2:
        st.info("At least two waves are required.")
        return
    segments = _ordered(cleaned["segment"])
    controls = st.columns(3)
    with controls[0]:
        reference = st.selectbox("Reference wave", waves, index=max(0, len(waves) - 2), key="wave_reference")
    with controls[1]:
        comparison = st.selectbox("Comparison wave", waves, index=len(waves) - 1, key="wave_comparison")
    with controls[2]:
        segment = st.selectbox("Segment", segments, key="wave_segment")
    st.caption(
        "Waves are ordered numerically where labels contain numbers (so “Wave 2” precedes “Wave 10”). "
        "Check that the wave order matches your fieldwork order before contrasting."
    )
    panel_ids = st.checkbox(
        "Respondent IDs are stable panel IDs across waves",
        value=False,
        key="wave_panel_ids",
        help=(
            "Tick only when the same people genuinely return with the same ID in both waves. "
            "Paired analysis is then used where IDs overlap, and only matched respondents contribute. "
            "Serial or recycled IDs would otherwise fabricate pairs, so this is off by default."
        ),
    )
    if st.button("Estimate wave changes", type="primary"):
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
            st.session_state["last_contrast"] = result
        except DataProblem as exc:
            show_error(exc)
    result = st.session_state.get("last_contrast")
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
    )
    _warnings(result.warnings)


def page_comparisons() -> None:
    _header(
        "Step 4",
        "Brand and segment comparisons",
        "Compare two brands—within the same respondents when you confirm the IDs identify the same people—or two segments as independent groups. These are descriptive survey contrasts—not positioning maps or causal effects.",
    )
    cleaned = st.session_state["audit"].cleaned
    waves = _ordered(cleaned["wave"])
    segments = _ordered(cleaned["segment"])
    brands = _ordered(cleaned["brand"])
    brand_tab, segment_tab = st.tabs(["Brand contrast", "Segment contrast"])
    with brand_tab:
        controls = st.columns(4)
        with controls[0]:
            wave = st.selectbox("Wave", waves, index=len(waves) - 1, key="brand_wave")
        with controls[1]:
            segment = st.selectbox("Segment", segments, key="brand_segment")
        with controls[2]:
            reference_brand = st.selectbox("Reference brand", brands, key="brand_reference")
        comparison_options = [brand for brand in brands if brand != reference_brand]
        with controls[3]:
            comparison_brand = st.selectbox("Comparison brand", comparison_options, key="brand_comparison")
        same_respondents = st.checkbox(
            "Respondent IDs identify the same people for both brands in this wave",
            value=False,
            key="brand_paired_ids",
            help=(
                "Tick only when each respondent rated both brands (not a monadic design with separate samples "
                "per brand). Paired within-respondent analysis is then used where IDs overlap; unmatched "
                "respondents are dropped from paired rows and reported."
            ),
        )
        if st.button("Estimate brand contrast", type="primary"):
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
                st.session_state["brand_contrast"] = result
                st.session_state["last_contrast"] = result
            except DataProblem as exc:
                show_error(exc)
        brand_result = st.session_state.get("brand_contrast")
        if brand_result is not None:
            st.dataframe(_contrast_table(brand_result.contrasts), width="stretch", hide_index=True)
            _warnings(brand_result.warnings)
    with segment_tab:
        if len(segments) < 2:
            st.info("At least two segments are required.")
        else:
            controls = st.columns(4)
            with controls[0]:
                wave = st.selectbox("Wave", waves, index=len(waves) - 1, key="segment_wave")
            with controls[1]:
                brand = st.selectbox("Brand", brands, key="segment_brand")
            with controls[2]:
                reference_segment = st.selectbox("Reference segment", segments, key="segment_reference")
            comparison_options = [segment for segment in segments if segment != reference_segment]
            with controls[3]:
                comparison_segment = st.selectbox("Comparison segment", comparison_options, key="segment_comparison")
            if st.button("Estimate segment contrast", type="primary"):
                try:
                    scoped = _scope_data(cleaned, wave=wave, brand=brand)
                    result = compare_groups(
                        scoped,
                        dimension="segment",
                        reference=reference_segment,
                        comparison=comparison_segment,
                        by=("metric",),
                    )
                    st.session_state["segment_contrast"] = result
                    st.session_state["last_contrast"] = result
                except DataProblem as exc:
                    show_error(exc)
            segment_result = st.session_state.get("segment_contrast")
            if segment_result is not None:
                st.dataframe(_contrast_table(segment_result.contrasts), width="stretch", hide_index=True)
                _warnings(segment_result.warnings)


def page_evidence_pack() -> None:
    _header(
        "Step 5",
        "Evidence pack",
        "Export the declared metric registry, cell audit, all tracking estimates, and the most recently displayed contrast so another analyst can inspect the work.",
    )
    audit = st.session_state["audit"]
    summary = summarize_tracking(audit.cleaned)
    latest = st.session_state.get("last_contrast")
    contrast_frame = latest.contrasts if latest is not None else None
    metadata = {
        "app": "TrackSignal",
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
        "Download TrackSignal evidence pack",
        workbook,
        "tracksignal-evidence-pack.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.markdown("### Included")
    st.write("- Release and interpretation metadata\n- Metric registry and measurement provenance\n- Cell sizes and effective sample sizes\n- Separate estimates with confidence intervals\n- Latest wave, brand, or segment contrast, when one has been run")
    st.info("The workbook intentionally excludes a universal brand-equity score and does not turn descriptive movement into a causal story.")


def page_methods() -> None:
    _header(
        "Methods and boundaries",
        "What TrackSignal calculates",
        "The app is deliberately narrower than a general survey package: it handles repeated brand-tracking estimates and transparent pairwise contrasts.",
    )
    st.markdown("### Estimates")
    st.write("Binary metrics use Wilson score intervals. Weighted binary metrics use a clearly labelled Kish effective-sample-size approximation. Ratings and externally validated construct scores use t intervals on their original scales.")
    st.markdown("### Comparisons")
    st.write("Independent unweighted binary contrasts use a Newcombe–Wilson difference interval with a matching unpooled z test. Continuous contrasts use Welch intervals. Paired analysis is used only when you explicitly confirm that respondent IDs identify the same people in both groups and the IDs overlap; overlapping IDs alone never trigger pairing, and paired rows report how many pairs were used and how many respondents were dropped from each group. For unweighted paired binary data the p-value comes from the exact McNemar test while the interval uses a paired-difference approximation; the method column labels this hybrid. Benjamini–Hochberg q-values control false-discovery rate within the displayed contrast family.")
    st.markdown("### Decision language")
    st.write("A change is labelled clear only when its interval excludes zero, its BH q-value is at most 0.05, and its absolute size reaches the declared positive practical threshold. When no practical threshold is declared (or the declared value is zero), the app cannot judge business relevance: a detected change is labelled “DETECTED — NO PRACTICAL THRESHOLD DECLARED” instead of “CLEAR”. The full estimate and interval remain primary; the label is an audit aid, not a verdict.")
    st.markdown("### Product boundaries")
    st.write("- Multi-item item-level validation belongs in MeasureSignal. TrackSignal accepts only the resulting documented score.\n- TrackSignal may track a prespecified attribute-ownership item over time. Perceptual maps, association geometry, and POP/POD mapping remain in PositionSignal.\n- Driver models belong in DriverSignal. Experiments belong in ExperimentSignal. Text-derived metrics belong in TextSignal.\n- Complex survey designs require specialist variance estimation; this release does not model strata, clusters, finite-population corrections, or replicate weights.\n- The app estimates population differences under a sampling model. It does not identify causes.")
    st.markdown("### Sources")
    st.write("The implementation is independently written from public statistical and brand-measurement literature. Full references and originality notes are bundled in the repository documentation.")


_ensure_state()

with st.sidebar:
    mark = f'<img class="ps-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f'<div class="ps-lockup">{mark}<div class="ps-name">Track<span>Signal</span></div></div>'
        '<p class="ps-tag">Brand movement without the magic equity score.</p>',
        unsafe_allow_html=True,
    )
    st.caption(f"Brand-tracking evidence · v{__version__}")
    page = st.radio(
        "Workflow",
        [
            "Welcome",
            "1 · Data & contract",
            "2 · Current pulse",
            "3 · Change over time",
            "4 · Brand & segment compare",
            "5 · Evidence pack",
            "Methods & boundaries",
        ],
    )
    st.markdown("---")
    audit = st.session_state["audit"]
    st.caption(
        f"Validated: {audit.summary['waves']} waves · {audit.summary['brands']} brands · "
        f"{audit.summary['metrics']} separate metrics"
    )
    st.caption(
        "Name status: informally screened (17 July 2026); not legally cleared and not a trademark opinion."
    )
    st.caption("Local mode · no telemetry · no external AI calls · uploads stay in this Python process")

PAGES = {
    "Welcome": page_welcome,
    "1 · Data & contract": page_data_contract,
    "2 · Current pulse": page_dashboard,
    "3 · Change over time": page_wave_change,
    "4 · Brand & segment compare": page_comparisons,
    "5 · Evidence pack": page_evidence_pack,
    "Methods & boundaries": page_methods,
}
masthead()
try:
    PAGES[page]()
except Exception as exc:
    show_error(exc)
footer()
