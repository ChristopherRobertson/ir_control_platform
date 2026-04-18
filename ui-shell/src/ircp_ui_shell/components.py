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
    OperateDisclosureModel,
    OperatePageModel,
    OperatePanelModel,
    ResultsArtifactRowModel,
    ResultsFilterModel,
    ResultsPageModel,
    ResultsTracePreviewModel,
    ServicePageModel,
    SessionSummaryCard,
    StatusBadge,
    StatusItemModel,
    SummaryPanel,
    SurfaceActionModel,
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
code {
  font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
  font-size: 0.92em;
}

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

.selection-context {
  display: grid;
  gap: 16px;
}

.metric-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.results-action-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: flex-start;
}

.results-filter-form {
  display: grid;
  gap: 12px;
}

.results-filter-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 2fr) repeat(2, minmax(180px, 1fr));
}

.filter-summary {
  color: var(--muted);
  font-size: 0.92rem;
}

.panel-header-row {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: flex-start;
}

.panel-heading {
  flex: 1 1 auto;
  min-width: 0;
}

.panel-header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
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

.field-grid.two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-grid.three-column {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.field-group-heading {
  grid-column: 1 / -1;
  padding-top: 8px;
}

.field-group-heading:first-child {
  padding-top: 0;
}

.field-group-heading strong {
  display: block;
  margin-bottom: 4px;
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

.session-card.selected {
  background: rgba(15, 118, 110, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 14px;
  margin: 8px -10px 0;
  padding: 12px 10px 10px;
}

.session-card.selected:first-child {
  margin-top: 0;
}

.trace-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.trace-card {
  display: grid;
  gap: 12px;
}

.trace-chart {
  border: 1px solid #ebe7db;
  border-radius: 14px;
  padding: 10px;
  background:
    linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(15, 118, 110, 0.02)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 248, 249, 0.92));
}

.trace-chart svg {
  width: 100%;
  height: 132px;
  display: block;
}

.trace-chart polyline {
  fill: none;
  stroke: var(--accent);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trace-meta {
  display: grid;
  gap: 6px;
}

.artifact-list {
  display: grid;
}

.artifact-row {
  padding: 12px 0;
  border-top: 1px solid #ebe7db;
  display: grid;
  gap: 10px;
}

.artifact-row:first-child {
  border-top: none;
  padding-top: 0;
}

.artifact-row-head {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
}

.artifact-row-meta {
  display: grid;
  gap: 4px;
}

.artifact-row-path {
  word-break: break-word;
  color: #4b5563;
}

.field {
  display: grid;
  gap: 6px;
}

.field.full-width {
  grid-column: 1 / -1;
}

.field.checkbox-field {
  display: flex;
  align-items: center;
  gap: 10px;
  align-self: end;
  padding-bottom: 10px;
}

.field label {
  font-weight: 600;
  color: #24303a;
}

.field.checkbox-field label {
  margin: 0;
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

.field.checkbox-field input {
  width: auto;
  margin: 0;
}

.field input:disabled,
.field select:disabled,
.field textarea:disabled {
  background: #e5e7eb;
  border-color: #d0d5dd;
  color: #7a8793;
  cursor: not-allowed;
}

.field input[readonly],
.field textarea[readonly] {
  background: #f3f4f6;
  border-color: #d0d5dd;
}

.field input:invalid,
.field textarea:invalid,
.field select:invalid {
  border-color: #b91c1c;
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
  .results-filter-grid { grid-template-columns: 1fr; }
}
"""

APP_SHELL_SCRIPT = """
<script>
(() => {
  const fixedModeFieldNames = ["tune_target_cm1"];
  const scanModeFieldNames = [
    "scan_start_cm1",
    "scan_stop_cm1",
    "scan_step_size_cm1",
  ];
  const pulseFieldNames = [
    "pulse_repetition_rate_hz",
    "pulse_width_ns",
    "pulse_duty_cycle_percent",
  ];
  const fixedModeActionPaths = ["/experiment/laser/tune"];
  const scanModeActionPaths = [
    "/experiment/laser/scan/start",
    "/experiment/laser/scan/stop",
  ];
  const operatingModeFieldNames = [
    "experiment_type",
    "emission_mode",
    "pulse_repetition_rate_hz",
    "pulse_width_ns",
    "ndyag_continuous",
  ];
  const pulseRepetitionRateMinHz = 10;
  const pulseRepetitionRateMaxHz = 3000000;
  const pulseWidthMinNs = 20;
  const pulseWidthMaxNs = 1005;
  const pulseDutyCycleMaxPercent = 30;
  const guardedLaserActions = new Set([
    "/experiment/laser/arm",
    "/experiment/laser/tune",
    "/experiment/laser/emission/on",
    "/experiment/laser/scan/start",
  ]);

  function calculateDutyCyclePercent(rateHz, pulseWidthNs) {
    if (!Number.isFinite(rateHz) || !Number.isFinite(pulseWidthNs) || rateHz <= 0 || pulseWidthNs <= 0) {
      return 0;
    }
    return rateHz * pulseWidthNs * 1e-7;
  }

  function maxPulseWidthNs(rateHz) {
    if (!Number.isFinite(rateHz) || rateHz <= 0) {
      return pulseWidthMaxNs;
    }
    return (pulseDutyCycleMaxPercent / 100) / (rateHz * 1e-9);
  }

  function syncOperatingModeActionButtons(form) {
    const emissionMode = form.querySelector('select[name="emission_mode"]');
    if (!emissionMode) {
      return;
    }
    const formValid = form.checkValidity();
    for (const button of form.querySelectorAll('button[formaction]')) {
      if (!(button instanceof HTMLButtonElement)) {
        continue;
      }
      if (button.dataset.serverDisabled == null) {
        button.dataset.serverDisabled = button.disabled ? "true" : "false";
      }
      const action = button.getAttribute("formaction") || "";
      if (!guardedLaserActions.has(action)) {
        continue;
      }
      button.disabled = button.dataset.serverDisabled === "true" || !formValid;
    }
  }

  function collectAsyncFormState(excludedForm) {
    const values = new Map();
    for (const form of document.querySelectorAll('form[data-async-form="true"]')) {
      if (form === excludedForm) {
        continue;
      }
      for (const control of form.elements) {
        if (!(control instanceof HTMLInputElement) &&
            !(control instanceof HTMLSelectElement) &&
            !(control instanceof HTMLTextAreaElement)) {
          continue;
        }
        if (!control.name || control.type === "hidden") {
          continue;
        }
        values.set(control.name, {
          type: control.type,
          value: control.value,
          checked: control instanceof HTMLInputElement ? control.checked : false,
        });
      }
    }
    return values;
  }

  function restoreAsyncFormState(values) {
    for (const [name, state] of values.entries()) {
      const selector = `[name="${CSS.escape(name)}"]`;
      const controls = document.querySelectorAll(selector);
      for (const control of controls) {
        if (control instanceof HTMLInputElement) {
          if (control.type === "checkbox") {
            control.checked = Boolean(state.checked);
          } else {
            control.value = state.value;
          }
        } else if (control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement) {
          control.value = state.value;
        }
      }
    }
  }

  function syncFieldVisibility(form, fieldNames, visible) {
    for (const fieldName of fieldNames) {
      const wrapper = form.querySelector(`[data-field-name="${fieldName}"]`);
      const input = form.querySelector(`[name="${fieldName}"]`);
      if (wrapper instanceof HTMLElement) {
        wrapper.hidden = !visible;
      }
      if (input instanceof HTMLInputElement ||
          input instanceof HTMLSelectElement ||
          input instanceof HTMLTextAreaElement) {
        input.disabled = !visible;
      }
    }
  }

  function syncActionVisibility(form, actionPaths, visible) {
    for (const actionPath of actionPaths) {
      const wrapper = form.querySelector(`[data-action-button="${CSS.escape(actionPath)}"]`);
      if (wrapper instanceof HTMLElement) {
        wrapper.hidden = !visible;
      }
    }
  }

  function syncNdyagFields(form) {
    const continuousInput = form.querySelector('input[name="ndyag_continuous"]');
    const shotCountInput = form.querySelector('input[name="ndyag_shot_count"]');
    if (!(continuousInput instanceof HTMLInputElement) ||
        !(shotCountInput instanceof HTMLInputElement)) {
      return;
    }
    const shotCountEnabled = !continuousInput.disabled && !continuousInput.checked;
    shotCountInput.disabled = !shotCountEnabled;
  }

  function syncOperatingModeFields(root = document) {
    const forms =
      root instanceof HTMLFormElement
        ? [root]
        : Array.from(root.querySelectorAll('form[data-async-form="true"]'));
    for (const form of forms) {
      syncNdyagFields(form);
      const experimentType = form.querySelector('select[name="experiment_type"]');
      const emissionMode = form.querySelector('select[name="emission_mode"]');
      if (!(experimentType instanceof HTMLSelectElement) || !(emissionMode instanceof HTMLSelectElement)) {
        continue;
      }
      const wavelengthScan = experimentType.value === "wavelength_scan";
      syncFieldVisibility(form, fixedModeFieldNames, !wavelengthScan);
      syncFieldVisibility(form, scanModeFieldNames, wavelengthScan);
      syncActionVisibility(form, fixedModeActionPaths, !wavelengthScan);
      syncActionVisibility(form, scanModeActionPaths, wavelengthScan);
      const repetitionRateInput = form.querySelector('input[name="pulse_repetition_rate_hz"]');
      const pulseWidthInput = form.querySelector('input[name="pulse_width_ns"]');
      const dutyCycleInput = form.querySelector('input[name="pulse_duty_cycle_percent"]');
      const pulsed = emissionMode.value === "pulsed";
      syncFieldVisibility(form, pulseFieldNames, pulsed);
      if (!(repetitionRateInput instanceof HTMLInputElement) ||
          !(pulseWidthInput instanceof HTMLInputElement) ||
          !(dutyCycleInput instanceof HTMLInputElement)) {
        continue;
      }
      const repetitionRateHz = Number.parseFloat(repetitionRateInput.value);
      const pulseWidthNs = Number.parseFloat(pulseWidthInput.value);
      const allowedPulseWidthMaxNs = Math.min(pulseWidthMaxNs, maxPulseWidthNs(repetitionRateHz));
      repetitionRateInput.min = String(pulseRepetitionRateMinHz);
      repetitionRateInput.max = String(pulseRepetitionRateMaxHz);
      pulseWidthInput.min = String(pulseWidthMinNs);
      pulseWidthInput.max = String(Math.max(pulseWidthMinNs, Math.floor(allowedPulseWidthMaxNs)));
      const dutyCyclePercent = calculateDutyCyclePercent(repetitionRateHz, pulseWidthNs);
      dutyCycleInput.value = dutyCyclePercent.toFixed(3);
      const dutyCycleMessage =
        dutyCyclePercent > pulseDutyCycleMaxPercent
          ? `Duty cycle must be ${pulseDutyCycleMaxPercent}% or less.`
          : "";
      repetitionRateInput.setCustomValidity(dutyCycleMessage);
      pulseWidthInput.setCustomValidity(dutyCycleMessage);
      dutyCycleInput.setCustomValidity(dutyCycleMessage);
      if (!pulsed) {
        repetitionRateInput.setCustomValidity("");
        pulseWidthInput.setCustomValidity("");
        dutyCycleInput.setCustomValidity("");
      }
      syncOperatingModeActionButtons(form);
    }
  }

  function restoreFocus(name) {
    if (!name) {
      return;
    }
    const selector = `[name="${CSS.escape(name)}"]`;
    const replacement = document.querySelector(selector);
    if (!(replacement instanceof HTMLElement)) {
      return;
    }
    replacement.focus();
    if (replacement instanceof HTMLInputElement || replacement instanceof HTMLTextAreaElement) {
      replacement.selectionStart = replacement.value.length;
      replacement.selectionEnd = replacement.value.length;
    }
  }

  function swapShellFromHtml(markup) {
    const parser = new DOMParser();
    const nextDocument = parser.parseFromString(markup, "text/html");
    const nextHeader = nextDocument.querySelector(".shell-header");
    const nextMain = nextDocument.querySelector("main");
    const currentHeader = document.querySelector(".shell-header");
    const currentMain = document.querySelector("main");
    if (!nextHeader || !nextMain || !currentHeader || !currentMain) {
      throw new Error("Unable to refresh Experiment page shell.");
    }
    currentHeader.outerHTML = nextHeader.outerHTML;
    currentMain.outerHTML = nextMain.outerHTML;
    if (nextDocument.title) {
      document.title = nextDocument.title;
    }
    syncOperatingModeFields(document);
  }

  async function submitAsyncForm(form, submitter) {
    if (!form.reportValidity()) {
      syncOperatingModeFields(form);
      return;
    }
    if (form.dataset.submitting === "true") {
      return;
    }
    form.dataset.submitting = "true";
    const preservedValues = collectAsyncFormState(form);
      const activeName =
        document.activeElement instanceof HTMLElement && "name" in document.activeElement
          ? document.activeElement.getAttribute("name")
        : null;
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    try {
      const action = submitter?.formAction || form.action || window.location.href;
      const method = (submitter?.formMethod || form.method || "post").toUpperCase();
      const formData = new FormData(form);
      const body = new URLSearchParams();
      for (const [key, value] of formData.entries()) {
        body.append(key, String(value));
      }
      const response = await fetch(action, {
        method,
        body,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "IRCPUiShell",
        },
        redirect: "follow",
      });
      const markup = await response.text();
      swapShellFromHtml(markup);
      restoreAsyncFormState(preservedValues);
      syncOperatingModeFields(document);
      history.replaceState({}, "", response.url);
      window.scrollTo(scrollX, scrollY);
      restoreFocus(activeName);
    } finally {
      form.dataset.submitting = "false";
    }
  }

  document.addEventListener("submit", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLFormElement) || target.dataset.asyncForm !== "true") {
      return;
    }
    event.preventDefault();
    submitAsyncForm(target, event.submitter instanceof HTMLElement ? event.submitter : null);
  });

  document.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) {
      return;
    }
    if (!operatingModeFieldNames.includes(target.name)) {
      return;
    }
    const form = target.closest('form[data-async-form="true"]');
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    syncOperatingModeFields(form);
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) {
      return;
    }
    if (!operatingModeFieldNames.includes(target.name)) {
      return;
    }
    const form = target.closest('form[data-async-form="true"]');
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    syncOperatingModeFields(form);
  });

  syncOperatingModeFields(document);
})();
</script>
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
    {APP_SHELL_SCRIPT}
  </body>
