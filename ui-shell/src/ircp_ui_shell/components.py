"""Server-rendered UI primitives for the operator-first shell."""

from __future__ import annotations

from html import escape

from .models import (
    ActionButtonModel,
    AdvancedPageModel,
    AdvancedSectionModel,
    AnalyzePageModel,
    CalloutModel,
    DeviceSummaryCard,
    EventLogItem,
    FormFieldModel,
    HeaderStatus,
    NavigationItem,
    OperatePageModel,
    OperatePanelModel,
    ResultsPageModel,
    ServicePageModel,
    SessionSummaryCard,
    StatusBadge,
    StatusItemModel,
    SummaryPanel,
    TableModel,
)
from .page_state import PageStateModel


APP_CSS = """
:root {
  --bg-top: #f4efe3;
  --bg-bottom: #e6ede8;
  --surface: rgba(255, 255, 255, 0.92);
  --surface-strong: rgba(255, 255, 255, 0.97);
  --border: #d6d0c1;
  --ink: #172129;
  --muted: #55606d;
  --accent: #0f766e;
  --accent-strong: #115e59;
  --accent-soft: rgba(15, 118, 110, 0.1);
  --secondary: #475569;
  --ghost: #b45309;
  --danger: #b91c1c;
  --good-bg: #ddf4e6;
  --good-border: #6a9f7a;
  --warn-bg: #fff4d6;
  --warn-border: #d1a54d;
  --bad-bg: #ffe4df;
  --bad-border: #d66855;
  --info-bg: #e5f0f6;
  --info-border: #6f93ac;
  --shadow: 0 14px 36px rgba(24, 37, 51, 0.08);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 34%),
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
    linear-gradient(135deg, rgba(20, 34, 46, 0.98) 0%, rgba(16, 74, 82, 0.94) 60%, rgba(90, 61, 42, 0.94) 100%);
  color: #f8fbfc;
  padding: 28px 24px 30px;
  box-shadow: var(--shadow);
}

.shell-header h1 {
  margin: 0 0 10px;
  font-size: 2rem;
  letter-spacing: -0.03em;
}

.nav-row, .scenario-row, .badge-row, .surface-badges, .action-row, .toolbar-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.scenario-row, .nav-row, .badge-row { margin-top: 12px; }

.nav-link, .scenario-chip, .badge-pill, .button-link {
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

.page-stack {
  display: grid;
  gap: 18px;
}

.hero {
  background: var(--surface-strong);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 22px;
  box-shadow: var(--shadow);
}

.hero h2, .panel h3, .panel h4 {
  margin-top: 0;
}

.panel-subtitle, .hero-subtitle {
  color: var(--muted);
  margin-top: -4px;
  margin-bottom: 14px;
}

.small {
  color: #66717c;
  font-size: 0.92rem;
}

.panel-grid {
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

.panel.state-accent {
  border-color: rgba(15, 118, 110, 0.24);
}

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
.state-box.unavailable, .state-box.recovery, .callout.info {
  background: var(--info-bg);
  border-color: var(--info-border);
}
.callout.good { background: var(--good-bg); border-color: var(--good-border); }

.callout-stack {
  display: grid;
  gap: 12px;
}

.toolbar-row {
  margin-top: 12px;
}

.action-row {
  align-items: center;
}

.button-note {
  display: block;
  color: var(--muted);
  font-size: 0.86rem;
  margin-top: 6px;
}

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

button.secondary, .button-link.secondary { background: var(--secondary); }
button.ghost, .button-link.ghost { background: var(--ghost); }
button.danger, .button-link.danger { background: var(--danger); }

button:disabled, .button-link.disabled {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
}

.field-grid {
  display: grid;
  gap: 12px;
}

.status-grid {
  display: grid;
  gap: 10px;
}

.status-item, .device-card, .session-card, .summary-row, .event-row {
  padding: 10px 0;
  border-top: 1px solid #ebe7db;
}

.status-item:first-child,
.device-card:first-child,
.session-card:first-child,
.summary-row:first-child,
.event-row:first-child {
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
.status-label.info { background: #e2eef8; }
.status-label.neutral { background: #edf2f7; }

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

.field textarea {
  min-height: 88px;
  resize: vertical;
}

.field-help {
  color: var(--muted);
  font-size: 0.88rem;
}

.notes-list, .detail-list {
  margin: 8px 0 0 18px;
  padding: 0;
}

.detail-list li, .notes-list li {
  margin-top: 6px;
}

.placeholder-copy {
  color: #6c6f74;
  font-style: italic;
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

.accordion {
  border-top: 1px dashed #d4d0c4;
  padding-top: 10px;
}

details > summary {
  cursor: pointer;
  font-weight: 600;
  color: #32414d;
  list-style: none;
}

details > summary::-webkit-details-marker { display: none; }

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
            f'href="/operate?scenario={escape(option.scenario_id)}">{escape(option.label)}</a>'
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


def render_operate_page(page: OperatePageModel, scenario_id: str) -> str:
    live_status = "".join(render_status_item(item) for item in page.live_status)
    activity = "".join(render_event_row(item) for item in page.recent_activity) or (
        '<div class="placeholder-copy">No recent activity yet.</div>'
    )
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="panel-grid">
        {render_operate_panel(page.session_panel, scenario_id)}
        {render_operate_panel(page.laser_panel, scenario_id)}
        {render_operate_panel(page.acquisition_panel, scenario_id)}
        {render_operate_panel(page.run_panel, scenario_id)}
      </section>
      <section class="panel-grid">
        <div class="panel state-accent">
          <h3>Live Status</h3>
          <p class="panel-subtitle">What the system is doing right now, without the diagnostic overload.</p>
          <div class="status-grid">{live_status}</div>
        </div>
        <div class="panel">
          <h3>Recent Activity</h3>
          <p class="panel-subtitle">Compact events, warnings, and action feedback for the current operator pass.</p>
          {activity}
        </div>
      </section>
    </div>"""


