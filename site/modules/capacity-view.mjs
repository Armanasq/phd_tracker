const format = n => Number.isFinite(n) ? Number(n).toLocaleString("en-GB", {maximumFractionDigits: 2}) : "Unknown";

export function capacityCsv(report) {
 if (!report || !Array.isArray(report.scheduled)) throw new TypeError("Missing schedule");
 const keys = ["date", "task_type", "task_id", "application_id", "hours"];
 const quote = value => {
  const raw = String(value ?? "");
  const safe = /^[\s\u0000-\u001f]*[=+\-@\t\r]/.test(raw) ? "'" + raw : raw;
  return '"' + safe.replaceAll('"', '""') + '"';
 };
 const blocks = [...report.scheduled, ...(report.scheduled_shared_documents || [])];
 return [keys.map(quote).join(","), ...blocks.map(row => keys.map(key => quote(row[key])).join(","))].join("\r\n");
}

export function renderCapacityReport({report, esc, byId, button}) {
 const base = report.baseline || {}, combined = report.with_shared_documents || {};
 const metric = ([name, value, note]) => '<div><strong>' + esc(value) + '</strong><span>' + esc(name) + '</span><small>' + esc(note) + '</small></div>';
 const stats = [
  ["Application effort", format(base.total_work_hours) + "h", "Owner estimates; excludes shared documents"],
  ["Shared preparation", format(Number(combined.total_work_hours || 0) - Number(base.total_work_hours || 0)) + "h", "One task per known document type"],
  ["Base shortfall", format(base.total_hours_unallocated) + "h", "Before shared preparation"],
  ["Combined shortfall", format(combined.total_hours_unallocated) + "h", "Including estimated shared preparation"],
 ];
 const state = report.status === "over_capacity" ? "Insufficient entered capacity" : report.status === "unresolved_inputs" ? "Unquantified work remains" : "No overload detected within entered assumptions";
 const label = item => item.task_type === "document" ? "Shared document: " + String(item.task_id || "").replace(/^document:/, "").replaceAll("_", " ") : byId(item.application_id)?.name || item.application_id || item.task_id;
 const rows = (items, render) => items.length ? items.slice(0, 24).map(render).join("") : '<p class="os-empty">No records in this category.</p>';
 const combinedUnallocated = [...(report.unallocated || []), ...(report.unallocated_shared_documents || [])];
 const shortfall = rows(combinedUnallocated, item => '<div class="ops-row"><div><strong>' + esc(label(item)) + '</strong><small>' + esc(format(item.hours_unallocated)) + 'h unallocated by ' + esc(item.deadline) + '</small></div></div>');
 const bottlenecks = rows(report.deadline_bottlenecks || [], item => '<div class="ops-row"><div><strong>' + esc(item.deadline) + '</strong><small>' + esc(format(item.due_work_hours)) + 'h due; ' + esc(format(item.available_hours)) + 'h cumulative assumed capacity</small></div><span class="os-badge warn">' + esc(format(item.minimum_shortfall_hours)) + 'h short</span></div>');
 const unknown = [
  ...(report.unknown_effort_or_date || []).map(item => ({title:byId(item.application_id)?.name || item.application_id, note:item.reason})),
  ...(report.unknown_document_effort || []).map(item => ({title:String(item.document).replaceAll("_", " "), note:item.applications + " applications; shared effort unknown"})),
  ...(report.unconfirmed_document_requirements || []).map(id => ({title:byId(id)?.name || id, note:"Official document inventory not recorded"})),
 ];
 const shared = Object.entries(report.shared_document_hours || {}).map(([key, hours]) => '<span class="os-badge">' + esc(key.replaceAll("_", " ")) + ' · ' + esc(format(hours)) + 'h</span>').join(" ");
 return '<div class="os-hint" role="status"><strong>' + esc(state) + '</strong> · ' + esc(report.caution || "Interpret provisionally.") + '</div>' +
  '<div class="os-kpi-strip ops-metrics">' + stats.map(metric).join("") + '</div>' +
  '<div class="ops-columns"><section class="os-panel"><div class="os-panel-heading"><div><h2>Deadline bottlenecks</h2><p>Known work compared with the cumulative shared time budget.</p></div></div><div class="ops-rows">' + bottlenecks + '</div></section>' +
  '<section class="os-panel"><div class="os-panel-heading"><div><h2>Unallocated work</h2><p>Combined scenario; application tasks plus estimated shared document work.</p></div></div><div class="ops-rows">' + shortfall + '</div></section></div>' +
  '<section class="os-panel"><div class="os-panel-heading"><div><h2>Unquantified work</h2><p>Unknown does not mean zero hours. Confirm missing source evidence and actual effort.</p></div></div><div class="ops-rows">' + rows(unknown, item => '<div class="ops-row"><div><strong>' + esc(item.title) + '</strong><small>' + esc(item.note) + '</small></div></div>') + '</div></section>' +
  '<section class="os-panel"><div class="os-panel-heading"><div><h2>Shared preparation and export</h2><p>Effort may overlap with application estimates; documents may require institutional customization.</p></div></div><div class="os-actions" style="padding:14px 18px">' + (shared || '<span class="os-meta">No shared-document estimates entered.</span>') + button("Export allocation CSV", "capacity-export", "", "quiet") + '</div><details style="padding:0 18px 18px"><summary>Planning assumptions</summary><ul>' + (report.assumptions || []).map(x => '<li>' + esc(x) + '</li>').join("") + '</ul></details></section>' +
 (report.allocations_truncated ? '<p class="os-hint">Some allocation blocks were omitted from the preview and CSV. Summary totals still use the full computed allocation.</p>' : '');
}