</html>"""


def render_header(header: HeaderStatus) -> str:
    scenarios = "".join(
        (
            f'<a class="scenario-chip{" active" if option.active else ""}" '
            f'href="/experiment?scenario={escape(option.scenario_id)}">{escape(option.label)}</a>'
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
    summary = f"<div>{escape(header.summary)}</div>" if header.summary else ""
    scenario_row = f'<div class="scenario-row">{scenarios}</div>' if scenarios else ""
    nav_row = f'<div class="nav-row">{navigation}</div>' if navigation else ""
    badge_row = f'<div class="badge-row">{badges}</div>' if badges else ""
    return f"""
    <header class="shell-header">
      <h1>{escape(header.title)}</h1>
      {summary}
      {scenario_row}
      {nav_row}
      {badge_row}
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
    results_handoff = render_surface_handoff(page.results_handoff, scenario_id)
    return f"""
    <div class="page-stack">
      {render_page_state(page.state)}
      {results_handoff}
      {render_operate_panel(page.session_panel, scenario_id)}
      {render_operate_panel(page.laser_panel, scenario_id)}
      <section class="panel-grid">
        {render_operate_panel(page.ndyag_panel, scenario_id)}
        {render_operate_panel(page.acquisition_panel, scenario_id)}
      </section>
      {render_operate_panel(page.run_panel, scenario_id)}
    </div>"""