def render_operate_panel(panel: OperatePanelModel, scenario_id: str) -> str:
    fields = "".join(render_form_field(field) for field in panel.fields)
    actions = "".join(render_action_button(button, scenario_id) for button in panel.actions)
    status_items = "".join(render_status_item(item) for item in panel.status_items) or (
        '<div class="placeholder-copy">No status is available for this section yet.</div>'
    )
    notes = "".join(f"<li>{escape(note)}</li>" for note in panel.notes)
    notes_markup = f'<ul class="notes-list">{notes}</ul>' if notes else ""
    return f"""
    <section class="panel state-accent">
      <h3>{escape(panel.title)}</h3>
      <p class="panel-subtitle">{escape(panel.subtitle)}</p>
      {render_page_state(panel.state)}
      <form method="post">
        <input type="hidden" name="scenario" value="{escape(scenario_id)}">
        <div class="field-grid">{fields}</div>
        <div class="action-row">{actions}</div>
      </form>
      <div class="status-grid">{status_items}</div>
      {notes_markup}
    </section>"""


def render_action_button(button: ActionButtonModel, scenario_id: str) -> str:
    hidden_fields = "".join(
        f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'
        for name, value in button.hidden_fields
    )
    helper = f'<span class="button-note">{escape(button.helper_text)}</span>' if button.helper_text else ""
    tone_class = "" if button.tone == "primary" else f" {escape(button.tone)}"
    return (
        '<div>'
        f'{hidden_fields}<button type="submit" formaction="{escape(button.action)}"'
        f' class="{tone_class.strip()}" {"disabled" if button.disabled else ""}>'
        f"{escape(button.label)}</button>{helper}</div>"
    )


def render_status_item(item: StatusItemModel) -> str:
    detail = f'<div class="small">{escape(item.detail)}</div>' if item.detail else ""
    return (
        '<div class="status-item">'
        f'<div><strong>{escape(item.label)}</strong></div>'
        f'<div><span class="status-label {escape(item.tone)}">{escape(item.value)}</span></div>'
        f"{detail}</div>"
    )


