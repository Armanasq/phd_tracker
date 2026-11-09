import {auditWorkspace, auditCategories, sourceCoverage} from "./assurance.mjs";

const labels={all:"All",deadline:"Deadlines",source:"Sources",documents:"Documents",submission:"Receipts",route:"Routes",status:"Status"};

export function renderAssurance({snapshot,records,today,filter="all",limit=75,escape,button,link}){
 const audited=auditWorkspace({...snapshot,records},today);
 const selected=auditCategories.includes(filter)?filter:"all";
 const filtered=selected==="all"?audited.queue:audited.queue.filter(item=>item.category===selected);
 const shown=filtered.slice(0,Math.max(1,limit));
 const summary=[
  [audited.totals.affected,"Applications with open checks"],
  [audited.totals.cutoffUnstructured,"Closing-hour proof not structured"],
  [audited.totals.unverified,"Evidence verification pending"],
  [audited.totals.documentsUnknown,"Document readiness unknown"],
  [audited.totals.documentsNotStarted,"Explicit document preparation gaps"],
  [audited.totals.receiptsAbsent,"Submitted without recorded receipt"]
 ];
 const failed=audited.providers.degraded;
 return '<div class="assurance-layout">'+
  '<div class="assurance-intro"><section class="assurance-note"><h2>Evidence freshness</h2><p>'+escape(audited.freshness.label)+'. '+audited.totals.tracked+' tracked opportunities and '+audited.totals.obligations+' review obligations. This is a deterministic audit of recorded evidence, not a current university portal check.</p></section>'+
  '<section class="assurance-note"><h2>Discovery coverage</h2><p>'+failed.length+' of '+audited.providers.total+' integrations degraded or unconfirmed. '+escape(failed.map(p=>p.name+" ("+p.health+")").join("; ")||"No degraded feeds reported")+'. Healthy feeds do not prove completeness.</p></section></div>'+
  '<div class="assurance-metrics">'+summary.map(([value,title])=>'<div class="assurance-metric"><strong>'+escape(value)+'</strong><span>'+escape(title)+'</span></div>').join("")+'</div>'+
  '<section class="assurance-panel"><div class="assurance-header"><div><h2>Proof obligations</h2><p>Prioritized by deadline proximity and evidence type. Applicant status is never inferred.</p></div>'+button("Export all checks","export-audit")+'</div>'+
  '<div class="assurance-filters" role="group" aria-label="Filter proof obligations">'+auditCategories.map(category=>'<button type="button" data-action="audit-filter" data-value="'+category+'" aria-pressed="'+(selected===category)+'">'+labels[category]+' · '+(category==="all"?audited.queue.length:audited.counts[category])+'</button>').join("")+'</div>'+
  (shown.length?'<ol class="assurance-list">'+shown.map(item=>'<li class="assurance-item"><span class="assurance-state '+item.urgency+'">'+escape(item.urgency)+'</span><div><h3>'+escape(item.title)+'</h3><p>'+escape(item.detail)+'</p><small>'+escape(item.record_name)+' · '+escape(item.record_id)+'</small></div><div class="assurance-links">'+button("Open record","record",item.record_id)+link(item.source_url,"Official source")+'</div></li>').join("")+'</ol>':'<p class="assurance-empty">No recorded checks in this category. This does not establish eligibility or completed applications.</p>')+
  '<div class="assurance-footer"><span>Showing '+shown.length+' of '+filtered.length+' in this category. Unknown states remain unknown.</span>'+(filtered.length>shown.length?button("Show next 75","audit-more"):"")+'</div></section></div>';
}

export function renderCoverage({snapshot,escape,link,repository}){
 const coverage=sourceCoverage(snapshot),totals=coverage.totals;
 const metrics=[
  [totals.tracked??snapshot.meta?.tracked??0,"Tracked applications"],
  [totals.research_candidates??snapshot.meta?.candidates??0,"Research candidates"],
  [totals.reviewed_opportunity_notes??"Unknown","Enriched programme records"],
  [totals.discovery_leads??snapshot.leads?.length??0,"Unpromoted discovery leads"],
  [totals.historical_exclusions??snapshot.archive?.length??0,"Historical exclusions"],
  [totals.task_projection??snapshot.tasks?.length??0,"Tasks in current projection"]
 ];
 const fileLink=path=>/^(?:data\/[A-Za-z0-9_./-]+|PhD_Action_List\.xlsx)$/.test(path)?repository+"/blob/main/"+path:"";
 const errors=Object.entries(coverage.discoveryErrors);
 return '<div class="assurance-layout">'+
  '<div class="assurance-metrics">'+metrics.map(([n,label])=>'<div class="assurance-metric"><strong>'+escape(n)+'</strong><span>'+escape(label)+'</span></div>').join("")+'</div>'+
  '<section class="assurance-panel"><div class="assurance-header"><div><h2>Original workbook coverage</h2><p>Last workbook structural audit: '+escape(coverage.asOf||"not recorded")+'. Counts refer to populated worksheet rows, not distinct PhD opportunities.</p></div>'+link(repository+"/blob/main/PhD_Action_List.xlsx","Full workbook")+'</div>'+
  '<div class="tablewrap"><table class="table assurance-table"><thead><tr><th>Worksheet</th><th>Populated rows</th><th>Due on audit date</th><th>Next 7 days on audit date</th></tr></thead><tbody>'+
  coverage.sheets.map(row=>'<tr><td>'+escape(row.name)+'</td><td>'+escape(row.populated_rows)+'</td><td>'+escape(row.today_count)+'</td><td>'+escape(row.next_7_count)+'</td></tr>').join("")+'</tbody></table></div>'+
  '<p class="assurance-footnote">The original action list, step timeline, research queue and exclusions contain different record types. They are not combined into the tracked-application count. Historical audit counts are not live deadlines.</p></section>'+
  '<section class="assurance-panel"><div class="assurance-header"><div><h2>Source and projection catalog</h2><p>Inspect the committed evidence layers and understand how each feeds the workspace.</p></div></div>'+
  '<div class="assurance-catalog">'+coverage.sources.map(file=>'<div class="assurance-source"><div><strong>'+escape(file.name)+'</strong><small>'+escape(file.description)+'</small></div>'+link(fileLink(file.path),"Open file")+'</div>').join("")+'</div></section>'+
  '<section class="assurance-panel"><div class="assurance-header"><div><h2>Discovery limitations</h2><p>Observed source-provider failures are not proof that no opportunities are available.</p></div></div>'+
  (errors.length?'<div class="assurance-errors">'+errors.map(([name,problems])=>'<p><strong>'+escape(name)+'</strong> · '+escape(Array.isArray(problems)?problems.join("; "):String(problems))+'</p>').join("")+'</div>':'<p class="assurance-footnote">No provider failures were recorded in this snapshot. Coverage remains incomplete by design.</p>')+
  '</section></div>';
}