def render_operate_panel(panel: OperatePanelModel, scenario_id: str) -> str:
    fields = "".join(render_form_field(field) for field in (*panel.fields, *panel.conditional_fields))
    disclosures = "".join(render_operate_disclosure(disclosure) for disclosure in panel.disclosures)
    header_actions = "".join(render_action_button(button, scenario_id) for button in panel.header_actions)
    actions = "".join(render_action_button(button, scenario_id) for button in panel.actions)
    status_items = "".join(render_status_item(item) for item in panel.status_items)
    actions_markup = f'<div class="action-row">{actions}</div>' if actions else ""
    status_markup = f'<div class="status-grid">{status_items}</div>' if status_items else ""
    footer_callouts = render_callouts(panel.footer_callouts)
    notes = "".join(f"<li>{escape(note)}</li>" for note in panel.notes)
    notes_markup = f'<ul class="notes-list">{notes}</ul>' if notes else ""
    if panel.field_columns == 3:
        field_grid_class = "field-grid three-column"
    elif panel.field_columns == 2:
        field_grid_class = "field-grid two-column"
    else:
        field_grid_class = "field-grid"
    form_action = f' action="{escape(panel.form_action)}"' if panel.form_action else ""
    return f"""
    <section class="panel state-accent">
      <form method="post"{form_action} data-async-form="true">
        <div class="panel-header-row">
          <div class="panel-heading">
            <h3>{escape(panel.title)}</h3>
          </div>
          <div class="panel-header-actions">{header_actions}</div>
        </div>
        {render_page_state(panel.state)}
        <input type="hidden" name="scenario" value="{escape(scenario_id)}">
        <div class="{field_grid_class}">{fields}</div>
        {disclosures}
        {actions_markup}
      </form>
      {status_markup}
      {notes_markup}
      {footer_callouts}
    </section>"""


