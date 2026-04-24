"""Server-rendered components for the three-page v1 workflow."""

from __future__ import annotations

from html import escape

from .models import (
    ActionButtonModel,
    FormFieldModel,
    HeaderStatus,
    NavigationItem,
    PanelModel,
    ResultsPageModel,
    ResultsPlotModel,
    RunListItem,
    SessionListItem,
    SessionPageModel,
    SetupPageModel,
    StatusBadge,
    StatusItemModel,
)
from .page_state import PageStateModel


APP_CSS = """
:root {
  --bg: #edf0f2;
  --surface: #ffffff;
  --panel: #f8fafb;
  --border: #cdd6de;
  --ink: #1d252c;
  --muted: #5d6872;
  --accent: #006b7f;
  --accent-dark: #005466;
  --danger: #a73535;
  --danger-border: #d46464;
  --warn-bg: #fff3d6;
  --bad-bg: #f9dedc;
  --good-bg: #deefdf;
  --info-bg: #e3eef5;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", Arial, sans-serif;
  color: var(--ink);
  background: var(--bg);
}
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
}
.shell-header {
  background: #24313b;
  color: #f4f8fb;
  padding: 20px 16px;
  display: grid;
  align-content: start;
  gap: 18px;
}
.shell-header h1 { margin: 0; font-size: 1.2rem; }
.rail-label {
  color: #b9c7d2;
  font-size: 0.75rem;
  text-transform: uppercase;
}
.nav-row, .badge-row { display: grid; gap: 8px; }
.nav-link {
  display: block;
  color: #f4f8fb;
  padding: 8px 10px;
  border-radius: 8px;
  text-decoration: none;
  border: 1px solid rgba(255,255,255,0.12);
}
.nav-link.active { background: rgba(0,107,127,0.45); }
.nav-link.disabled { opacity: 0.55; pointer-events: none; }
.badge-pill {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 999px;
  background: #edf2f5;
  color: #1d252c;
  font-size: 0.82rem;
}
.badge-pill.good { background: var(--good-bg); }
.badge-pill.warn { background: var(--warn-bg); }
.badge-pill.bad { background: var(--bad-bg); }
.badge-pill.info { background: var(--info-bg); }
main { padding: 20px; }
.page-stack { display: grid; gap: 14px; max-width: 1180px; }
.hero, .panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}
.hero h2, .panel h3 { margin: 0 0 6px; }
.hero-subtitle, .panel-subtitle, .help, .small { color: var(--muted); }
.two-column { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.field-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.field { display: grid; gap: 5px; }
.field label { font-weight: 600; }
input, select, textarea {
  width: 100%;
  font: inherit;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #bfcad3;
  background: white;
}
.field.invalid input, .field.invalid select, .field.invalid textarea {
  border-color: var(--danger-border);
  background: #fff5f5;
}
.field.invalid label, .field.invalid .help { color: var(--danger); }
textarea { min-height: 88px; }
input[readonly] { background: #eef2f5; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.panel-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.panel-head h3 { margin: 0; }
.panel-head .actions { margin-top: 0; justify-content: flex-end; }
button, .button-link {
  border: 0;
  border-radius: 6px;
  padding: 8px 12px;
  background: var(--accent);
  color: white;
  font: inherit;
  cursor: pointer;
  text-decoration: none;
}
button.secondary, .button-link.secondary { background: #53606a; }
button.success, .button-link.success { background: #2d8a57; }
button.danger, .button-link.danger { background: var(--danger); }
button:disabled, .button-link.disabled { opacity: 0.55; cursor: not-allowed; pointer-events: none; }
.state-box {
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 10px 12px;
}
.state-box.success { background: var(--good-bg); }
.state-box.blocked, .state-box.warning { background: var(--warn-bg); }
.state-box.fault { background: var(--bad-bg); }
.state-box.empty, .state-box.unavailable, .state-box.recovery { background: var(--info-bg); }
.status-grid { display: grid; gap: 8px; }
.status-row, .list-row { border-top: 1px solid #e1e7ec; padding: 8px 0; }
.status-row:first-child, .list-row:first-child { border-top: 0; }
.list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.inline-open {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.setup-sections { display: grid; gap: 14px; }
.plot-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.plot-table th, .plot-table td { border-top: 1px solid #e1e7ec; padding: 6px 8px; text-align: left; }
@media (max-width: 760px) {
  .app-shell { grid-template-columns: 1fr; }
  .two-column { grid-template-columns: 1fr; }
}
"""

