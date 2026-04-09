"""Server-rendered UI primitives for the Phase 3B shell."""

from __future__ import annotations

from html import escape

from ircp_contracts import PreflightReport

from .models import (
    DeviceSummaryCard,
    EventLogItem,
    HeaderStatus,
    LiveDataSeries,
    ResultsPageModel,
    RunPageModel,
    RunStepSummary,
    ServicePageModel,
    SessionSummaryCard,
    SetupPageModel,
    StatusBadge,
    SummaryPanel,
)
from .page_state import PageStateModel


APP_CSS = """
body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background: linear-gradient(180deg, #f3f4ee 0%, #fbfaf6 100%);
  color: #1f231f;
}
a { color: #164e63; text-decoration: none; }
main { max-width: 1120px; margin: 0 auto; padding: 24px; }
.shell-header {
  background: linear-gradient(135deg, #19323c 0%, #28536b 100%);
  color: #f7fafc;
  padding: 24px;
}
.shell-header h1 { margin: 0 0 10px; font-size: 2rem; }
.nav-row, .scenario-row, .badge-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.nav-link, .scenario-chip, .badge-pill, .button-link {
  border-radius: 999px;
  padding: 8px 14px;
  border: 1px solid rgba(255,255,255,0.25);
}
.nav-link.active, .scenario-chip.active {
  background: rgba(255,255,255,0.18);
}
.scenario-chip { color: #f7fafc; }
.badge-pill {
  background: rgba(255,255,255,0.12);
  font-size: 0.92rem;
}
.badge-pill.good { border-color: #88c0a8; }
.badge-pill.warn { border-color: #f2c36b; }
.badge-pill.bad { border-color: #ec8b8b; }
.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin: 18px 0 24px;
}
.panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #d8d8cf;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 8px 18px rgba(17, 24, 39, 0.05);
}
.panel h2, .panel h3 { margin-top: 0; }
.panel-subtitle {
  color: #4b5563;
  margin-top: -6px;
  margin-bottom: 14px;
}
.state-box {
  border-radius: 14px;
  padding: 14px 16px;
  margin: 0 0 18px;
  border: 1px solid #d8d8cf;
}
.state-box.blocked { background: #fff7e8; border-color: #f2c36b; }
.state-box.warning { background: #fff7e8; border-color: #f2c36b; }
.state-box.fault { background: #fff1f1; border-color: #e98989; }
.state-box.empty { background: #f8f8f4; }
.state-box.unavailable, .state-box.recovery { background: #eef5f7; border-color: #8eb8c7; }
.device-card, .session-card, .timeline-step, .readiness-row, .event-row, .summary-row {
  padding: 10px 0;
  border-top: 1px solid #ecebe4;
}
.device-card:first-child, .session-card:first-child, .timeline-step:first-child,
.readiness-row:first-child, .event-row:first-child, .summary-row:first-child {
  border-top: none;
  padding-top: 0;
}
.status-label {
  display: inline-block;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.82rem;
  background: #edf2f7;
}
.status-label.good { background: #d9f2dd; }
.status-label.warn { background: #fff4d8; }
.status-label.bad { background: #ffe2e2; }
.status-label.neutral { background: #edf2f7; }
.panel-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}
form { margin: 0; }
button, .button-link {
  background: #0f766e;
  color: white;
  border: none;
  cursor: pointer;
  padding: 10px 14px;
  border-radius: 12px;
  font: inherit;
}
button.secondary, .button-link.secondary {
  background: #475569;
}
button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th, .data-table td {
  padding: 8px;
  border-top: 1px solid #ecebe4;
  text-align: left;
}
.data-table th { border-top: none; font-size: 0.9rem; color: #4b5563; }
.small { color: #6b7280; font-size: 0.92rem; }
"""


def render_layout(header: HeaderStatus, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(header.title)}</title>
    <style>{APP_CSS}</style>
  </head>
  <body>
    {render_header(header)}
    <main>{body}</main>
  </body>