def render_operate_disclosure(disclosure: OperateDisclosureModel) -> str:
    if disclosure.field_columns == 3:
        field_grid_class = "field-grid three-column"
    elif disclosure.field_columns == 2:
        field_grid_class = "field-grid two-column"
    else:
        field_grid_class = "field-grid"
    fields = "".join(render_form_field(field) for field in disclosure.fields)
    notes = "".join(f"<li>{escape(note)}</li>" for note in disclosure.notes)
    notes_markup = f'<ul class="notes-list">{notes}</ul>' if notes else ""
    open_attr = " open" if disclosure.open_by_default else ""
    subtitle = f'<p class="panel-subtitle">{escape(disclosure.subtitle)}</p>' if disclosure.subtitle else ""
    return f"""
    <details class="accordion"{open_attr}>
      <summary>{escape(disclosure.title)}</summary>
      {subtitle}
      <div class="{field_grid_class}">{fields}</div>
      {notes_markup}
    </details>"""


def render_action_button(button: ActionButtonModel, scenario_id: str) -> str:
    hidden_fields = "".join(
        f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'
        for name, value in button.hidden_fields
    )
    helper = f'<span class="button-note">{escape(button.helper_text)}</span>' if button.helper_text else ""
    tone_class = "" if button.tone == "primary" else f" {escape(button.tone)}"
    hidden_attr = " hidden" if button.hidden else ""
    return (
        f'<div data-action-button="{escape(button.action)}"{hidden_attr}>'
        f'{hidden_fields}<button type="submit" formaction="{escape(button.action)}"'
        f' class="{tone_class.strip()}" {"disabled" if button.disabled else ""}>'
        f"{escape(button.label)}</button>{helper}</div>"
    )