APP_JS = """
document.addEventListener("DOMContentLoaded", () => {
  const setupForm = document.querySelector('form[action="/setup/save"]');
  const setupDraftKey = "ircp.setupDraft";
  const trackedFieldSelector = "input[name], select[name], textarea[name]";

  if (setupForm) {
    const restoreSetupDraft = () => {
      const raw = window.sessionStorage.getItem(setupDraftKey);
      if (!raw) {
        return;
      }
      try {
        const saved = JSON.parse(raw);
        setupForm.querySelectorAll(trackedFieldSelector).forEach((field) => {
          const name = field.name;
          if (!(name in saved)) {
            return;
          }
          if (field.type === "checkbox") {
            field.checked = Boolean(saved[name]);
            return;
          }
          field.value = saved[name];
        });
      } catch (_error) {
        window.sessionStorage.removeItem(setupDraftKey);
      }
    };

    const persistSetupDraft = () => {
      const draft = {};
      setupForm.querySelectorAll(trackedFieldSelector).forEach((field) => {
        if (field.type === "checkbox") {
          draft[field.name] = field.checked;
          return;
        }
        draft[field.name] = field.value;
      });
      window.sessionStorage.setItem(setupDraftKey, JSON.stringify(draft));
    };

    restoreSetupDraft();
    setupForm.querySelectorAll(trackedFieldSelector).forEach((field) => {
      field.addEventListener(field.tagName === "SELECT" ? "change" : "input", persistSetupDraft);
      field.addEventListener("change", persistSetupDraft);
    });
    setupForm.addEventListener("submit", () => {
      window.sessionStorage.removeItem(setupDraftKey);
    });
  }

  const pumpEnabled = document.querySelector('input[name="pump_enabled"]');
  const shotCount = document.querySelector('input[name="shot_count"]');
  if (pumpEnabled && shotCount) {
    const syncPumpFields = () => {
      shotCount.disabled = !pumpEnabled.checked;
    };
    pumpEnabled.addEventListener("change", syncPumpFields);
    syncPumpFields();
  }

  const emissionMode = document.querySelector('select[name="emission_mode"]');
  const pulseRate = document.querySelector('input[name="pulse_rate_hz"]');
  const pulseWidth = document.querySelector('input[name="pulse_width_ns"]');
  if (emissionMode && pulseRate && pulseWidth) {
    const syncProbeFields = () => {
      const pulsed = emissionMode.value === "pulsed";
      pulseRate.disabled = !pulsed;
      pulseWidth.disabled = !pulsed;
    };
    emissionMode.addEventListener("change", syncProbeFields);
    syncProbeFields();
  }
});
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
  <div class="app-shell">
    <aside class="shell-header">
      <h1>{escape(header.title)}</h1>
      <div class="small">{escape(header.summary)}</div>
      <div>
        <div class="rail-label">Workflow</div>
        <nav class="nav-row">{''.join(_render_nav(item) for item in header.navigation)}</nav>
      </div>
      <div>
        <div class="rail-label">Status</div>
        <div class="badge-row">{''.join(_render_badge(badge) for badge in header.badges)}</div>
      </div>
    </aside>
    <main>{body}</main>
  </div>
  <script>{APP_JS}</script>
</body>
</html>"""


def render_session_page(page: SessionPageModel) -> str:
    body = (
        _render_panel(page.session_panel)
        + _render_panel(page.run_header_panel)
        + _render_session_lists(page.existing_sessions, page.existing_runs)
    )
    return f'<div class="page-stack">{body}</div>'


def render_setup_page(page: SetupPageModel) -> str:
    sections = (
        _render_panel(page.pump_panel)
        + _render_panel(page.timescale_panel)
        + _render_panel(page.probe_panel)
        + _render_panel(page.lockin_panel)
        + _render_panel(page.run_controls_panel)
    )
    return f"""
<div class="page-stack">
  <form method="post" action="/setup/save">
    <div class="actions">{_render_action(page.save_action)}</div>
    <div class="setup-sections">{sections}</div>
  </form>
</div>"""


