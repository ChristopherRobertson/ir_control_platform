"""Server-rendered UI primitives for the workflow-first shell."""

from __future__ import annotations

from html import escape

from ircp_contracts import PreflightReport

from .models import (
    AnalyzePageModel,
    CalloutModel,
    DeviceSummaryCard,
    EventLogItem,
    FormFieldModel,
    FormSectionModel,
    HeaderStatus,
    LiveDataSeries,
    NavigationItem,
    ResultsPageModel,
    RunPageModel,
    RunStepSummary,
    ServicePageModel,
    SessionSummaryCard,
    SetupPageModel,
    StatusBadge,
    SummaryPanel,
    TableModel,
)
from .page_state import PageStateModel


APP_CSS = """
:root {
  --bg-top: #f4efe3;
  --bg-bottom: #e7ece8;
  --surface: rgba(255, 255, 255, 0.9);
  --surface-strong: rgba(255, 255, 255, 0.96);
  --border: #d6d0c1;
  --ink: #1d2328;
  --muted: #55606d;
  --accent: #0f766e;
  --accent-strong: #115e59;
  --secondary: #8b5e34;
  --good-bg: #ddf4e6;
  --good-border: #6a9f7a;
  --warn-bg: #fff4d6;
  --warn-border: #d1a54d;
  --bad-bg: #ffe4df;
  --bad-border: #d66855;
  --info-bg: #e5f0f6;
  --info-border: #6f93ac;
  --shadow: 0 12px 30px rgba(24, 37, 51, 0.08);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 32%),
    radial-gradient(circle at top right, rgba(139, 94, 52, 0.12), transparent 28%),
    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
  color: var(--ink);
}

a { color: #0f4c5c; text-decoration: none; }
a:hover { text-decoration: underline; }

main {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 24px 44px;
}

.shell-header {
  background:
    linear-gradient(135deg, rgba(20, 34, 46, 0.98) 0%, rgba(16, 74, 82, 0.94) 58%, rgba(90, 61, 42, 0.94) 100%);
  color: #f8fbfc;
  padding: 28px 24px 30px;
  box-shadow: var(--shadow);
}

.shell-header h1 {
  margin: 0 0 12px;
  font-size: 2rem;
  letter-spacing: -0.03em;
}

.nav-row, .scenario-row, .badge-row, .surface-nav, .surface-badges, .panel-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.scenario-row, .nav-row, .badge-row { margin-top: 12px; }

.nav-link, .scenario-chip, .badge-pill, .surface-link, .button-link {
  border-radius: 999px;
  padding: 8px 14px;
  border: 1px solid rgba(255, 255, 255, 0.22);
}

.nav-link, .scenario-chip {
  color: #f8fbfc;
  background: rgba(255, 255, 255, 0.06);
}

.nav-link.active, .scenario-chip.active {
  background: rgba(255, 255, 255, 0.2);
}

.badge-pill {
  background: rgba(255, 255, 255, 0.12);
  font-size: 0.92rem;
}

.badge-pill.good { border-color: #88c39a; }
.badge-pill.warn { border-color: #e8bf70; }
.badge-pill.bad { border-color: #eb8d84; }
.badge-pill.info, .badge-pill.neutral { border-color: #9bb8c6; }

.page-topbar {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}

.surface-link {
  color: var(--ink);
  border-color: var(--border);
  background: rgba(255, 255, 255, 0.55);
}

.surface-link.active {
  background: rgba(15, 118, 110, 0.12);
  border-color: rgba(15, 118, 110, 0.4);
  color: var(--accent-strong);
}

.page-stack {
  display: grid;
  gap: 18px;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px;
  box-shadow: var(--shadow);
}

.panel.hero {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.97) 0%, rgba(245, 248, 247, 0.95) 100%);
}

.panel h2, .panel h3, .panel h4 { margin-top: 0; }

.panel-subtitle {
  color: var(--muted);
  margin-top: -6px;
  margin-bottom: 14px;
}

.small { color: #66717c; font-size: 0.92rem; }

.state-box, .callout {
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px solid var(--border);
}

.state-box { margin-bottom: 16px; }
.state-box.blocked, .callout.warn { background: var(--warn-bg); border-color: var(--warn-border); }
.state-box.warning { background: var(--warn-bg); border-color: var(--warn-border); }
.state-box.fault, .callout.bad { background: var(--bad-bg); border-color: var(--bad-border); }
.state-box.empty, .callout.neutral { background: #f5f4ef; }
.state-box.unavailable, .state-box.recovery, .callout.info, .callout.good {
  background: var(--info-bg);
  border-color: var(--info-border);
}
.callout.good { background: var(--good-bg); border-color: var(--good-border); }

.callout-stack {
  display: grid;
  gap: 12px;
}

.summary-row, .device-card, .session-card, .timeline-step, .readiness-row, .event-row, .table-note {
  padding: 10px 0;
  border-top: 1px solid #ebe7db;
}

.summary-row:first-child,
.device-card:first-child,
.session-card:first-child,
.timeline-step:first-child,
.readiness-row:first-child,
.event-row:first-child,
.table-note:first-child {
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

form { margin: 0; }

button, .button-link {
  background: var(--accent);
  color: white;
  border: none;
  cursor: pointer;
  padding: 10px 14px;
  border-radius: 12px;
  font: inherit;
  text-decoration: none;
}

button.secondary, .button-link.secondary {
  background: #475569;
}

button.ghost, .button-link.ghost {
  background: #b45309;
}

button:disabled, .button-link.disabled {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label {
  font-weight: 600;
  color: #24303a;
}

.field input,
.field select,
.field textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid #c8d2d0;
  padding: 10px 12px;
  font: inherit;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.92);
}

.field textarea { min-height: 88px; resize: vertical; }

.field input:disabled,
.field select:disabled,
.field textarea:disabled {
  color: var(--ink);
  opacity: 1;
  background: rgba(245, 248, 247, 0.9);
}

.field-help {
  color: var(--muted);
  font-size: 0.88rem;
}

.field.checkbox-field {
  grid-template-columns: auto 1fr;
  align-items: start;
  gap: 10px;
}

.field.checkbox-field label {
  margin-top: 2px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: 8px;
  border-top: 1px solid #ebe7db;
  text-align: left;
  vertical-align: top;
}

.data-table th {
  border-top: none;
  color: var(--muted);
  font-size: 0.9rem;
}

.notes-list, .detail-list { margin: 8px 0 0 18px; padding: 0; }

.detail-list li, .notes-list li { margin-top: 6px; }

.placeholder-copy {
  color: #6c6f74;
  font-style: italic;
}

details {
  border-top: 1px dashed #d4d0c4;
  margin-top: 12px;
  padding-top: 10px;
}

details summary {
  cursor: pointer;
  font-weight: 600;
  color: #32414d;
}

@media (max-width: 720px) {
  main { padding: 20px 16px 36px; }
  .shell-header { padding: 22px 16px 24px; }
  .shell-header h1 { font-size: 1.7rem; }
}
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


def render_page_topbar(
    surface_navigation: tuple[NavigationItem, ...] = (),
    surface_badges: tuple[StatusBadge, ...] = (),
) -> str:
    parts: list[str] = []
    if surface_navigation:
        parts.append(
            '<div class="surface-nav">'
            + "".join(
                f'<a class="surface-link{" active" if item.active else ""}" href="{escape(item.href)}">'
                f"{escape(item.label)}</a>"
                for item in surface_navigation
            )
            + "</div>"
        )
    if surface_badges:
        parts.append(
            '<div class="surface-badges">'
            + "".join(render_badge(badge) for badge in surface_badges)
            + "</div>"
        )
    if not parts:
        return ""
    return '<div class="page-topbar">' + "".join(parts) + "</div>"


def render_page_state(state: PageStateModel | None) -> str:
    if state is None:
        return ""
    detail_lines = "".join(f"<li>{escape(detail)}</li>" for detail in state.details)
    details = f'<ul class="detail-list">{detail_lines}</ul>' if detail_lines else ""
    return (
        f'<section class="state-box {escape(state.kind.value)}">'
        f"<strong>{escape(state.title)}</strong><div>{escape(state.message)}</div>{details}</section>"
    )


def render_callouts(callouts: tuple[CalloutModel, ...]) -> str:
    if not callouts:
        return ""
    return '<section class="callout-stack">' + "".join(render_callout(callout) for callout in callouts) + "</section>"


def render_callout(callout: CalloutModel) -> str:
    items = "".join(f"<li>{escape(item)}</li>" for item in callout.items)
    details = f'<ul class="detail-list">{items}</ul>' if items else ""
    return (
        f'<div class="callout {escape(callout.tone)}">'
        f"<strong>{escape(callout.title)}</strong>"
        f"<div>{escape(callout.body)}</div>"
        f"{details}"
        "</div>"
    )


def render_setup_page(page: SetupPageModel, scenario_id: str, surface: str) -> str:
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels)
    forms = "".join(render_form_section(section) for section in page.form_sections)
    cards = "".join(render_device_card(card) for card in page.device_cards)
    readiness = "".join(render_readiness_row(row) for row in page.readiness_rows)
    tables = "".join(render_table_section(table) for table in page.tables)
    preflight = render_preflight_report(page.preflight_report)
    return f"""
    <div class="page-stack">
      {render_page_topbar(page.surface_navigation, page.surface_badges)}
      <section class="panel hero">
        <h2>{escape(page.title)}</h2>
        <p class="panel-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
        <div class="small">Recipe: {escape(page.recipe_title)} | Preset: {escape(page.preset_name)}</div>
        <div class="panel-actions">
          <form method="post" action="/setup/preflight">
            <input type="hidden" name="scenario" value="{escape(scenario_id)}">
            <input type="hidden" name="surface" value="{escape(surface)}">
            <button type="submit">Run Preflight</button>
          </form>
          <a class="button-link secondary" href="/run?scenario={escape(scenario_id)}">Continue to Run</a>
          <a class="button-link ghost" href="/results?scenario={escape(scenario_id)}">Inspect Results</a>
        </div>
      </section>
      {render_callouts(page.callouts)}
      <section class="section-grid">{summaries}</section>
      <section class="section-grid">{forms}</section>
      <section class="section-grid">
        <div class="panel">
          <h3>{escape(page.section_header.title)}</h3>
          <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
          {cards or '<div class="placeholder-copy">No device cards for this surface.</div>'}
        </div>
        <div class="panel">
          <h3>Readiness</h3>
          <p class="panel-subtitle">Explicit pass, warning, and blocked states for the visible workflow.</p>
          {readiness or '<div class="placeholder-copy">No readiness checks are shown on this surface.</div>'}
        </div>
      </section>
      {tables}
      <section class="panel">
        <h3>Preflight Summary</h3>
        <p class="panel-subtitle">Canonical preflight output from the engine boundary.</p>
        {preflight}
      </section>
    </div>"""


def render_run_page(page: RunPageModel, scenario_id: str) -> str:
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels)
    tables = "".join(render_table_section(table) for table in page.tables)
    primary_live_data = "".join(render_live_data_series(series) for series in page.primary_live_data) or (
        '<div class="placeholder-copy">No primary HF2 data has been produced for this scenario yet.</div>'
    )
    secondary_live_data = "".join(render_live_data_series(series) for series in page.secondary_live_data) or (
        '<div class="placeholder-copy">No secondary Pico monitor data is present for this scenario.</div>'
    )
    steps = "".join(render_run_step(step) for step in page.run_steps) or (
        '<div class="placeholder-copy">No run has been started yet.</div>'
    )
    events = "".join(render_event_row(item) for item in page.event_log) or (
        '<div class="placeholder-copy">The event timeline is empty until the run boundary emits events.</div>'
    )
    results_link = (
        f'<a class="button-link ghost" href="/results?scenario={escape(scenario_id)}&session_id={escape(page.session_id)}">'
        "Open Selected Result"
        "</a>"
        if page.session_id
        else ""
    )
    return f"""
    <div class="page-stack">
      {render_page_topbar(surface_badges=page.surface_badges)}
      <section class="panel hero">
        <h2>{escape(page.title)}</h2>
        <p class="panel-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
        <div class="small">Run ID: {escape(page.run_id or 'not started')} | Session ID: {escape(page.session_id or 'none')}</div>
        <div class="small">Current phase: {escape(page.run_phase_label)}</div>
        <div class="panel-actions">
          <form method="post" action="/run/start">
            <input type="hidden" name="scenario" value="{escape(scenario_id)}">
            <button type="submit">Start Run</button>
          </form>
          <form method="post" action="/run/abort">
            <input type="hidden" name="scenario" value="{escape(scenario_id)}">
            <button type="submit" class="secondary" {"disabled" if page.run_id is None else ""}>Abort</button>
          </form>
          {results_link}
        </div>
      </section>
      {render_callouts(page.callouts)}
      <section class="section-grid">{summaries}</section>
      {tables}
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
          <h3>Pico Monitor Context</h3>
          <p class="panel-subtitle">Secondary monitor traces are visible without taking ownership from HF2.</p>
          {secondary_live_data}
        </div>
      </section>
      <section class="panel">
        <h3>Event Timeline</h3>
        <p class="panel-subtitle">Structured run events emitted through the canonical path.</p>
        {events}
      </section>
    </div>"""


def render_results_page(page: ResultsPageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id) for card in page.sessions) or (
        '<div class="placeholder-copy">No saved sessions are available for this scenario.</div>'
    )
    details = "".join(render_summary_panel(panel) for panel in page.detail_panels) or (
        '<div class="placeholder-copy">Select a session to inspect the persisted manifest summary.</div>'
    )
    artifacts = "".join(render_summary_panel(panel) for panel in page.artifact_panels) or (
        '<div class="placeholder-copy">Persisted artifact groups will appear once a session is selected.</div>'
    )
    tables = "".join(render_table_section(table) for table in page.tables)
    events = "".join(render_event_row(item) for item in page.event_log) or (
        '<div class="placeholder-copy">The persisted session timeline is empty for this selection.</div>'
    )
    return f"""
    <div class="page-stack">
      {render_page_topbar(surface_badges=page.surface_badges)}
      <section class="panel hero">
        <h2>{escape(page.title)}</h2>
        <p class="panel-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="section-grid">
        <div class="panel">
          <h3>{escape(page.section_header.title)}</h3>
          <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
          {sessions}
        </div>
        <div class="panel">
          <h3>Selected Session</h3>
          <p class="panel-subtitle">Results reads the saved session and artifact graph rather than live widget state.</p>
          {details}
        </div>
      </section>
      {tables}
      <section class="section-grid">{artifacts}</section>
      <section class="panel">
        <h3>Persisted Event Timeline</h3>
        <p class="panel-subtitle">Results reads saved run events instead of relying on live runtime state.</p>
        {events}
      </section>
    </div>"""


def render_analyze_page(page: AnalyzePageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id, target="analyze") for card in page.sessions) or (
        '<div class="placeholder-copy">No persisted sessions are available for analysis.</div>'
    )
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels) or (
        '<div class="placeholder-copy">Select a session to inspect analysis context.</div>'
    )
    forms = "".join(render_form_section(section) for section in page.form_sections)
    tables = "".join(render_table_section(table) for table in page.tables)
    return f"""
    <div class="page-stack">
      {render_page_topbar(surface_badges=page.surface_badges)}
      <section class="panel hero">
        <h2>{escape(page.title)}</h2>
        <p class="panel-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="section-grid">
        <div class="panel">
          <h3>{escape(page.section_header.title)}</h3>
          <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
          {sessions}
        </div>
        <div class="panel">
          <h3>Analysis Context</h3>
          <p class="panel-subtitle">The visible surface is driven from persisted session truth and explicit scaffold labels.</p>
          {summaries}
        </div>
      </section>
      <section class="section-grid">{forms}</section>
      {tables}
    </div>"""


def render_service_page(page: ServicePageModel) -> str:
    cards = "".join(render_device_card(card) for card in page.device_cards)
    notes = "".join(f"<li>{escape(note)}</li>" for note in page.notes)
    diagnostics = "".join(render_summary_panel(panel) for panel in page.diagnostic_panels)
    forms = "".join(render_form_section(section) for section in page.form_sections)
    tables = "".join(render_table_section(table) for table in page.tables)
    return f"""
    <div class="page-stack">
      {render_page_topbar(surface_badges=page.surface_badges)}
      <section class="panel hero">
        <h2>{escape(page.title)}</h2>
        <p class="panel-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="section-grid">
        <div class="panel">
          <h3>{escape(page.section_header.title)}</h3>
          <p class="panel-subtitle">{escape(page.section_header.subtitle)}</p>
          {cards}
        </div>
        <div class="panel">
          <h3>Service Limits</h3>
          <p class="panel-subtitle">Expert-only actions stay outside the default operator flow.</p>
          <ul class="notes-list">{notes}</ul>
        </div>
      </section>
      <section class="section-grid">{diagnostics}</section>
      <section class="section-grid">{forms}</section>
      {tables}
    </div>"""


def render_summary_panel(panel: SummaryPanel) -> str:
    rows = "".join(f'<div class="summary-row">{escape(item)}</div>' for item in panel.items) or (
        '<div class="summary-row placeholder-copy">No details available.</div>'
    )
    return f"""
    <div class="panel">
      <h3>{escape(panel.title)}</h3>
      <p class="panel-subtitle">{escape(panel.subtitle)}</p>
      {rows}
    </div>"""


def render_form_section(section: FormSectionModel) -> str:
    fields = "".join(render_form_field(field) for field in section.fields)
    notes = "".join(f"<li>{escape(note)}</li>" for note in section.notes)
    details = ""
    if notes:
        details = (
            "<details><summary>Section Notes</summary>"
            f'<ul class="notes-list">{notes}</ul>'
            "</details>"
        )
    return f"""
    <div class="panel">
      <h3>{escape(section.title)}</h3>
      <p class="panel-subtitle">{escape(section.subtitle)}</p>
      <div class="form-grid">{fields}</div>
      {details}
    </div>"""


def render_form_field(field: FormFieldModel) -> str:
    field_id = _field_id(field.label)
    if field.field_type == "textarea":
        control = (
            f'<textarea id="{field_id}" placeholder="{escape(field.placeholder)}" '
            f'{"disabled" if field.disabled else ""}>{escape(field.value)}</textarea>'
        )
        wrapper_class = "field"
    elif field.field_type == "select":
        options = "".join(
            f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>'
            f"{escape(option.label)}</option>"
            for option in field.options
        )
        control = f'<select id="{field_id}" {"disabled" if field.disabled else ""}>{options}</select>'
        wrapper_class = "field"
    elif field.field_type == "checkbox":
        control = (
            f'<input id="{field_id}" type="checkbox" '
            f'{"checked" if field.checked else ""} {"disabled" if field.disabled else ""}>'
        )
        wrapper_class = "field checkbox-field"
    else:
        input_type = "number" if field.field_type == "number" else "text"
        control = (
            f'<input id="{field_id}" type="{input_type}" value="{escape(field.value)}" '
            f'placeholder="{escape(field.placeholder)}" {"disabled" if field.disabled else ""}>'
        )
        wrapper_class = "field"

    if field.field_type == "checkbox":
        label_markup = f'<label for="{field_id}">{escape(field.label)}</label>'
        help_markup = (
            f'<div class="field-help">{escape(field.help_text)}</div>' if field.help_text else ""
        )
        return f'<div class="{wrapper_class}">{control}<div>{label_markup}{help_markup}</div></div>'

    help_markup = f'<div class="field-help">{escape(field.help_text)}</div>' if field.help_text else ""
    return f"""
    <div class="{wrapper_class}">
      <label for="{field_id}">{escape(field.label)}</label>
      {control}
      {help_markup}
    </div>"""


def render_table_section(table: TableModel) -> str:
    header_cells = "".join(f"<th>{escape(header)}</th>" for header in table.headers)
    if table.rows:
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
            for row in table.rows
        )
    else:
        rows = f'<tr><td colspan="{max(len(table.headers), 1)}" class="placeholder-copy">{escape(table.empty_message)}</td></tr>'
    return f"""
    <section class="panel">
      <h3>{escape(table.title)}</h3>
      <p class="panel-subtitle">{escape(table.subtitle)}</p>
      <table class="data-table">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_device_card(card: DeviceSummaryCard) -> str:
    details = "".join(f"<li>{escape(detail)}</li>" for detail in card.details)
    return f"""
    <div class="device-card">
      <strong>{escape(card.device_label)}</strong>
      <div><span class="status-label {escape(card.tone)}">{escape(card.status_label)}</span></div>
      <div>{escape(card.summary)}</div>
      {'<ul class="detail-list">' + details + '</ul>' if details else ''}
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
      {'<ul class="detail-list">' + details + '</ul>' if details else ''}
    </div>"""