def render_form_field(field: FormFieldModel) -> str:
    if field.field_type == "select":
        options = "".join(
            f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>{escape(option.label)}</option>'
            for option in field.options
        )
        control = (
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f'<select id="{escape(field.name)}" name="{escape(field.name)}" {"disabled" if field.disabled else ""}>{options}</select>'
        )
    elif field.field_type == "textarea":
        control = (
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f'<textarea id="{escape(field.name)}" name="{escape(field.name)}" placeholder="{escape(field.placeholder)}" '
            f'{"disabled" if field.disabled else ""}>{escape(field.value)}</textarea>'
        )
    else:
        field_type = "number" if field.field_type == "number" else "text"
        control = (
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f'<input id="{escape(field.name)}" name="{escape(field.name)}" type="{field_type}" value="{escape(field.value)}" '
            f'placeholder="{escape(field.placeholder)}" {"disabled" if field.disabled else ""}>'
        )
    help_markup = f'<div class="field-help">{escape(field.help_text)}</div>' if field.help_text else ""
    return f'<div class="field">{control}{help_markup}</div>'


def render_results_page(page: ResultsPageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id, target="results") for card in page.sessions) or (
        '<div class="placeholder-copy">No saved sessions are available yet.</div>'
    )
    details = "".join(render_summary_panel(panel) for panel in page.detail_panels) or (
        '<div class="placeholder-copy">Select a session to inspect the saved summary.</div>'
    )
    artifacts = "".join(render_summary_panel(panel) for panel in page.artifact_panels) or (
        '<div class="placeholder-copy">Artifact groups appear after a session is selected.</div>'
    )
    storage = "".join(render_summary_panel(panel) for panel in page.storage_panels)
    events = "".join(render_event_row(item) for item in page.event_log) or (
        '<div class="placeholder-copy">No saved event timeline is available for this selection.</div>'
    )
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="panel-grid">
        <div class="panel">
          <h3>Recent Sessions</h3>
          <p class="panel-subtitle">Pick a saved session and review the persisted record.</p>
          {sessions}
        </div>
        <div class="panel">
          <h3>Selected Session</h3>
          <p class="panel-subtitle">Human-readable summary of the saved manifest, outcome, and replay context.</p>
          {details}
        </div>
      </section>
      <section class="panel-grid">
        <div class="panel">
          <h3>Artifacts and Provenance</h3>
          <p class="panel-subtitle">Saved raw, processed, analysis, and export groups remain separated.</p>
          {artifacts}
        </div>
        <div class="panel">
          <h3>Storage Details</h3>
          <p class="panel-subtitle">Basic durable session details that can already be shown honestly.</p>
          {storage or '<div class="placeholder-copy">Storage details appear when a session is selected.</div>'}
        </div>
      </section>
      <section class="panel">
        <h3>Session Activity</h3>
        <p class="panel-subtitle">Persisted run events for the selected session.</p>
        {events}
      </section>
    </div>"""


def render_advanced_page(page: AdvancedPageModel) -> str:
    sections = "".join(render_advanced_section(section) for section in page.sections)
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      {sections}
    </div>"""


def render_advanced_section(section: AdvancedSectionModel) -> str:
    summaries = "".join(render_summary_panel(panel) for panel in section.summary_panels)
    tables = "".join(render_table_section(table) for table in section.tables)
    notes = "".join(f"<li>{escape(note)}</li>" for note in section.notes)
    notes_markup = f'<ul class="notes-list">{notes}</ul>' if notes else ""
    open_attr = " open" if section.open_by_default else ""
    return f"""
    <section class="panel">
      <details class="accordion"{open_attr}>
        <summary>{escape(section.title)}</summary>
        <p class="panel-subtitle">{escape(section.subtitle)}</p>
        <div class="panel-grid">{summaries}</div>
        {tables}
        {notes_markup}
      </details>
    </section>"""