def render_results_page(page: ResultsPageModel) -> str:
    plot = _render_plot(page.plot)
    history = _render_run_history(page.run_history)
    body = (
        _render_panel(page.selector_panel)
        + _render_panel(page.metadata_panel)
        + plot
        + _render_panel(page.export_panel)
        + history
    )
    return _page_frame(page.title, page.subtitle, page.state, body)


def _page_frame(title: str, subtitle: str, state: PageStateModel | None, body: str) -> str:
    return f"""
<div class="page-stack">
  <section class="hero">
    <h2>{escape(title)}</h2>
    <div class="hero-subtitle">{escape(subtitle)}</div>
    {_render_state(state)}
  </section>
  {body}
</div>"""


def _render_panel(panel: PanelModel) -> str:
    form_start = f'<form method="post" action="{escape(panel.form_action)}">' if panel.form_action else ""
    form_end = "</form>" if panel.form_action else ""
    header_actions = _render_actions(panel.header_actions)
    return f"""
<section class="panel">
  <div class="panel-head"><h3>{escape(panel.title)}</h3>{header_actions}</div>
  {_render_state(panel.state)}
  {form_start}
  {_render_fields(panel.fields)}
  {_render_status_items(panel.status_items)}
  {_render_notes(panel.notes)}
  {_render_actions(panel.actions)}
  {form_end}
</section>"""


def _render_fields(fields: tuple[FormFieldModel, ...]) -> str:
    if not fields:
        return ""
    return '<div class="field-grid">' + "".join(_render_field(field) for field in fields) + "</div>"


def _render_field(field: FormFieldModel) -> str:
    attrs = []
    if field.required:
        attrs.append("required")
    if field.disabled:
        attrs.append("disabled")
    if field.read_only:
        attrs.append("readonly")
    if field.min_value:
        attrs.append(f'min="{escape(field.min_value)}"')
    if field.max_value:
        attrs.append(f'max="{escape(field.max_value)}"')
    if field.step:
        attrs.append(f'step="{escape(field.step)}"')
    attr_text = " ".join(attrs)
    name = escape(field.name)
    label = escape(field.label)
    value = escape(field.value)
    field_class = "field invalid" if field.invalid else "field"
    if field.field_type == "select":
        control = (
            f'<select name="{name}" {attr_text}>'
            + "".join(
                f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>{escape(option.label)}</option>'
                for option in field.options
            )
            + "</select>"
        )
    elif field.field_type == "textarea":
        control = f'<textarea name="{name}" {attr_text}>{value}</textarea>'
    elif field.field_type == "checkbox":
        control = f'<input type="checkbox" name="{name}" value="1" {"checked" if field.checked else ""} {attr_text}>'
    else:
        control = f'<input type="{escape(field.field_type)}" name="{name}" value="{value}" {attr_text}>'
    help_text = f'<div class="help">{escape(field.help_text)}</div>' if field.help_text else ""
    label_html = f"<label>{label}</label>" if field.label else ""
    return f'<div class="{field_class}">{label_html}{control}{help_text}</div>'


def _render_actions(actions: tuple[ActionButtonModel, ...]) -> str:
    if not actions:
        return ""
    return '<div class="actions">' + "".join(_render_action(action) for action in actions) + "</div>"


def _render_action(action: ActionButtonModel) -> str:
    disabled = "disabled" if action.disabled else ""
    helper = f'<span class="help">{escape(action.helper_text)}</span>' if action.helper_text else ""
    return (
        f'<span><button class="{escape(action.tone)}" formaction="{escape(action.action)}" {disabled}>'
        f'{escape(action.label)}</button>{helper}</span>'
    )


def _render_status_items(items: tuple[StatusItemModel, ...]) -> str:
    if not items:
        return ""
    return '<div class="status-grid">' + "".join(_render_status_item(item) for item in items) + "</div>"


def _render_status_item(item: StatusItemModel) -> str:
    detail = f'<div class="small">{escape(item.detail)}</div>' if item.detail else ""
    return f'<div class="status-row"><strong>{escape(item.label)}:</strong> {escape(item.value)}{detail}</div>'


