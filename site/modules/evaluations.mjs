const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=value=>typeof value==="number"&&Number.isFinite(value)?value.toLocaleString():"Not measured";
const option=(id,label,active)=>'<option value="'+esc(id)+'"'+(id===active?" selected":"")+'>'+esc(label)+'</option>';
const metric=(value,label)=>'<div><strong>'+esc(fmt(value))+'</strong><span>'+esc(label)+'</span></div>';

export function renderEvaluations({report=null,provider="all",agent="all",error="",loading=false}={}) {
 const data=report?.schema_version===1&&Array.isArray(report.providers)&&Array.isArray(report.agents)?report:null;
 const providers=data?.providers||[],agents=data?.agents||[];
 const selectedProvider=providers.some(x=>x.provider_id===provider)?provider:"all";
 const selectedAgent=agents.some(x=>x.agent_id===agent)?agent:"all";
 const traces=(data?.recent_traces||[]).filter(item=>
   (selectedProvider==="all"||item.provider_id===selectedProvider)&&
   (selectedAgent==="all"||item.agent_id===selectedAgent)).slice(0,40);
 const totals=data?.summary||{};
 const group=(title,rows,key)=>'<section class="os-panel"><div class="os-panel-heading"><div><h2>'+esc(title)+'</h2>'+
   '<p>Only observed model calls count; missing measurements remain unknown.</p></div></div>'+
   '<div class="os-eval-table"><div class="os-eval-row os-eval-header"><span>Identity</span><span>Calls</span><span>Failed</span><span>p95 latency</span><span>Unknown citations</span></div>'+
   (rows.length?rows.map(item=>'<div class="os-eval-row"><strong>'+esc(item[key])+'</strong><span>'+esc(fmt(item.calls))+'</span>'+
     '<span>'+esc(fmt(item.failed))+'</span><span>'+esc(item.latency_p95_ms==null?"Not measured":fmt(item.latency_p95_ms)+" ms")+
     '</span><span>'+esc(fmt(item.unknown_reference_links))+'</span></div>').join(""):
     '<p class="os-empty">No measured calls in this category.</p>')+'</div></section>';
 return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE / MODEL ASSURANCE</div>'+
   '<h1>Agent evaluations</h1><p>Reproducible local execution and citation metrics. No speculative model grading or admissions outcomes.</p></div>'+
   '<div class="os-head-actions"><button type="button" class="os-btn quiet" data-os-action="refresh-evaluations"'+(loading?" disabled":"")+
   '>Refresh metrics</button></div></div>'+
   (error?'<p class="os-warning" role="alert">'+esc(error)+'</p>':"")+
   (!data?'<section class="os-panel"><p class="os-empty">'+(loading?"Loading private metrics…":
     "Evaluation metrics unavailable. Connect the local runtime or refresh.")+'</p></section>':
   '<div class="os-kpi-strip">'+metric(totals.calls,"Recorded model calls")+metric(totals.failed,"Failed calls")+
     metric(totals.citation_audits,"Citation audits")+metric(totals.unknown_reference_links,"Unknown citation links")+
     metric(totals.unverified_reference_links,"Unverified citation links")+'</div>'+
   (data.sample_truncated?'<p class="os-note">Partial sample: newest '+esc(fmt(data.sample_limit))+' run-ledger entries only.</p>':"")+
   (data.status==="no_observations"?'<p class="os-note">No agent executions recorded. Performance and citation quality cannot be estimated.</p>':"")+
   group("Provider comparison",providers,"provider_id")+group("Agent comparison",agents,"agent_id")+
   '<section class="os-panel"><div class="os-panel-heading"><div><h2>Recent execution traces</h2>'+
   '<p>Filters affect the displayed recent traces, not the aggregate metrics above. Applicant text is never returned here.</p></div></div>'+
   '<div class="os-eval-filters"><label class="os-field"><span>Provider</span><select data-os-eval-provider>'+
   option("all","All providers",selectedProvider)+providers.map(x=>option(x.provider_id,x.provider_id,selectedProvider)).join("")+'</select></label>'+
   '<label class="os-field"><span>Agent</span><select data-os-eval-agent>'+
   option("all","All agents",selectedAgent)+agents.map(x=>option(x.agent_id,x.agent_id,selectedAgent)).join("")+'</select></label></div>'+
   '<div class="os-ledger">'+(traces.length?traces.map(run=>
     '<article class="os-ledger-row"><div><strong>'+esc(run.agent_id)+'</strong><small>'+esc(run.provider_id)+' · '+
     esc(run.model||"Model not recorded")+' · '+esc(run.created_at)+'</small>'+
     '<small>Contract: '+esc(run.prompt_contract_id||"Legacy/unrecorded")+' · '+esc(String(run.run_id||"").slice(0,12))+
     '</small></div><span class="os-badge '+(run.status==="failed"?"warn":"good")+'">'+esc(run.status)+'</span>'+
     '<span class="os-meta">'+esc(run.latency_ms==null?"Latency unknown":run.latency_ms+" ms")+'</span></article>').join(""):
     '<p class="os-empty">No recent traces match these filters.</p>')+'</div></section>'+
   '<section class="os-panel"><div class="os-panel-heading"><div><h2>Workflow execution outcomes</h2>'+
   '<p>Workflow summaries are not counted twice as inference calls.</p></div></div>'+
   '<div class="os-ledger">'+((data.workflow_summaries||[]).length?(data.workflow_summaries||[]).map(item=>
     '<article class="os-ledger-row"><div><strong>'+esc(item.workflow_id)+'</strong><small>'+esc(String(item.run_id||"").slice(0,12))+
     ' · '+esc(fmt(item.completed_stages))+' of '+esc(fmt(item.stage_count))+' stages</small></div>'+
     '<span class="os-badge '+(item.status==="failed"?"warn":"good")+'">'+esc(item.status)+'</span></article>').join(""):
     '<p class="os-empty">No workflow execution summaries recorded.</p>')+'</div></section>'+
   '<p class="os-footnote">'+esc(data.limitations||"")+' · Sample generated '+esc(data.generated_at||"unknown")+'</p>')+
   '</section>';
}