def render_surface_handoff(action: SurfaceActionModel | None, scenario_id: str) -> str:
    if action is None:
        return ""
    return f"""
    <section class="panel">
      <h3>Results Handoff</h3>
      <p class="panel-subtitle">Persisted review, visualizations, and export stay off the control surface.</p>
      {render_surface_action_row((action,), scenario_id)}
    </section>"""


def render_surface_action_row(actions: tuple[SurfaceActionModel, ...], scenario_id: str) -> str:
    if not actions:
        return ""
    rendered = "".join(render_surface_action(action, scenario_id) for action in actions)
    return f'<div class="toolbar-row">{rendered}</div>'


def render_surface_action(action: SurfaceActionModel, scenario_id: str) -> str:
    helper = f'<span class="button-note">{escape(action.helper_text)}</span>' if action.helper_text else ""
    tone_class = "" if action.tone == "primary" else f" {escape(action.tone)}"
    href = _surface_action_href(action, scenario_id)
    if action.disabled or href is None:
        control = f'<span class="button-link{tone_class} disabled">{escape(action.label)}</span>'
    else:
        control = f'<a class="button-link{tone_class}" href="{href}">{escape(action.label)}</a>'
    return f"<div>{control}{helper}</div>"


def _surface_action_href(action: SurfaceActionModel, scenario_id: str) -> str | None:
    if action.route is None:
        return None
    query_params = [f"scenario={escape(scenario_id)}"]
    if action.session_id:
        query_params.append(f"session_id={escape(action.session_id)}")
    for key, value in action.query_params:
        query_params.append(f"{escape(key)}={escape(value)}")
    return f'/{escape(action.route)}?{"&".join(query_params)}'


def render_status_item(item: StatusItemModel) -> str:
    detail = f'<div class="small">{escape(item.detail)}</div>' if item.detail else ""
    return (
        '<div class="status-item">'
        f'<div><strong>{escape(item.label)}</strong></div>'
        f'<div><span class="status-label {escape(item.tone)}">{escape(item.value)}</span></div>'
        f"{detail}</div>"
    )


def render_form_field(field: FormFieldModel) -> str:
    if field.field_type == "group_heading":
        help_markup = f'<div class="field-help">{escape(field.help_text)}</div>' if field.help_text else ""
        return (
            f'<div class="field-group-heading"><strong>{escape(field.label)}</strong>{help_markup}</div>'
        )
    if field.field_type == "select":
        options = "".join(
            f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>{escape(option.label)}</option>'
            for option in field.options
        )
        label = f'{escape(field.section_label)} / {escape(field.label)}' if field.section_label else escape(field.label)
        auto_submit = ' onchange="this.form.requestSubmit()"' if field.auto_submit and not field.disabled else ""
        control = (
            f'<label for="{escape(field.name)}">{label}</label>'
            f'<select id="{escape(field.name)}" name="{escape(field.name)}" {"disabled" if field.disabled else ""}{auto_submit}>{options}</select>'
        )
    elif field.field_type == "textarea":
        label = f'{escape(field.section_label)} / {escape(field.label)}' if field.section_label else escape(field.label)
        auto_submit = ' onchange="this.form.requestSubmit()"' if field.auto_submit and not field.disabled else ""
        read_only = " readonly" if field.read_only else ""
        control = (
            f'<label for="{escape(field.name)}">{label}</label>'
            f'<textarea id="{escape(field.name)}" name="{escape(field.name)}" placeholder="{escape(field.placeholder)}" '
            f'{"disabled" if field.disabled else ""}{read_only}{auto_submit}>{escape(field.value)}</textarea>'
        )
    elif field.field_type == "checkbox":
        auto_submit = ' onchange="this.form.requestSubmit()"' if field.auto_submit and not field.disabled else ""
        control = (
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f'<input id="{escape(field.name)}" name="{escape(field.name)}" type="checkbox" value="1" '
            f'{"checked" if field.checked else ""} {"disabled" if field.disabled else ""}{auto_submit}>'
        )
    else:
        field_type = "number" if field.field_type == "number" else "text"
        label = f'{escape(field.section_label)} / {escape(field.label)}' if field.section_label else escape(field.label)
        auto_submit = ' onchange="this.form.requestSubmit()"' if field.auto_submit and not field.disabled else ""
        read_only = " readonly" if field.read_only else ""
        min_attr = f' min="{escape(field.min_value)}"' if field.min_value else ""
        max_attr = f' max="{escape(field.max_value)}"' if field.max_value else ""
        step_attr = f' step="{escape(field.step)}"' if field.step else ""
        control = (
            f'<label for="{escape(field.name)}">{label}</label>'
            f'<input id="{escape(field.name)}" name="{escape(field.name)}" type="{field_type}" value="{escape(field.value)}" '
            f'placeholder="{escape(field.placeholder)}" {"disabled" if field.disabled else ""}{read_only}{min_attr}{max_attr}{step_attr}{auto_submit}>'
        )
    help_markup = f'<div class="field-help">{escape(field.help_text)}</div>' if field.help_text else ""
    field_class = "field checkbox-field" if field.field_type == "checkbox" else "field"
    if field.full_width:
        field_class += " full-width"
    hidden_attr = " hidden" if field.hidden else ""
    data_attr = f' data-field-name="{escape(field.name)}"' if field.name else ""
    return f'<div class="{field_class}"{data_attr}{hidden_attr}>{control}{help_markup}</div>'