def render_preflight_report(report: PreflightReport | None) -> str:
    if report is None:
        return '<div class="placeholder-copy">Preflight has not been requested yet.</div>'
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
        f'<div class="table-note"><strong>{escape(series.label)}</strong></div>'
        f'<div class="small">{escape(series.role_label)}</div>'
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


def render_session_card(card: SessionSummaryCard, scenario_id: str, *, target: str = "results") -> str:
    tone = {
        "Completed": "good",
        "Faulted": "bad",
        "Aborted": "warn",
    }.get(card.status_label, "neutral")
    failure_reason = (
        f'<div class="small">Failure reason: {escape(card.failure_reason_label)}</div>'
        if card.failure_reason_label
        else ""
    )
    results_link = f"/results?scenario={escape(scenario_id)}&session_id={escape(card.session_id)}"
    analyze_link = f"/analyze?scenario={escape(scenario_id)}&session_id={escape(card.session_id)}"
    return f"""
    <div class="session-card">
      <strong>{escape(card.recipe_title)}</strong>
      <div><span class="status-label {tone}">{escape(card.status_label)}</span></div>
      <div class="small">Session {escape(card.session_id)} updated {escape(card.updated_at.isoformat())}</div>
      <div class="small">Primary raw {card.primary_raw_artifact_count} | Secondary monitor {card.secondary_monitor_artifact_count}</div>
      <div class="small">Processed {card.processed_artifact_count} | Analysis {card.analysis_artifact_count} | Export {card.export_artifact_count}</div>
      <div class="small">Events {card.event_count} | Replay {'ready' if card.replay_ready else 'unavailable'}</div>
      {failure_reason}
      <div class="panel-actions">
        <form method="post" action="/results/reopen">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <input type="hidden" name="session_id" value="{escape(card.session_id)}">
          <button type="submit" class="secondary">Reopen Session</button>
        </form>
        <a class="button-link secondary" href="{results_link}">Open Results</a>
        <a class="button-link ghost" href="{analyze_link}">{"Stay in Analyze" if target == "analyze" else "Open Analyze"}</a>
      </div>
    </div>"""


def _field_id(label: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in label).strip("-")