def _render_state(state: PageStateModel | None) -> str:
    if state is None:
        return ""
    details = "".join(f"<li>{escape(detail)}</li>" for detail in state.details)
    detail_html = f"<ul>{details}</ul>" if details else ""
    return (
        f'<div class="state-box {escape(state.kind.value)}"><strong>{escape(state.title)}</strong>'
        f'<div>{escape(state.message)}</div>{detail_html}</div>'
    )


def _render_notes(notes: tuple[str, ...]) -> str:
    if not notes:
        return ""
    return "".join(f'<p class="small">{escape(note)}</p>' for note in notes)


def _render_saved_item(primary: str, identifier: str, suffix: str = "") -> str:
    identifier_html = "" if primary == identifier else f' <span class="small">({escape(identifier)})</span>'
    return f'<strong>{escape(primary)}</strong>{identifier_html}{suffix}'


def _render_inline_open(action: str, hidden_fields: dict[str, str], disabled: bool, helper_text: str = "") -> str:
    inputs = "".join(
        f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'
        for name, value in hidden_fields.items()
    )
    helper = f'<span class="help">{escape(helper_text)}</span>' if helper_text else ""
    return (
        f'<form method="post" action="{escape(action)}" class="inline-open">'
        f"{inputs}<button class=\"secondary\" {'disabled' if disabled else ''}>Open</button>{helper}</form>"
    )


def _render_session_lists(sessions: tuple[SessionListItem, ...], runs: tuple[RunListItem, ...]) -> str:
    session_rows = "".join(
        f'<div class="list-row"><div>{_render_saved_item(item.label, item.session_id)}</div>'
        f'{_render_inline_open("/session/open", {"session_id": item.session_id}, disabled=not item.open_enabled)}</div>'
        for item in sessions
    ) or '<div class="small">No saved sessions.</div>'
    run_rows = "".join(
        f'<div class="list-row"><div>{_render_saved_item(item.label, item.run_id, f" ({escape(item.status)})")}</div>'
        f'{_render_inline_open("/session/run/open", {"session_id": item.session_id, "run_id": item.run_id}, disabled=not item.open_enabled, helper_text="" if item.open_enabled else "Open the session first.")}</div>'
        for item in runs
    ) or '<div class="small">No saved runs.</div>'
    return f"""
<section class="panel two-column">
  <div><h3>Open existing session</h3>{session_rows}</div>
  <div><h3>Open existing run for review</h3>{run_rows}</div>
</section>"""


def _render_run_history(runs: tuple[RunListItem, ...]) -> str:
    rows = "".join(
        f'<div class="list-row">{_render_saved_item(item.label, item.run_id, f" ({escape(item.status)})")}</div>'
        for item in runs
    ) or '<div class="small">No saved runs.</div>'
    return f'<section class="panel"><h3>Saved run history</h3>{rows}</section>'


def _render_plot(plot: ResultsPlotModel | None) -> str:
    if plot is None:
        return '<section class="panel"><h3>Result plot</h3><div class="small">No saved run data selected.</div></section>'
    if plot.display_mode == "ratio":
        header = "<tr><th>Time</th><th>-log(sample/reference)</th></tr>"
        rows = "".join(
            f"<tr><td>{point.time_seconds:.9g}</td><td>{point.ratio:.9g}</td></tr>"
            for point in plot.points[:80]
            if point.ratio is not None
        )
    else:
        header = "<tr><th>Time</th><th>Sample</th><th>Reference</th></tr>"
        rows = "".join(
            f"<tr><td>{point.time_seconds:.9g}</td><td>{point.sample:.9g}</td><td>{point.reference:.9g}</td></tr>"
            for point in plot.points[:80]
            if point.sample is not None and point.reference is not None
        )
    return f"""
<section class="panel">
  <h3>Result plot</h3>
  <div class="panel-subtitle">{escape(plot.metric_family)} - {escape(plot.display_mode)}</div>
  <table class="plot-table">{header}{rows}</table>
</section>"""


def _render_nav(item: NavigationItem) -> str:
    cls = "nav-link"
    if item.active:
        cls += " active"
    if item.disabled:
        cls += " disabled"
    return f'<a class="{cls}" href="{escape(item.href)}">{escape(item.label)}</a>'


def _render_badge(badge: StatusBadge) -> str:
    return f'<span class="badge-pill {escape(badge.tone)}">{escape(badge.label)}</span>'