def render_results_page(page: ResultsPageModel, scenario_id: str) -> str:
    sessions = "".join(render_session_card(card, scenario_id, target="results") for card in page.sessions) or (
        '<div class="placeholder-copy">No saved sessions are available yet.</div>'
    )
    filters = render_results_filters(page.filters, page.selected_session, scenario_id)
    selected_context = render_results_selected_context(page, scenario_id)
    details = "".join(render_summary_panel(panel) for panel in page.detail_panels) or (
        '<div class="placeholder-copy">Select a session to inspect the saved summary.</div>'
    )
    artifacts = "".join(render_summary_panel(panel) for panel in page.artifact_panels) or (
        '<div class="placeholder-copy">Artifact groups appear after a session is selected.</div>'
    )
    artifact_rows = render_results_artifact_registry(page.artifact_rows, scenario_id)
    visualizations = "".join(render_summary_panel(panel) for panel in page.visualization_panels) or (
        '<div class="placeholder-copy">Select a session to review persisted plots and overlay context.</div>'
    )
    trace_previews = "".join(render_results_trace_preview(preview) for preview in page.trace_previews) or (
        '<div class="placeholder-copy">Select a session with saved raw artifacts to preview persisted traces.</div>'
    )
    storage = "".join(render_summary_panel(panel) for panel in page.storage_panels)
    exports = "".join(render_summary_panel(panel) for panel in page.export_panels) or (
        '<div class="placeholder-copy">Select a session to inspect download readiness and export scope.</div>'
    )
    events = "".join(render_event_row(item) for item in page.event_log) or (
        '<div class="placeholder-copy">No saved event timeline is available for this selection.</div>'
    )
    export_actions = render_surface_action_row(page.export_actions, scenario_id)
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {filters}
        {render_page_state(page.state)}
      </section>
      {render_callouts(page.callouts)}
      <section class="panel-grid">
        <div class="panel">
          <h3>Recent Sessions</h3>
          <p class="panel-subtitle">Review the saved session catalog, then pin one run for deeper inspection.</p>
          {sessions}
        </div>
        {selected_context}
      </section>
      <section class="panel-grid">
        <div class="panel">
          <h3>Overview and Provenance</h3>
          <p class="panel-subtitle">Human-readable summary of manifest state, replay context, and saved provenance.</p>
          <div class="panel-grid">{details}</div>
        </div>
        <div class="panel">
          <h3>Storage Details</h3>
          <p class="panel-subtitle">Durable paths and saved session context for the current selection.</p>
          {storage or '<div class="placeholder-copy">Storage details appear when a session is selected.</div>'}
        </div>
      </section>
      <section class="panel">
        <h3>Visualization and Trace Review</h3>
        <p class="panel-subtitle">Persisted plots, traces, and marker context live here instead of on Experiment.</p>
        <div class="panel-grid">{visualizations}</div>
        <div class="trace-grid">{trace_previews}</div>
      </section>
      <section class="panel">
        <h3>Artifacts and Provenance</h3>
        <p class="panel-subtitle">Saved raw, processed, analysis, and export groups remain separated and downloadable when files are present.</p>
        <div class="panel-grid">{artifacts}</div>
        {artifact_rows}
      </section>
      <section class="panel-grid">
        <div class="panel">
          <h3>Download and Export</h3>
          <p class="panel-subtitle">Downloads run from persisted session truth. Unsupported actions stay visibly disabled.</p>
          {export_actions}
          <div class="panel-grid">{exports}</div>
        </div>
        <div class="panel">
          <h3>Session Activity</h3>
          <p class="panel-subtitle">Persisted run events for the selected session.</p>
          {events}
        </div>
      </section>
    </div>"""


def render_results_filters(
    filters: ResultsFilterModel,
    selected_session: SessionSummaryCard | None,
    scenario_id: str,
) -> str:
    search_value = escape(filters.search_value)
    selected_session_id = selected_session.session_id if selected_session is not None else "__none__"
    status_options = "".join(
        f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>{escape(option.label)}</option>'
        for option in filters.status_options
    )
    sort_options = "".join(
        f'<option value="{escape(option.value)}" {"selected" if option.selected else ""}>{escape(option.label)}</option>'
        for option in filters.sort_options
    )
    return f"""
    <form method="get" action="/results" class="results-filter-form">
      <input type="hidden" name="scenario" value="{escape(scenario_id)}">
      <input type="hidden" name="session_id" value="{escape(selected_session_id)}">
      <div class="results-filter-grid">
        <div class="field">
          <label for="results-search">Search Sessions</label>
          <input id="results-search" name="search" type="text" value="{search_value}" placeholder="session id or recipe title">
        </div>
        <div class="field">
          <label for="results-status">Status</label>
          <select id="results-status" name="status">{status_options}</select>
        </div>
        <div class="field">
          <label for="results-sort">Sort</label>
          <select id="results-sort" name="sort">{sort_options}</select>
        </div>
      </div>
      <div class="toolbar-row">
        <button type="submit" class="secondary">Apply Filters</button>
        <a class="button-link ghost" href="/results?scenario={escape(scenario_id)}">Reset</a>
        <span class="filter-summary">Showing {filters.visible_session_count} of {filters.total_session_count} saved sessions.</span>
      </div>
    </form>"""


def render_results_selected_context(page: ResultsPageModel, scenario_id: str) -> str:
    if page.selected_session is None:
        return """
        <div class="panel">
          <h3>Selected Session</h3>
          <p class="panel-subtitle">Choose one saved session to inspect metrics, traces, artifacts, and downloads.</p>
          <div class="placeholder-copy">No session is currently selected.</div>
        </div>"""

    card = page.selected_session
    tone = "good" if card.replay_ready else ("warn" if card.failure_reason_label is None else "bad")
    failure = (
        f'<div class="small">Failure reason: {escape(card.failure_reason_label)}</div>'
        if card.failure_reason_label
        else ""
    )
    metrics = "".join(render_status_item(item) for item in page.selected_session_metrics) or (
        '<div class="placeholder-copy">No session metrics are available.</div>'
    )
    actions = render_surface_action_row(page.toolbar_actions, scenario_id)
    return f"""
    <div class="panel selection-context">
      <div>
        <h3>Selected Session</h3>
        <p class="panel-subtitle">Pinned saved-session context for trace review, artifacts, and follow-on actions.</p>
      </div>
      <div class="session-card selected">
        <div><strong>{escape(card.recipe_title)}</strong></div>
        <div><span class="status-label {tone}">{escape(card.status_label)}</span></div>
        <div class="small">Session {escape(card.session_id)} updated {escape(card.updated_at.isoformat())}</div>
        <div class="small">Primary raw {card.primary_raw_artifact_count} | Secondary monitor {card.secondary_monitor_artifact_count}</div>
        <div class="small">Processed {card.processed_artifact_count} | Analysis {card.analysis_artifact_count} | Export {card.export_artifact_count}</div>
        <div class="small">Events {card.event_count} | Replay {'ready' if card.replay_ready else 'unavailable'}</div>
        {failure}
      </div>
      <div class="results-action-bar">
        <form method="post" action="/experiment/session/open">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <input type="hidden" name="recent_session_id" value="{escape(card.session_id)}">
          <button type="submit" class="secondary">Reopen in Experiment</button>
        </form>
        {actions}
      </div>
      <div class="metric-grid">{metrics}</div>
    </div>"""


def render_results_trace_preview(preview: ResultsTracePreviewModel) -> str:
    chart = (
        f'<div class="trace-chart"><svg viewBox="0 0 320 132" preserveAspectRatio="none"><polyline points="{escape(preview.polyline_points or "")}"></polyline></svg></div>'
        if preview.polyline_points
        else ""
    )
    notes = "".join(f"<li>{escape(line)}</li>" for line in preview.note_lines)
    notes_markup = f'<ul class="detail-list">{notes}</ul>' if notes else ""
    return f"""
    <div class="panel trace-card">
      <div>
        <h4>{escape(preview.title)}</h4>
        <p class="panel-subtitle">{escape(preview.subtitle)}</p>
      </div>
      {render_page_state(preview.state)}
      {chart}
      <div class="trace-meta">
        <div><strong>{escape(preview.sample_count_label)}</strong></div>
        <div class="small">{escape(preview.axis_label)}</div>
        <div class="small">Axis: {escape(preview.axis_start_label)} to {escape(preview.axis_end_label)}</div>
        <div class="small">Value: {escape(preview.value_min_label)} to {escape(preview.value_max_label)}</div>
      </div>
      {notes_markup}
    </div>"""


def render_results_artifact_registry(rows: tuple[ResultsArtifactRowModel, ...], scenario_id: str) -> str:
    if not rows:
        return '<div class="placeholder-copy">Structured artifact entries appear when a session is selected.</div>'
    rendered = "".join(render_results_artifact_row(row, scenario_id) for row in rows)
    return f'<div class="artifact-list">{rendered}</div>'


def render_results_artifact_row(row: ResultsArtifactRowModel, scenario_id: str) -> str:
    details = "".join(f"<li>{escape(detail)}</li>" for detail in row.details)
    details_markup = f'<ul class="detail-list">{details}</ul>' if details else ""
    action = render_surface_action(row.download_action, scenario_id) if row.download_action is not None else ""
    return f"""
    <div class="artifact-row">
      <div class="artifact-row-head">
        <div class="artifact-row-meta">
          <div><strong>{escape(row.kind_label)}</strong> · {escape(row.artifact_id)}</div>
          <div class="small">{escape(row.source_label)}</div>
          <div class="small">{escape(row.stream_label)}</div>
        </div>
        <div>{action}</div>
      </div>
      <div class="small">Created {escape(row.created_at.isoformat())} · {escape(row.records_label)}</div>
      <div class="artifact-row-path"><code>{escape(row.path)}</code></div>
      {details_markup}
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
    evaluation = "".join(render_summary_panel(panel) for panel in page.evaluation_panels) or (
        '<div class="placeholder-copy">Select a session to stage reprocessing, comparison, and metric work.</div>'
    )
    tables = "".join(render_table_section(table) for table in page.tables)
    toolbar = render_surface_action_row(page.toolbar_actions, scenario_id)
    evaluation_actions = render_surface_action_row(page.evaluation_actions, scenario_id)
    return f"""
    <div class="page-stack">
      <section class="hero">
        <div class="surface-badges">{"".join(render_badge(badge) for badge in page.surface_badges)}</div>
        <h2>{escape(page.title)}</h2>
        <p class="hero-subtitle">{escape(page.subtitle)}</p>
        {toolbar}
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
          <h3>Reprocessing and Comparison</h3>
          <p class="panel-subtitle">Scientific evaluation begins from a selected saved session, not from live control state.</p>
          {evaluation_actions}
          <div class="panel-grid">{evaluation}</div>
        </div>
      </section>
      <section class="panel">
        <h3>Saved-Session Inputs</h3>
        <p class="panel-subtitle">Analyze reads persisted inputs, upstream outputs, and replay readiness before any evaluation step.</p>
        <div class="panel-grid">{summaries}</div>
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
      <div class="small">{escape(item.timestamp.astimezone().strftime("%H:%M:%S"))}</div>
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
    <div class="session-card{' selected' if card.selected else ''}">
      <div><strong>{escape(card.recipe_title)}</strong></div>
      <div><span class="status-label {tone}">{escape(card.status_label)}</span></div>
      <div class="small">Session {escape(card.session_id)} updated {escape(card.updated_at.isoformat())}</div>
      <div class="small">Primary raw {card.primary_raw_artifact_count} | Secondary monitor {card.secondary_monitor_artifact_count}</div>
      <div class="small">Processed {card.processed_artifact_count} | Analysis {card.analysis_artifact_count} | Export {card.export_artifact_count}</div>
      <div class="small">Events {card.event_count} | Replay {'ready' if card.replay_ready else 'unavailable'}</div>
      {failure}
      <div class="toolbar-row">
        <form method="post" action="/experiment/session/open">
          <input type="hidden" name="scenario" value="{escape(scenario_id)}">
          <input type="hidden" name="recent_session_id" value="{escape(card.session_id)}">
          <button type="submit" class="secondary">Open in Experiment</button>
        </form>
        <a class="button-link {'secondary' if target == 'results' else 'ghost'}" href="/results?scenario={escape(scenario_id)}&session_id={escape(card.session_id)}">Open Results</a>
        <a class="button-link ghost" href="{analyze_link}">Analyze</a>
      </div>
    </div>"""