</html>"""


def render_header(header: HeaderStatus) -> str:
    scenarios = "".join(
        (
            f'<a class="scenario-chip{" active" if option.active else ""}" '
            f'href="/setup?scenario={escape(option.scenario_id)}">{escape(option.label)}</a>'
        )
        for option in header.scenario_options
    )
    navigation = "".join(
        (
            f'<a class="nav-link{" active" if item.active else ""}" href="{escape(item.href)}">'
            f"{escape(item.label)}</a>"
        )
        for item in header.navigation
    )
    badges = "".join(render_badge(badge) for badge in header.badges)
    return f"""
    <header class="shell-header">
      <h1>{escape(header.title)}</h1>
      <div>{escape(header.summary)}</div>
      <div class="scenario-row">{scenarios}</div>
      <div class="nav-row">{navigation}</div>
      <div class="badge-row">{badges}</div>
    </header>"""


def render_badge(badge: StatusBadge) -> str:
    return f'<span class="badge-pill {escape(badge.tone)}">{escape(badge.label)}</span>'


def render_page_state(state: PageStateModel | None) -> str:
    if state is None:
        return ""
    detail_lines = "".join(f"<li>{escape(detail)}</li>" for detail in state.details)
    details = f"<ul>{detail_lines}</ul>" if detail_lines else ""
    return (
        f'<section class="state-box {escape(state.kind.value)}">'
        f"<strong>{escape(state.title)}</strong><div>{escape(state.message)}</div>{details}</section>"
    )


def render_setup_page(page: SetupPageModel, scenario_id: str) -> str:
    cards = "".join(render_device_card(card) for card in page.device_cards)
    readiness = "".join(render_readiness_row(row) for row in page.readiness_rows)
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels)
    preflight = render_preflight_report(page.preflight_report)
    return f"""
    <section class="panel">
      <h2>{escape(page.title)}</h2>
      <p class="panel-subtitle">{escape(page.subtitle)}</p>
      {render_page_state(page.state)}
      <div class="small">Recipe: {escape(page.recipe_title)} | Preset: {escape(page.preset_name)}</div>
      <div class="panel-actions">
        <form method="post" action="/setup/preflight">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <button type="submit">Run Preflight</button>
        </form>
        <a class="button-link secondary" href="/run?scenario={escape(scenario_id)}">Open Run Scaffold</a>
      </div>
    </section>
    <section class="section-grid">{summaries}</section>
    <section class="section-grid">
      <div class="panel">
        <h3>{escape(page.section_header.title)}</h3>
        <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
        {cards}
      </div>
      <div class="panel">
        <h3>Readiness</h3>
        <p class="panel-subtitle">Explicit pass, warning, and block states for Setup.</p>
        {readiness}
      </div>
    </section>
    <section class="panel">
      <h3>Preflight Summary</h3>
      <p class="panel-subtitle">Canonical preflight output from the engine boundary.</p>
      {preflight}
    </section>"""


def render_run_page(page: RunPageModel, scenario_id: str) -> str:
    actions = f"""
    <div class="panel-actions">
      <form method="post" action="/run/start">
        <input type="hidden" name="scenario" value="{escape(scenario_id)}">
        <button type="submit">Start Supported V1 Run</button>
      </form>
      <form method="post" action="/run/abort">
        <input type="hidden" name="scenario" value="{escape(scenario_id)}">
        <button type="submit" class="secondary" {"disabled" if page.run_id is None else ""}>Abort</button>
      </form>
    </div>"""
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels)
    primary_live_data = "".join(render_live_data_series(series) for series in page.primary_live_data) or (
        '<div class="small">No primary HF2 data has been produced for this scenario yet.</div>'
    )
    secondary_live_data = "".join(render_live_data_series(series) for series in page.secondary_live_data) or (
        '<div class="small">No secondary Pico monitor data is present for this scenario.</div>'
    )
    steps = "".join(render_run_step(step) for step in page.run_steps) or (
        '<div class="small">No run has been started yet.</div>'
    )
    events = "".join(render_event_row(item) for item in page.event_log) or (
        '<div class="small">The event timeline is empty until the run boundary emits events.</div>'
    )
    return f"""
    <section class="panel">
      <h2>{escape(page.title)}</h2>
      <p class="panel-subtitle">{escape(page.subtitle)}</p>
      {render_page_state(page.state)}
      <div class="small">Run ID: {escape(page.run_id or 'not started')} | Session ID: {escape(page.session_id or 'none')}</div>
      <div class="small">Current phase: {escape(page.run_phase_label)}</div>
      {actions}
    </section>
    <section class="section-grid">{summaries}</section>
    <section class="section-grid">
      <div class="panel">
        <h3>{escape(page.section_header.title)}</h3>
        <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
        {steps}
      </div>
      <div class="panel">
        <h3>Primary HF2 Live Data</h3>
        <p class="panel-subtitle">HF2 remains the primary scientific raw-data authority.</p>
        {primary_live_data}
      </div>
      <div class="panel">
        <h3>Pico Monitor Shell</h3>
        <p class="panel-subtitle">Secondary monitor traces only. They never redefine raw-data authority.</p>
        {secondary_live_data}
      </div>
    </section>
    <section class="panel">
      <h3>Event Timeline</h3>
      <p class="panel-subtitle">Structured run events emitted through the canonical path.</p>
      {events}
    </section>"""


def render_results_page(page: ResultsPageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id) for card in page.sessions) or (
        '<div class="small">No saved sessions are available for this scenario.</div>'
    )
    details = "".join(render_summary_panel(panel) for panel in page.detail_panels) or (
        '<div class="small">Select a session to inspect the persisted manifest summary.</div>'
    )
    return f"""
    <section class="panel">
      <h2>{escape(page.title)}</h2>
      <p class="panel-subtitle">{escape(page.subtitle)}</p>
      {render_page_state(page.state)}
    </section>
    <section class="section-grid">
      <div class="panel">
        <h3>{escape(page.section_header.title)}</h3>
        <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
        {sessions}
      </div>
      <div class="panel">
        <h3>Selected Session</h3>
        <p class="panel-subtitle">Reopen happens through the session and replay boundaries only.</p>
        {details}
      </div>
    </section>"""


def render_service_page(page: ServicePageModel) -> str:
    cards = "".join(render_device_card(card) for card in page.device_cards)
    notes = "".join(f"<li>{escape(note)}</li>" for note in page.notes)
    diagnostics = "".join(render_summary_panel(panel) for panel in page.diagnostic_panels)
    return f"""
    <section class="panel">
      <h2>{escape(page.title)}</h2>
      <p class="panel-subtitle">{escape(page.subtitle)}</p>
      {render_page_state(page.state)}
    </section>
    <section class="section-grid">
      <div class="panel">
        <h3>{escape(page.section_header.title)}</h3>
        <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
        {cards}
      </div>
      <div class="panel">
        <h3>Service Limits</h3>
        <p class="panel-subtitle">Service remains scaffold-only in this milestone.</p>
        <ul>{notes}</ul>
      </div>
    </section>
    <section class="section-grid">{diagnostics}</section>"""


def render_summary_panel(panel: SummaryPanel) -> str:
    rows = "".join(f'<div class="summary-row">{escape(item)}</div>' for item in panel.items) or (
        '<div class="summary-row small">No details available.</div>'
    )
    return f"""
    <div class="panel">
      <h3>{escape(panel.title)}</h3>
      <p class="panel-subtitle">{escape(panel.subtitle)}</p>
      {rows}
    </div>"""


def render_device_card(card: DeviceSummaryCard) -> str:
    details = "".join(f"<li>{escape(detail)}</li>" for detail in card.details)
    return f"""
    <div class="device-card">
      <strong>{escape(card.device_label)}</strong>
      <div><span class="status-label {escape(card.tone)}">{escape(card.status_label)}</span></div>
      <div>{escape(card.summary)}</div>
      {'<ul>' + details + '</ul>' if details else ''}
    </div>"""


def render_readiness_row(row) -> str:
    tone = {
        "pass": "good",
        "warn": "warn",
        "block": "bad",
    }.get(row.state, "neutral")
    details = "".join(f"<li>{escape(detail)}</li>" for detail in row.details)
    return f"""
    <div class="readiness-row">
      <strong>{escape(row.label)}</strong>
      <div><span class="status-label {tone}">{escape(row.state.upper())}</span></div>
      <div>{escape(row.summary)}</div>
      {'<ul>' + details + '</ul>' if details else ''}
    </div>"""


def render_preflight_report(report: PreflightReport | None) -> str:
    if report is None:
        return '<div class="small">Preflight has not been requested yet.</div>'
    rows = []
    for check in report.checks:
        issues = "; ".join(issue.message for issue in check.issues) if check.issues else "No issues."
        rows.append(
            "<tr>"
            f"<td>{escape(check.target)}</td>"
            f"<td>{escape(check.state.value)}</td>"
            f"<td>{escape(check.summary)}</td>"
            f"<td>{escape(issues)}</td>"
            "</tr>"
        )
    readiness = "ready" if report.ready_to_start else "blocked"
    return (
        f'<div class="small">Generated {escape(report.generated_at.isoformat())} | Overall: {readiness}</div>'
        '<table class="data-table"><thead><tr><th>Target</th><th>State</th><th>Summary</th><th>Issues</th>'
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_event_row(item: EventLogItem) -> str:
    return f"""
    <div class="event-row">
      <strong>{escape(item.source)}</strong>
      <div class="small">{escape(item.timestamp.isoformat())}</div>
      <div>{escape(item.message)}</div>
    </div>"""


def render_live_data_series(series: LiveDataSeries) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{point.axis_value:.1f}</td>"
        f"<td>{point.value:.3f}</td>"
        "</tr>"
        for point in series.points
    )
    return (
        f'<div class="panel-subtitle">{escape(series.label)} | {escape(series.role_label)}</div>'
        '<table class="data-table"><thead><tr>'
        f"<th>{escape(series.axis_label)} ({escape(series.axis_units)})</th>"
        f"<th>Value ({escape(series.units)})</th>"
        "</tr></thead><tbody>"
        + rows
        + "</tbody></table>"
    )


def render_run_step(step: RunStepSummary) -> str:
    return f"""
    <div class="timeline-step">
      <strong>{escape(step.phase_label)}</strong>
      <div><span class="status-label {escape(step.tone)}">{step.progress_fraction:.0%}</span></div>
      <div>{escape(step.active_step)}</div>
      <div class="small">{escape(step.summary)}</div>
    </div>"""


def render_session_card(card: SessionSummaryCard, scenario_id: str) -> str:
    selected = " active" if card.selected else ""
    return f"""
    <div class="session-card">
      <strong>{escape(card.recipe_title)}</strong>
      <div><span class="status-label{' good' if card.status_label == 'Completed' else 'neutral'}">{escape(card.status_label)}</span></div>
      <div class="small">Session {escape(card.session_id)} updated {escape(card.updated_at.isoformat())}</div>
      <div class="small">Primary raw {card.primary_raw_artifact_count} | Secondary monitor {card.secondary_monitor_artifact_count}</div>
      <div class="small">Processed {card.processed_artifact_count} | Analysis {card.analysis_artifact_count} | Export {card.export_artifact_count}</div>
      <div class="panel-actions">
        <form method="post" action="/results/reopen">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <input type="hidden" name="session_id" value="{escape(card.session_id)}">
          <button type="submit" class="secondary{selected}">Reopen Session</button>
        </form>
      </div>
    </div>"""
