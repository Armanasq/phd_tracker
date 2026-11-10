const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export function observationSummary(records) {
  if (!Array.isArray(records)) throw new TypeError("Observation records must be an array");
  const latest = new Map();
  const observedChanges = new Set();
  const pendingReview = new Map();
  for (const item of records) {
    if (!item || typeof item !== "object" || typeof item.application_id !== "string" || typeof item.source_url !== "string") continue;
    const key = JSON.stringify([item.application_id, item.source_url]);
    if (item.drift === "source_bytes_changed_needs_review") {
      observedChanges.add(key);
      if (item.review_decision !== "reviewed_no_fact_change") {
        const previousPending = pendingReview.get(key);
        if (!previousPending || String(item.observed_at ?? "") > String(previousPending.observed_at ?? "")) pendingReview.set(key,item);
      }
    }
    const previous = latest.get(key);
    if (!previous || String(item.observed_at ?? "") > String(previous.observed_at ?? "")) latest.set(key, item);
  }
  const counts = {changed:0,pending:0,unavailable:0,unchanged:0,baseline:0,legacy:0};
  const candidates = [...latest.entries()].map(([key,item])=>({...item,change_seen_in_loaded_history:observedChanges.has(key),pending_review:pendingReview.get(key)||null}));
  for (const item of candidates) {
    if (item.change_seen_in_loaded_history) counts.changed++;
    if (item.pending_review) counts.pending++;
    if (item.drift === "unavailable_no_source_conclusion") counts.unavailable++;
    else if (item.drift === "unchanged_bytes") counts.unchanged++;
    else if (item.drift === "baseline_only") counts.baseline++;
    else if (item.drift !== "source_bytes_changed_needs_review") counts.legacy++;
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
    if(selected==="changed")return x.pending_review!==null;
    if(selected==="unavailable")return x.drift==="unavailable_no_source_conclusion";
    if(selected==="unchanged")return x.drift==="unchanged_bytes";
    if(selected==="baseline")return x.drift==="baseline_only";
    return !["source_bytes_changed_needs_review","unavailable_no_source_conclusion","unchanged_bytes","baseline_only"].includes(x.drift);
  });
  const entries=list.slice(0,100).map(item=>{
    const url=observationLink(item.source_url);
    const title=esc(item.application_id.slice(0,120));
    const label=item.pending_review
      ? "Byte drift requires owner review · latest: "+driftLabel(item.drift)
      : item.change_seen_in_loaded_history
        ? "Earlier byte drift noted by owner · latest: "+driftLabel(item.drift)
        : driftLabel(item.drift);
    const pending=item.pending_review;
    const form=pending&&Number.isSafeInteger(pending.id)&&pending.id>0
      ? '<form class="os-form" data-os-form="source-review"><input type="hidden" name="observation_id" value="'+pending.id+'"><input type="hidden" name="expected_digest" value="'+esc(pending.content_sha256||"")+'"><label class="os-field"><span>Owner decision</span><select name="decision"><option value="needs_follow_up">Needs follow-up</option><option value="reviewed_no_fact_change">Inspected; no material claim change found</option></select></label><label class="os-field"><span>Review evidence and rationale</span><textarea name="note" rows="2" minlength="24" maxlength="1500" required placeholder="Record the primary evidence inspected and why this decision is justified."></textarea></label><button type="submit" class="os-btn quiet">Record owner review</button></form>'
      : "";
    return '<article class="os-ledger-row"><div><strong>'+title+'</strong><small>'+esc(item.observed_at||"Unknown time")+' · HTTP '+esc(item.http_status??"unavailable")+'</small>' +
      (url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Inspect recorded source</a>':'<small>Recorded URL unavailable or unsupported</small>')+
      '</div><span class="os-meta">'+esc(label)+'</span>'+form+'</article>';
  }).join("");
  const kpi=(name,value,description)=>'<div><strong>'+value+'</strong><span>'+name+'</span><small>'+description+'</small></div>';
  return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE EVIDENCE MONITORING</div><h1>Source observations</h1>'+
    '<p>Recorded official-source byte comparisons. No automatic eligibility or deadline conclusions.</p></div><div class="os-head-actions">'+
    '<button type="button" class="os-btn quiet" data-os-action="refresh-observations"'+(loading?' disabled':'')+'>Refresh history</button></div></div>'+
    '<section class="os-panel"><div class="os-kpi-strip">'+
    kpi("Recent sources",data.sources,"Latest result in the loaded history")+
    kpi("Review pending",data.counts.pending,"Unresolved drift in loaded history")+
    kpi("Unavailable",data.counts.unavailable,"Latest observation unavailable")+
    kpi("Unknown",data.counts.legacy,"Latest observation unclassified")+
    '</div><p class="os-footnote">A later byte-identical fetch does not clear an earlier change. An owner review records an attestation, not verified institutional facts. This view covers only the bounded loaded history. An initial baseline is not proof of unchanged institutional facts.</p></section>'+
    '<section class="os-panel"><div class="os-panel-heading"><div><h2>Review queue</h2><p>Each source is shown once at its latest observation within the loaded history. Older records remain in private SQLite.</p></div></div>'+
    '<label class="os-field"><span>Observation class</span><select data-os-observation-filter aria-label="Filter source observations by outcome">'+
    [["all","All"],["changed","Pending drift reviews"],["unavailable","Unavailable"],["unchanged","Unchanged bytes"],["baseline","Initial baselines"],["legacy","Legacy unknown"]].map(([value,label])=>
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