def render_analyze_page(page: AnalyzePageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id, target="analyze") for card in page.sessions) or (
        '<div class="placeholder-copy">No persisted sessions are available for analysis.</div>'
    )
    summaries = "".join(render_summary_panel(panel) for panel in page.summary_panels) or (
        '<div class="placeholder-copy">Select a session to inspect analysis context.</div>'
    )
    tables = "".join(render_table_section(table) for table in page.tables)
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="panel-grid">
        <div class="panel">
          <h3>Available Sessions</h3>
          <p class="panel-subtitle">Analyze stays secondary and starts from saved session truth.</p>
          {sessions}
        </div>
        <div class="panel">
          <h3>Analyze Preview</h3>
          <p class="panel-subtitle">Small, explicit signals for what exists now and what is deferred.</p>
          {summaries}
        </div>
      </section>
      {tables}
    </div>"""


def render_service_page(page: ServicePageModel) -> str:
    cards = "".join(render_device_card(card) for card in page.device_cards) or (
        '<div class="placeholder-copy">No device summaries are available.</div>'
    )
    diagnostics = "".join(render_summary_panel(panel) for panel in page.diagnostic_panels)
    tables = "".join(render_table_section(table) for table in page.tables)
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="panel-grid">
        <div class="panel">
          <h3>Device Diagnostics</h3>
          <p class="panel-subtitle">Expert-only summaries for bench and maintenance work.</p>
          {cards}
        </div>
        <div class="panel">
          <h3>Service Context</h3>
          <p class="panel-subtitle">What this surface owns and what stays out of the default operator path.</p>
          {diagnostics or '<div class="placeholder-copy">No service diagnostics are available.</div>'}
        </div>
      </section>
      {tables}
    </div>"""


def render_summary_panel(panel: SummaryPanel) -> str:
    rows = "".join(f'<div class="summary-row">{escape(item)}</div>' for item in panel.items) or (
        '<div class="summary-row placeholder-copy">No details available.</div>'
    )
    return f"""
    <div class="panel">
      <h4>{escape(panel.title)}</h4>
      <p class="panel-subtitle">{escape(panel.subtitle)}</p>
      {rows}
    </div>"""


def render_table_section(table: TableModel) -> str:
    headers = "".join(f"<th>{escape(header)}</th>" for header in table.headers)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in table.rows
    )
    if not rows:
        rows = f'<tr><td colspan="{max(len(table.headers), 1)}" class="placeholder-copy">{escape(table.empty_message)}</td></tr>'
    return f"""
    <section class="panel">
      <h4>{escape(table.title)}</h4>
      <p class="panel-subtitle">{escape(table.subtitle)}</p>
      <table class="data-table">
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_device_card(card: DeviceSummaryCard) -> str:
    details = "".join(f"<li>{escape(item)}</li>" for item in card.details)
    return f"""
    <div class="device-card">
      <div><strong>{escape(card.device_label)}</strong></div>
      <div><span class="status-label {escape(card.tone)}">{escape(card.status_label)}</span></div>
      <div>{escape(card.summary)}</div>
      {'<ul class="detail-list">' + details + '</ul>' if details else ''}
    </div>"""


def render_event_row(item: EventLogItem) -> str:
    return f"""
    <div class="event-row">
      <div><strong>{escape(item.source)}</strong></div>
      <div>{escape(item.message)}</div>
      <div class="small">{escape(item.timestamp.isoformat())}</div>
    </div>"""


def render_session_card(card: SessionSummaryCard, scenario_id: str, *, target: str) -> str:
    tone = "good" if card.replay_ready else ("warn" if card.failure_reason_label is None else "bad")
    failure = (
        f'<div class="small">Failure reason: {escape(card.failure_reason_label)}</div>'
        if card.failure_reason_label
        else ""
    )
    analyze_link = f"/analyze?scenario={escape(scenario_id)}&session_id={escape(card.session_id)}"
    return f"""
    <div class="session-card">
      <div><strong>{escape(card.recipe_title)}</strong></div>
      <div><span class="status-label {tone}">{escape(card.status_label)}</span></div>
      <div class="small">Session {escape(card.session_id)} updated {escape(card.updated_at.isoformat())}</div>
      <div class="small">Primary raw {card.primary_raw_artifact_count} | Secondary monitor {card.secondary_monitor_artifact_count}</div>
      <div class="small">Processed {card.processed_artifact_count} | Analysis {card.analysis_artifact_count} | Export {card.export_artifact_count}</div>
      <div class="small">Events {card.event_count} | Replay {'ready' if card.replay_ready else 'unavailable'}</div>
      {failure}
      <div class="toolbar-row">
        <form method="post" action="/operate/session/open">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <input type="hidden" name="session_id" value="{escape(card.session_id)}">
          <button type="submit" class="secondary">Open in Operate</button>
        </form>
        <a class="button-link {'secondary' if target == 'results' else 'ghost'}" href="/results?scenario={escape(scenario_id)}&session_id={escape(card.session_id)}">Open Results</a>
        <a class="button-link ghost" href="{analyze_link}">Analyze</a>
      </div>
    </div>"""
