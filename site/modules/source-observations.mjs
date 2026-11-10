const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export function observationSummary(records) {
  if (!Array.isArray(records)) throw new TypeError("Observation records must be an array");
  const latest = new Map();
  const observedChanges = new Set();
  for (const item of records) {
    if (!item || typeof item !== "object" || typeof item.application_id !== "string" || typeof item.source_url !== "string") continue;
    const key = JSON.stringify([item.application_id, item.source_url]);
    if (item.drift === "source_bytes_changed_needs_review") observedChanges.add(key);
    const previous = latest.get(key);
    if (!previous || String(item.observed_at ?? "") > String(previous.observed_at ?? "")) latest.set(key, item);
  }
  const counts = {changed:0,unavailable:0,unchanged:0,baseline:0,legacy:0};
  const candidates = [...latest.entries()].map(([key,item])=>({...item,change_seen_in_loaded_history:observedChanges.has(key)}));
  for (const item of candidates) {
    if (item.change_seen_in_loaded_history) counts.changed++;
    else if (item.drift === "unavailable_no_source_conclusion") counts.unavailable++;
    else if (item.drift === "unchanged_bytes") counts.unchanged++;
    else if (item.drift === "baseline_only") counts.baseline++;
    else counts.legacy++;
  }
  return {sources:latest.size,counts,latest:candidates.sort((a,b)=>String(b.observed_at??"").localeCompare(String(a.observed_at??"")))};
}

export function observationLink(value) {
  try {
    const url = new URL(String(value));
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password || url.search || url.hash) return "";
    if (["localhost","127.0.0.1","[::1]"].includes(url.hostname.toLowerCase())) return "";
    return url.href;
  } catch {return "";}
}

const driftLabel = value => ({
  source_bytes_changed_needs_review:"Bytes changed · manual review",
  unavailable_no_source_conclusion:"Source unavailable · no conclusion",
  unchanged_bytes:"Byte-identical · facts unverified",
  baseline_only:"Initial baseline · no comparison"
})[value] || "Legacy observation · classification unknown";

export function renderSourceObservations({records=[],loading=false,error="",filter="all"}={}) {
  const data=observationSummary(records);
  const choices=new Set(["all","changed","unavailable","unchanged","baseline","legacy"]);
  const selected=choices.has(filter)?filter:"all";
  const list=data.latest.filter(x=>{
    if(selected==="all")return true;
    if(selected==="changed")return x.change_seen_in_loaded_history;
    if(selected==="unavailable")return x.drift==="unavailable_no_source_conclusion";
    if(selected==="unchanged")return x.drift==="unchanged_bytes"&&!x.change_seen_in_loaded_history;
    if(selected==="baseline")return x.drift==="baseline_only";
    return !["source_bytes_changed_needs_review","unavailable_no_source_conclusion","unchanged_bytes","baseline_only"].includes(x.drift);
  });
  const entries=list.slice(0,100).map(item=>{
    const url=observationLink(item.source_url);
    const title=esc(item.application_id.slice(0,120));
    const label=item.change_seen_in_loaded_history&&item.drift!=="source_bytes_changed_needs_review"
      ? "Earlier byte drift in loaded history · review status unknown; latest: "+driftLabel(item.drift)
      : driftLabel(item.drift);
    return '<article class="os-ledger-row"><div><strong>'+title+'</strong><small>'+esc(item.observed_at||"Unknown time")+' · HTTP '+esc(item.http_status??"unavailable")+'</small>' +
      (url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Inspect recorded source</a>':'<small>Recorded URL unavailable or unsupported</small>')+
      '</div><span class="os-meta">'+esc(label)+'</span></article>';
  }).join("");
  const kpi=(name,value,description)=>'<div><strong>'+value+'</strong><span>'+name+'</span><small>'+description+'</small></div>';
  return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE EVIDENCE MONITORING</div><h1>Source observations</h1>'+
    '<p>Recorded official-source byte comparisons. No automatic eligibility or deadline conclusions.</p></div><div class="os-head-actions">'+
    '<button type="button" class="os-btn quiet" data-os-action="refresh-observations"'+(loading?' disabled':'')+'>Refresh history</button></div></div>'+
    '<section class="os-panel"><div class="os-kpi-strip">'+
    kpi("Recent sources",data.sources,"Latest result in the loaded history")+
    kpi("Drift seen",data.counts.changed,"Changes in loaded history; review unknown")+
    kpi("Unavailable",data.counts.unavailable,"No source conclusion")+
    kpi("Unknown",data.counts.legacy,"Legacy/unclassified")+
    '</div><p class="os-footnote">A later byte-identical fetch does not clear an earlier change. Review resolution is not tracked; this view covers only the bounded loaded history. An initial baseline is not proof of unchanged institutional facts.</p></section>'+
    '<section class="os-panel"><div class="os-panel-heading"><div><h2>Review queue</h2><p>Each source is shown once at its latest observation within the loaded history. Older records remain in private SQLite.</p></div></div>'+
    '<label class="os-field"><span>Observation class</span><select data-os-observation-filter aria-label="Filter source observations by outcome">'+
    [["all","All"],["changed","Byte drift in history"],["unavailable","Unavailable"],["unchanged","Unchanged bytes"],["baseline","Initial baselines"],["legacy","Legacy unknown"]].map(([value,label])=>
      '<option value="'+value+'"'+(selected===value?' selected':'')+'>'+label+'</option>').join("")+
    '</select></label>'+
    (error?'<p class="os-warning" role="alert">'+esc(error)+'</p>':'')+
    (loading?'<p class="os-note" role="status">Loading private observation history…</p>':'')+
    '<div class="os-ledger">'+(entries||'<p class="os-empty">'+(loading?"History request pending.":"No matching source observations are recorded.")+'</p>')+'</div></section>'+
    '<section class="os-panel"><div class="os-panel-heading"><div><h2>Run a new observation</h2><p>Source fetching is deliberate, server-side and limited to previously reviewed HTTPS sources.</p></div></div>'+
    '<div class="os-code">python -m phd_agents observe-sources --limit 8</div>'+
    '<div class="os-actions"><button type="button" class="os-btn quiet" data-os-action="copy-observer-command">Copy command</button></div>'+
    '<p class="os-footnote">Executing this command performs network requests. The workspace does not initiate collection automatically or promote altered evidence into verified application facts.</p></section></section>';
}
