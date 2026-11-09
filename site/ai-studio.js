(() => {
"use strict";
const $ = id => document.getElementById(id);
const escape = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = {data:null,ops:null,view:"overview",query:"",selected:"",busy:false,filter:"all",providerFilter:"all"};
const VIEWS = {overview:"Decision desk",agents:"AI agents",workflows:"Automation",providers:"Models & providers",applications:"Applications",referees:"Referees",timeline:"Deadline clocks",evidence:"Evidence ledger",planning:"Capacity planning",activity:"Run history",settings:"Settings & diagnostics"};
const isCloud = id => !state.data.catalog.providers.find(p => p.id === id)?.local;
function toast(message){const el=$("message");el.textContent=message;el.style.display="block";clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.style.display="none",4500)}
async function api(path, body){
 const options = {headers:{Accept:"application/json"}};
 if(body !== undefined){options.method="POST";options.headers["Content-Type"]="application/json";options.body=JSON.stringify(body)}
 const res=await fetch(path,options);
 let value;try{value=await res.json()}catch{throw Error("The private API returned an invalid response")}
 if(!res.ok)throw Error(value.error || "Request failed ("+res.status+")");
 return value;
}
const btn=(label,act,id="",type="")=>'<button type="button" class="btn '+type+'" data-action="'+escape(act)+'" data-id="'+escape(id)+'">'+escape(label)+'</button>';
const minor=(label,act,id="")=>'<button type="button" class="mini-button" data-action="'+escape(act)+'" data-id="'+escape(id)+'">'+escape(label)+'</button>';
const tag=(text,kind="neutral")=>'<span class="tag '+kind+'">'+escape(text)+'</span>';
const heading=(kicker,title,desc,actions="")=>'<div class="section-head"><div><p class="eyebrow">'+escape(kicker)+'</p><h1>'+escape(title)+'</h1><p class="subtitle">'+escape(desc)+'</p></div><div class="buttons">'+actions+'</div></div>';
const metric=(label,value,note)=>'<article class="metric"><span>'+escape(label)+'</span><strong>'+escape(value)+'</strong><small>'+escape(note)+'</small></article>';
const panel=(title,subtitle,body,action="")=>'<section class="panel"><div class="panel-head"><div><h2>'+escape(title)+'</h2>'+(subtitle?'<p>'+escape(subtitle)+'</p>':"")+'</div>'+action+'</div><div class="panel-body">'+body+'</div></section>';
const isExpired=r=>r.deadline&&r.deadline<new Date().toISOString().slice(0,10);
function nav(view){
 if(!VIEWS[view])return;
 state.view=view;location.hash=view;render();
}
function selectChoices(items,current){return items.map(x=>'<option value="'+escape(x.id)+'"'+(x.id===current?' selected':'')+'>'+escape(x.label)+'</option>').join("")}
function providerSelect(name="provider_id",current=""){
 const selected=current||state.data.settings?.default_provider||"ollama";
 return '<select id="'+escape(name)+'" name="'+escape(name)+'" required>'+selectChoices(state.data.catalog.providers.map(p=>({id:p.id,label:p.label+" · "+p.model})),selected)+'</select>';
}
function appSelect(name="application_id",selected=""){
 return '<select name="'+name+'"><option value="">Whole portfolio</option>'+selectChoices(state.data.records.filter(r=>r.record_type==="tracked").map(r=>({id:r.id,label:r.name})),selected)+'</select>';
}
function overview(){
 const d=state.data,records=d.records.filter(r=>r.record_type==="tracked"),tasks=d.agenda;
 const immediate=tasks.filter(t=>t.days!==null&&t.days<=3);
 const unverified=records.filter(r=>!["source_verified","owner_verified"].includes(r.verification)).length;
 const sourceWarn=d.providers_status.filter(x=>x.health!=="ok");
 const runs=d.runs||[];
 const taskRows=tasks.slice(0,12).map(t=>'<div class="list-row"><div><strong>'+escape(t.label)+'</strong><p>'+escape(records.find(r=>r.id===t.application_id)?.name||t.application_id)+'</p><div class="row-meta">'+tag(t.kind,"neutral")+'<span class="code">'+escape(t.days===null?"date unknown":t.days+" days")+'</span></div></div>'+minor("Inspect","inspect",t.application_id)+'</div>').join("");
 return heading("01 / OPERATIONAL INTELLIGENCE","Decisions before dashboards","A prioritized, source-aware queue across application preparation, documents and post-submission tasks.",btn("Run daily briefing","workflow-run","daily_brief","primary")+btn("Add an agent","new-agent"))+
 '<div class="kpis">'+metric("TRACKED APPLICATIONS",records.length,"Candidate leads kept separate")+metric("NEXT 72 HOURS",immediate.length,"Distinct actions, not applications")+metric("SOURCE CHECKS NEEDED",unverified,"Evidence confirmation pending")+metric("RECORDED AI RUNS",runs.length,"Private proposals and audits")+'</div>'+
 (sourceWarn.length?'<div class="notice">Discovery coverage degraded: '+sourceWarn.map(x=>escape(x.name+" ("+x.health+")")).join(", ")+'. An unchanged source does not establish that a call remains open.</div>':'')+
 '<div class="grid-two">'+panel("Decision queue","Ranked by urgency and stated resource dependencies",taskRows||'<div class="blank">No actionable tasks found.</div>',minor("All applications","nav","applications"))+
 '<div>'+panel("Automated workflow state","Scheduled runs are opt-in; AI output never submits an application.",d.catalog.workflows.slice(0,6).map(w=>'<div class="list-row"><div><strong>'+escape(w.label)+'</strong><p>'+escape(w.description)+'</p><div class="row-meta">'+tag(w.enabled?"Enabled":"Disabled",w.enabled?"":"warn")+tag(w.schedule)+'</div></div>'+minor("Configure","edit-workflow",w.id)+'</div>').join(""),minor("Manage all","nav","workflows"))+
 '<div style="height:17px"></div>'+panel("Safety boundary","Designed for private applicant operations",'<div class="notice neutral" style="margin:0">Cloud model calls require explicit disclosure approval. Credentials are read from environment variables. Agent outputs are proposals; verified source facts and submitted status are never inferred from model text.</div>')+'</div></div>';
}
function agents(){
 const d=state.data;
 return heading("02 / INTELLIGENT WORKERS","Research and execution agents","Specialized, configurable agents with human-controlled actions, evidence injection and provider-independent prompting.",btn("New agent","new-agent","","primary"))+
 '<div class="panel" style="margin-bottom:23px"><div class="panel-head"><div><h2>Run an agent</h2><p>The selected source record will be supplied as untrusted evidence. Review provider data handling before calling cloud models.</p></div></div><div class="panel-body">'+
 '<form id="agentRunForm" class="form-grid"><div class="field"><label>Research agent</label><select name="agent_id" required>'+selectChoices(d.catalog.agents.map(a=>({id:a.id,label:a.label})),d.settings?.default_agent||d.catalog.agents[0]?.id)+'</select></div>'+
 '<div class="field"><label>Model provider</label>'+providerSelect()+'</div>'+
 '<div class="field wide"><label>Application context</label>'+appSelect()+'</div>'+
 '<div class="field wide"><label>Specific research task</label><textarea name="input_text" rows="3" maxlength="5000" placeholder="Ask for a verifiable analysis, decision, or draft."></textarea></div>'+
 '<div class="field wide checkbox"><input type="checkbox" name="cloud_consent" id="agentCloud"><label for="agentCloud">I explicitly authorize sending the selected application evidence and prompt to the configured cloud model when a cloud provider is chosen.</label></div>'+
 '<div class="form-actions"><button type="submit" class="btn primary">Execute analysis</button></div></form></div></div>'+
 '<div class="cards">'+d.catalog.agents.map(a=>'<article class="catalog-card"><div class="catalog-top"><span class="catalog-badge">'+escape(a.id)+'</span>'+tag("AI agent")+'</div><h3>'+escape(a.label)+'</h3><p>'+escape(a.description)+'</p><div class="buttons">'+minor("Edit agent","edit-agent",a.id)+minor("Select for run","select-agent",a.id)+'</div></article>').join("")+'</div>';
}
function workflows(){
 const d=state.data;
 return heading("03 / AUTOMATION DESIGN","Workflows and schedules","Connect agents to explicit tasks and schedules. Each run creates an auditable proposal; no external side effects or hidden submissions.",btn("New workflow","new-workflow","","primary")+btn("Evaluate schedules","scheduler-tick"))+
 '<div class="notice neutral">Scheduled execution occurs only when you run the private scheduler. Disabled is the default. Scheduled cloud calls require a separate saved cloud-consent setting.</div>'+
 '<div class="cards two">'+d.catalog.workflows.map(w=>'<article class="catalog-card"><div class="catalog-top"><span class="catalog-badge">'+escape(w.id)+'</span>'+tag(w.enabled?"Enabled":"Disabled",w.enabled?"":"warn")+'</div><h3>'+escape(w.label)+'</h3><p>'+escape(w.description)+'</p><div class="row-meta">'+tag(w.schedule)+tag((w.steps||[w.agent_id]).join(" then "))+tag(w.provider_id||"ollama")+'</div><div class="buttons">'+minor("Edit workflow","edit-workflow",w.id)+minor("Run now","workflow-run",w.id)+'</div></article>').join("")+'</div>';
}
function providers(){
 const d=state.data, all=d.catalog.providers, status=d.provider_states||{};
 const verified=all.filter(p=>status[p.id]?.state==="responded").length;
 const configured=all.filter(p=>["ready_to_test","responded","reachable"].includes(status[p.id]?.state)).length;
 const visible=all.filter(p=>state.providerFilter==="all"||(state.providerFilter==="local"&&p.local)||(state.providerFilter==="cloud"&&!p.local)||(state.providerFilter==="attention"&&["needs_setup","failed"].includes(status[p.id]?.state)));
 const labels={needs_setup:"Setup required",ready_to_test:"Untested",responded:"Inference verified",reachable:"Catalog reachable",failed:"Connection failed"};
 const cards=visible.map(p=>{
  const st=status[p.id]||{}, code=st.state||"ready_to_test", tone=code==="responded"?"good":code==="failed"||code==="needs_setup"?"warn":"neutral";
  const reason=st.reason||st.last_error||(st.last_checked?"Last check: "+st.last_checked+" · "+(st.latency_ms??"—")+" ms":"Endpoint not yet tested");
  return '<article class="catalog-card connection-card"><div class="catalog-top">'+tag(p.local?"On-device":"Cloud API",p.local?"":"warn")+'<span class="provider-health '+escape(tone)+'"><span class="provider-dot"></span>'+escape(labels[code]||code)+'</span></div>'+
   '<div class="provider-brand"><h3>'+escape(p.label)+'</h3><span class="mono">'+escape(p.kind)+'</span></div>'+
   '<dl class="provider-facts"><div><dt>Model</dt><dd>'+escape(p.model)+'</dd></div><div><dt>Endpoint</dt><dd class="endpoint">'+escape(p.base_url)+'</dd></div><div><dt>Credentials</dt><dd>'+escape(p.api_key_env?(st.credential_configured?"Configured in environment":"Requires "+p.api_key_env):"No API key required")+'</dd></div></dl>'+
   '<p class="connection-detail">'+escape(reason)+'</p><div class="buttons provider-actions">'+minor("Discover models","provider-models",p.id)+minor("Test inference","provider-probe",p.id)+minor("Configure","edit-provider",p.id)+'</div></article>';
 }).join("");
 return heading("04 / MODEL INFRASTRUCTURE","Connections and model routing","Configure local and cloud endpoints, inspect discovered models and verify a response before selecting a provider.",btn("Add provider","new-provider","","primary")+btn("Settings","nav","settings"))+
 '<div class="kpis">'+metric("PROVIDERS",all.length,"Catalog entries · connection not implied")+metric("VERIFIED INFERENCE",verified,"Most recent successful model responses")+metric("CONFIGURATION READY",configured,"Credential and endpoint checks only")+metric("DEFAULT ROUTE",d.settings?.default_provider||"ollama","Private preferences")+'</div>'+
 '<div class="notice neutral">Provider checks are explicitly initiated. Model discovery contacts the provider but sends no application records. Inference tests may consume tokens. Credential values remain in the backend environment.</div>'+
 '<div class="connection-toolbar"><label for="providerFilter">View providers</label><select id="providerFilter">'+[["all","All"],["local","Local"],["cloud","Cloud"],["attention","Needs attention"]].map(([k,label])=>'<option value="'+k+'"'+(state.providerFilter===k?" selected":"")+'>'+label+'</option>').join("")+'</select><span>'+visible.length+' / '+all.length+' connections</span></div>'+
 '<div class="cards provider-cards">'+(cards||'<div class="blank">No providers match the selected filter.</div>')+'</div>';
}
function settings(){
 const d=state.data, prefs=d.settings||{}, status=d.provider_states||{};
 const credentials=d.catalog.providers.filter(p=>status[p.id]?.credential_configured).length;
 const checked=Object.values(status).filter(s=>s.state==="responded").length;
 return heading("11 / OPERATOR CONTROLS","Settings & diagnostics","Persistent private defaults, time zone, run limits and evidence-grounded connection health.",btn("Connections","nav","providers","primary"))+
 '<div class="settings-layout">'+panel("Runtime preferences","Preferences affect local agent execution, not the public spreadsheet.",'<form id="settingsForm" class="form-grid">'+
 '<div class="field"><label for="default_provider">Default provider</label>'+providerSelect("default_provider",prefs.default_provider||"ollama")+'</div>'+
 '<div class="field"><label for="prefAgent">Default agent</label><select name="default_agent" id="prefAgent">'+selectChoices(d.catalog.agents.map(a=>({id:a.id,label:a.label})),prefs.default_agent||"portfolio_planner")+'</select></div>'+
 '<div class="field"><label for="prefZone">Local IANA time zone</label><input id="prefZone" name="timezone" required value="'+escape(prefs.timezone||"Europe/London")+'"><small>Example: Europe/Amsterdam. Official cutoff-zone evidence remains separate.</small></div>'+
 '<div class="field"><label for="prefLimit">Maximum scheduled runs per tick</label><input id="prefLimit" type="number" min="1" max="10" step="1" name="max_runs_per_tick" value="'+escape(prefs.max_runs_per_tick||3)+'" required><small>Limits each scheduled evaluation; no background service is created automatically.</small></div>'+
 '<div class="field"><label for="prefCloudLimit">Daily scheduled cloud model calls</label><input id="prefCloudLimit" type="number" min="0" max="100" step="1" name="max_cloud_model_calls_per_day" value="'+escape(prefs.max_cloud_model_calls_per_day??0)+'" required><small>Zero disables scheduled cloud calls, even for approved workflows. Manual calls remain explicitly confirmed.</small></div>'+
 '<div class="field wide privacy-setting"><strong>Cloud disclosure approval enforced</strong><p>Manual cloud requests need explicit authorization. Scheduled cloud workflows require separate workflow-level approval. This protection cannot be disabled.</p></div>'+
 '<div class="form-actions"><button type="submit" class="btn primary">Save preferences</button></div></form>')+
 panel("Operational diagnostics","A listed provider is not the same as a working connection.",'<div class="diagnostics-list">'+
 [["Private runtime","Loopback only","No externally accessible API"],["Credentials",credentials+" configured environment variable(s)","Secret values never leave the server"],["Inference checks",checked+" verified provider(s)","Last check is not an uptime guarantee"],["Scheduler","External trigger required","Invoke scheduler-once using cron or systemd"],["Storage","Local SQLite","Private state is not synced to public GitHub"]].map(([name,value,desc])=>'<div class="diagnostic-row"><span>'+escape(name)+'</span><div><strong>'+escape(value)+'</strong><small>'+escape(desc)+'</small></div></div>').join("")+
 '<div class="buttons">'+btn("Connection tests","nav","providers","primary")+btn("Run history","nav","activity")+'</div></div>')+'</div>'+
 '<section class="panel" style="margin-top:22px"><div class="panel-head"><div><h2>Deployment boundary</h2><p>Why a private runtime is necessary</p></div></div><div class="panel-body"><p class="subtitle">The public Pages site can display source data but cannot securely host provider credentials, scheduled LLM execution or personal records. Run AI Studio from the checkout on your private machine.</p><code class="instruction">python -m phd_agents serve --port 8765</code></div></section>';
}
function applications(){
 const list=state.data.records.filter(r=>r.record_type==="tracked").filter(r=>(r.name+" "+r.id+" "+r.topic).toLowerCase().includes(state.query.toLowerCase())).slice(0,160);
 return heading("05 / APPLICATION CONTROL","Evidence-backed applications","Inspect preflight proof obligations, update private owner state, and retain status after portal submission.",btn("Run preflight agent","nav","agents","primary"))+
 '<div class="controls"><input id="appSearch" class="search" type="search" placeholder="Find a programme, identifier or topic…" value="'+escape(state.query)+'" aria-label="Filter applications"><span class="tag neutral">'+list.length+' applications</span></div>'+
 '<section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Opportunity</th><th>Deadline</th><th>Stage</th><th>Source</th><th>Actions</th></tr></thead><tbody>'+
 list.map(r=>'<tr><td><strong>'+escape(r.name)+'</strong><small>'+escape(r.id)+'</small></td><td>'+escape(r.deadline||"Unknown")+(isExpired(r)?'<small>Recorded date passed</small>':'')+'</td><td>'+tag(r.status,"neutral")+'</td><td>'+tag(r.verification,["source_verified","owner_verified"].includes(r.verification)?"":"warn")+'</td><td>'+minor("Preflight","inspect",r.id)+' '+minor("Update","edit-application",r.id)+'</td></tr>').join("")+'</tbody></table></div></section>';
}
function activity(){
 const runs=state.data.runs||[],audit=state.data.activity||[],stats=state.data.usage_summary||{},groups=stats.provider_usage||[];
 const providerRows=groups.map(p=>'<div class="list-row"><div><strong>'+escape(p.provider_id)+'</strong><p>'+escape(p.calls)+' model calls · '+escape(p.failed)+' failed</p><div class="row-meta">'+tag(p.input_tokens+' input tokens')+tag(p.output_tokens+' output tokens')+(p.average_latency_ms===null?"":tag(p.average_latency_ms+' ms average latency'))+'</div></div></div>').join("");
 return heading("06 / OBSERVABILITY","Inference and execution history","Inspect actual model usage, latency and failures. No pricing, admission probabilities or completed external actions are inferred.",btn("Refresh metrics","refresh"))+
 '<div class="kpis">'+metric("RECORDED MODEL CALLS",stats.sampled_runs??0,"Sample of up to "+escape(stats.sample_limit||2000)+" stored runs")+metric("INPUT TOKENS",stats.total_input_tokens??0,"Only reported usage")+metric("OUTPUT TOKENS",stats.total_output_tokens??0,"Only reported usage")+metric("FAILED CALLS",stats.total_failed??0,"Recorded provider invocation failures")+'</div>'+
 '<div class="notice neutral">Costs are not estimated without verified provider-specific pricing. Inference latency is measured wall-clock time per model call. Reports do not include unobserved external usage.</div>'+
 '<div class="grid-two">'+panel("Provider-level execution","Observed calls and model-response telemetry",providerRows||'<div class="blank">No inference telemetry has been recorded yet.</div>')+
 panel("Agent run ledger","Individual execution records",runs.map(r=>'<div class="list-row"><div><strong>'+escape(r.agent_id)+'</strong><p>'+escape(r.created_at)+' · '+escape(r.provider_id)+' · '+escape(r.status)+'</p><div class="row-meta">'+tag(r.model||"model unavailable")+(r.latency_ms!==null&&r.latency_ms!==undefined?tag(r.latency_ms+' ms'):"")+(r.application_id?tag(r.application_id):"")+'</div></div>'+minor("Inspect","view-run",r.id)+'</div>').join("")||'<div class="blank">No agent runs have been recorded.</div>')+'</div>'+
 '<div style="height:18px"></div>'+panel("Audit events","Private state changes and scheduler events",'<div class="timeline">'+audit.map(a=>'<div class="timeline-item"><strong>'+escape(a.action)+'</strong><time>'+escape(a.created_at)+'</time><span class="code">'+escape(a.subject)+'</span></div>').join("")+'</div>'||'<div class="blank">No recorded events.</div>');
}

function referees(){
 const o=state.ops,m=o.referee_matrix||{requests:[]},contacts=o.referees||[];
 return heading("07 / SHARED DEPENDENCIES","Referees and recommendations","Each referee × application request has an independent state, deadline and portal verification. A shared referee may block several applications.",btn("Add referee","new-private","referee","primary")+btn("Track reference","new-private","reference"))+
 '<div class="kpis">'+metric("REGISTERED REFEREES",m.referees||0,"Private contact records")+metric("REFERENCE REQUESTS",m.requests.length,"One request per portal")+metric("PENDING VERIFICATION",m.pending||0,"Not yet portal-verified")+metric("DUE WITHIN 7 DAYS",m.urgent||0,"Human follow-up required")+'</div>'+
 '<div class="grid-two">'+panel("Reference dependency matrix","Uploaded and acknowledged are not the same as portal-verified.",(m.requests.length?m.requests.map(r=>
 '<div class="list-row"><div><strong>'+escape(r.referee)+'</strong><p>'+escape(state.data.records.find(x=>x.id===r.application_id)?.name||r.application_id)+'</p><div class="row-meta">'+tag(r.status,r.is_portal_verified?"":r.needs_attention?"warn":"neutral")+
 (r.deadline?tag(r.deadline):"")+'</div></div>'+minor("Update","edit-private","reference:"+r.id)+'</div>').join(""):'<div class="blank">No portal-specific reference requests. Add a referee and connect each application separately.</div>'))+
 panel("Referee contact registry","Private records are never projected to public Pages.",(contacts.length?contacts.map(r=>
 '<div class="list-row"><div><strong>'+escape(r.name)+'</strong><p>'+escape(r.affiliation||"Affiliation not recorded")+'</p><div class="row-meta">'+tag(String(o.referee_matrix.shared_dependency[r.id]||0)+" linked applications")+'</div></div>'+minor("Edit","edit-private","referee:"+r.id)+'</div>').join(""):'<div class="blank">No referees recorded yet.</div>'))+'</div>';
}
function timeline(){
 const o=state.ops,events=o.deadline_events||[];
 const ahead=events.filter(e=>e.days_left!==null&&e.days_left>=0).slice(0,75);
 const needsTime=events.filter(e=>e.days_left!==null&&e.days_left>=0&&!e.cutoff_fully_verified).length;
 return heading("08 / TEMPORAL INTELLIGENCE","Multiple deadlines, one source of truth","Keep final cutoffs separate from referee, scholarship, supervisor-contact, interview and priority-review milestones.",btn("Record milestone","new-private","milestone","primary")+btn("Private calendar export","private-ics"))+
 '<div class="kpis">'+metric("RECORDED CLOCKS",events.length,"Source and private milestones")+metric("UPCOMING EVENTS",events.filter(e=>e.days_left!==null&&e.days_left>=0).length,"Calendar dates only")+metric("CUTOFF TIMES UNKNOWN",needsTime,"Require official time-zone evidence")+metric("PRIVATE MILESTONES",o.milestones.length,"Explicitly maintained by applicant")+'</div>'+
 '<div class="notice">Date-only events do not imply a verified end-of-day cutoff. An institutional source may change after a prior observation. Verify the submission portal.</div>'+
 panel("Milestone timeline","Showing the next 75 calendar events",ahead.map(e=>
 '<div class="list-row"><div><strong>'+escape(state.data.records.find(r=>r.id===e.application_id)?.name||e.application_id)+'</strong><p>'+escape(e.kind.replaceAll("_"," "))+' · '+escape(e.date)+(e.time?' '+escape(e.time)+' '+escape(e.timezone):" · Cutoff time unknown")+'</p><div class="row-meta">'+tag(e.verification||"unverified",e.cutoff_fully_verified?"":"warn")+'<span class="code">'+escape(e.provenance)+'</span></div></div>'+
 (e.id.startsWith("source:")?minor("Open application","inspect",e.application_id):minor("Edit milestone","edit-private","milestone:"+e.id))+'</div>').join("")||'<div class="blank">No upcoming dated events.</div>');
}
function evidence(){
 const o=state.ops,claims=o.claims||[],conflicts=o.evidence_conflicts||[];
 return heading("09 / VERIFIED ASSERTIONS","Evidence and contradictions","Maintain separate source-linked claims. Disagreements are presented for review and never silently overwritten by AI.",btn("Add evidence claim","new-private","evidence","primary"))+
 '<div class="kpis">'+metric("PRIVATE ASSERTIONS",claims.length,"Versioned through private storage")+metric("CONFLICT GROUPS",conflicts.length,"Different source assertions")+metric("PRIMARY CONFIRMED",claims.filter(c=>c.status==="primary_confirmed").length,"Owner-entered proof status")+metric("REQUIRES REVIEW",claims.filter(c=>["unverified","needs_review","contradicted"].includes(c.status)).length,"No automatic confirmation")+'</div>'+
 (conflicts.length?'<div class="notice">'+conflicts.length+' assertion groups disagree: '+escape(conflicts.map(c=>c.application_id+" / "+c.field).join(", "))+'</div>':"")+
 panel("Claim ledger","Evidence status is owner-entered, not a guarantee that a source remains live",claims.length?claims.map(c=>
 '<div class="list-row"><div><strong>'+escape(c.field)+' · '+escape(c.application_id)+'</strong><p>'+escape(c.assertion)+'</p><div class="row-meta">'+tag(c.status,c.status==="primary_confirmed"?"":c.status==="contradicted"?"danger":"warn")+
 (c.source_url?'<a href="'+escape(c.source_url)+'" target="_blank" rel="noopener noreferrer">Official/source link</a>':"")+'</div></div>'+minor("Review","edit-private","evidence:"+c.id)+'</div>').join(""):'<div class="blank">No private claims yet. Source records from the existing tracker remain available in Applications.</div>');
}
function planning(){
 const o=state.ops,profile=o.profile||{},signals=o.research_fit_signals||[];
 const value=profile.hours_per_week||"";
 const priority=signals.slice(0,18).map(x=>'<div class="list-row"><div><strong>'+escape(state.data.records.find(r=>r.id===x.application_id)?.name||x.application_id)+'</strong><p>Matched research vocabulary: '+escape(x.matched_terms.join(", "))+'</p></div>'+tag(x.matched_count+" terms")+'</div>').join("");
 return heading("10 / RESOURCE INTELLIGENCE","Capacity and research fit","Make unknown effort explicit, reuse preparation assets and distinguish keyword overlap from defensible methodological fit.",btn("Edit applicant research profile","edit-private","profile:applicant","primary"))+
 '<div class="grid-two">'+
 panel("Application work allocation","Earliest-deadline-first screening; provisional until effort and shared dependencies are confirmed.",'<form id="capacityForm" class="form-grid"><div class="field"><label for="capacityHours">Applicant hours per week</label><input id="capacityHours" name="hours_per_week" type="number" step="0.5" min="0.5" max="168" value="'+escape(value)+'" required></div><div class="field" style="justify-content:end">'+btn("Generate allocation","generate-schedule","","primary")+'</div><div class="field wide"><small>Enter estimated hours against individual applications. Shared document work is identified separately, not silently counted as completed.</small></div></form>')+
 panel("Lexical research alignment","A discovery hint, not evidence of recruiting status, eligibility or admission probability",priority||'<div class="blank">Enter research topics and skills in the private applicant profile to enable inspectable matching signals.</div>')+'</div>';
}

function render(){
 const d=state.data;if(!d)return;
 const actual={overview,agents,workflows,providers,applications,referees,timeline,evidence,planning,activity,settings};
 $("crumb").textContent=VIEWS[state.view];
 const mobileView=$("mobileStudioView");if(mobileView)mobileView.value=state.view;
 document.querySelectorAll("[data-view]").forEach(b=>{b.classList.toggle("active",b.dataset.view===state.view);if(b.dataset.view===state.view)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current")});
 $("workspace").innerHTML=actual[state.view]();
}
let focusReturn=null;
function modal(title,body){
 if(!$("dialogLayer").children.length)focusReturn=document.activeElement;
 document.querySelector(".studio").inert=true;
 document.body.classList.add("dialog-open");
 $("dialogLayer").innerHTML='<div class="overlay"><section class="dialog" tabindex="-1" role="dialog" aria-modal="true" aria-label="'+escape(title)+'"><div class="dialog-head"><h2>'+escape(title)+'</h2><button type="button" class="dialog-close" data-action="close" aria-label="Close dialog">×</button></div><div class="dialog-body">'+body+'</div></section></div>';
 $("dialogLayer").querySelector(".dialog-close")?.focus();
}
function close(){
 $("dialogLayer").innerHTML="";
 document.querySelector(".studio").inert=false;
 document.body.classList.remove("dialog-open");
 if(focusReturn?.isConnected&&typeof focusReturn.focus==="function")focusReturn.focus();
 focusReturn=null;
}
const textField=(name,label,value="",hint="",type="text")=>'<div class="field"><label for="f_'+escape(name)+'">'+escape(label)+'</label><input id="f_'+escape(name)+'" type="'+type+'" name="'+escape(name)+'" value="'+escape(value)+'"'+(name==="id"?' required pattern="[a-z][a-z0-9_-]{1,63}"':"")+'>'+ (hint?'<small>'+escape(hint)+'</small>':"")+'</div>';
const area=(name,label,value="",rows=4)=>'<div class="field wide"><label for="f_'+escape(name)+'">'+escape(label)+'</label><textarea id="f_'+escape(name)+'" name="'+escape(name)+'" rows="'+rows+'">'+escape(value)+'</textarea></div>';
function configModal(kind,id=""){
 const d=state.data,entries=d.catalog[kind+"s"]||[],old=entries.find(p=>p.id===id)||{};
 let body="";
 if(kind==="provider"){
  body=textField("id","Provider identifier",old.id||"")+textField("label","Display name",old.label||"")+
   '<div class="field"><label>Adapter</label><select name="kind">'+selectChoices(["openai_compatible","azure_openai","azure_deployment","anthropic"].map(z=>({id:z,label:z})),old.kind||"openai_compatible")+'</select></div>'+
   textField("model","Model ID / deployment",old.model||"")+textField("base_url","API base URL",old.base_url||"http://127.0.0.1:11434/v1","Local HTTP requires a loopback address")+
   textField("api_key_env","Credential environment variable",old.api_key_env||"","Never enter the credential value here")+
    textField("api_version","Azure deployment API version",old.api_version||"","Only for Azure deployment-based endpoints; e.g. 2024-10-21")+
   textField("max_output_tokens","Max response tokens",old.max_output_tokens||1200,"64–4096","number")+
   '<div class="field"><label>Token parameter</label><select name="token_parameter">'+selectChoices(["max_tokens","max_completion_tokens"].map(z=>({id:z,label:z})),old.token_parameter||"max_tokens")+'</select></div>'+
   '<div class="field wide checkbox"><input type="checkbox" id="localProvider" name="local" '+(old.local?"checked":"")+'><label for="localProvider">Local or self-hosted endpoint (HTTP only permitted on loopback)</label></div>';
 }else if(kind==="agent"){
  body=textField("id","Agent identifier",old.id||"")+textField("label","Agent name",old.label||"")+
  area("description","Purpose and human-facing description",old.description||"",2)+
  area("instructions","Specialized system instructions",old.instructions||"",7)+
  textField("tools","Allowlisted tools, comma-separated",(old.tools||[]).join(", "), "Optional tools: preflight, daily_agenda, deadline_clocks, referee_dependencies, evidence_disputes, research_alignment, capacity_screen, discovery_health, paper_radar, proof_obligations");
 }else{
  body=textField("id","Workflow identifier",old.id||"")+textField("label","Workflow name",old.label||"")+
  '<div class="field"><label>Assigned agent</label><select name="agent_id">'+selectChoices(d.catalog.agents.map(x=>({id:x.id,label:x.label})),old.agent_id||"portfolio_planner")+'</select></div>'+
  '<div class="field"><label>Schedule</label><select name="schedule">'+selectChoices(["manual","daily","twice_daily","weekly"].map(z=>({id:z,label:z})),old.schedule||"manual")+'</select></div>'+
  '<div class="field"><label>Provider for scheduled runs</label>'+providerSelect("provider_id",old.provider_id||"ollama")+'</div>'+
  textField("steps","Sequential agent stages, comma-separated",(old.steps||[old.agent_id||"portfolio_planner"]).join(", "), "One to three known agent IDs")+
  area("description","What this workflow does",old.description||"",2)+area("prompt","Custom workflow objective",old.prompt||"",3)+
  '<div class="field checkbox"><input type="checkbox" id="enabledFlow" name="enabled" '+(old.enabled?"checked":"")+'><label for="enabledFlow">Enable scheduled execution</label></div>'+
  '<div class="field checkbox"><input type="checkbox" id="allowCloudFlow" name="cloud_consent" '+(old.cloud_consent?"checked":"")+'><label for="allowCloudFlow">Authorize scheduled cloud-model disclosure of application context</label></div>';
 }
 modal((id?"Edit ":"Create ")+kind,'<form id="configForm" data-kind="'+kind+'" class="form-grid">'+body+
 '<div class="form-actions"><button class="btn" type="button" data-action="close">Cancel</button><button class="btn primary" type="submit">Save configuration</button></div></form>');
}
async function inspect(id){
 const record=state.data.records.find(r=>r.id===id);if(!record)return;
 try{
  const result=await api("/api/preflight/"+encodeURIComponent(id));
  const checks=result.checks.map(x=>'<div class="check-item">'+tag(x.status,x.status==="pass"?"":x.status==="blocker"?"danger":"warn")+'<p><strong>'+escape(x.code.replaceAll("_"," "))+'</strong><br>'+escape(x.explanation)+'</p></div>').join("");
  modal("Application preflight · "+id,'<div class="split-detail"><div><h3>'+escape(record.name)+'</h3><dl class="details-list"><dt>Recorded deadline</dt><dd>'+escape(record.deadline||"Unknown")+'</dd><dt>Source status</dt><dd>'+escape(record.verification)+'</dd><dt>Funding</dt><dd>'+escape(record.funding||"Unknown")+'</dd><dt>Eligibility</dt><dd>'+escape(record.eligibility||"Unknown")+'</dd></dl><div class="buttons" style="margin-top:22px">'+minor("Update applicant state","edit-application",id)+'</div></div><div><h3 style="margin-bottom:15px">'+escape(result.counts.blocker||0)+' blockers · '+escape(result.counts.unknown||0)+' unknowns</h3><div class="checks">'+checks+'</div></div></div>');
 }catch(e){toast(e.message)}
}
function applicationModal(id){
 const r=state.data.records.find(x=>x.id===id);if(!r)return;
 const states=["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"];
 const contacts=["unrecorded","to_contact","contacted","awaiting_reply","followup_due","replied","declined","completed"];
 const docs=r.documents||[];
 const body='<form id="applicationForm" data-id="'+escape(id)+'" class="form-grid">'+
 '<div class="field wide"><strong>'+escape(r.name)+'</strong><small>Private override version '+escape(r.private_version||0)+' · Never silently changes the source workbook</small></div>'+
 '<div class="field"><label>Application status</label><select name="status">'+selectChoices(states.map(x=>({id:x,label:x})),r.status)+'</select></div>'+
 '<div class="field"><label>Contact stage</label><select name="contact_status">'+selectChoices(contacts.map(x=>({id:x,label:x})),r.contact_status||"unrecorded")+'</select></div>'+
 '<div class="field"><label>Priority</label><select name="priority">'+selectChoices(["normal","high","low"].map(x=>({id:x,label:x})),r.priority||"normal")+'</select></div>'+
 textField("followup","Next follow-up date",r.followup||"","","date")+
 textField("estimated_hours","Estimated hours to prepare",r.estimated_hours==null?"":r.estimated_hours,"Required for capacity-aware planning","number")+
 area("next_step","Next action",r.next_step||"",3)+area("notes","Private applicant notes",r.notes||"",3)+
 textField("receipt","Submission confirmation link (private)",r.receipt||"","Keep sensitive URLs private")+
 '<div class="field wide"><label>Document readiness</label>'+docs.map(key=>'<div class="list-row"><strong>'+escape(key.replaceAll("_"," "))+'</strong><select data-doc="'+escape(key)+'">'+selectChoices(["unknown","ready","in_progress","not_started","not_applicable"].map(x=>({id:x,label:x})),r.document_states?.[key]||"unknown")+'</select></div>').join("")+'</div>'+
 '<div class="field wide checkbox"><input type="checkbox" name="confirmed_submission" id="ownerConfirms"><label for="ownerConfirms">I confirm that any change to Submitted reflects an actual portal submission. Model text never counts as proof.</label></div>'+
 '<div class="form-actions"><button class="btn" type="button" data-action="close">Cancel</button><button class="btn primary" type="submit">Save private status</button></div></form>';
 modal("Owner record · "+id,body);
}
function workflowRunModal(id){
 const w=state.data.catalog.workflows.find(x=>x.id===id);if(!w)return;
 modal("Run workflow · "+w.label,'<form id="workflowRunForm" data-id="'+escape(id)+'" class="form-grid"><div class="field"><label>Model provider</label>'+providerSelect("provider_id",w.provider_id||"ollama")+'</div><div class="field"><label>Application context</label>'+appSelect()+'</div>'+area("input_text","Additional instructions",w.prompt||"",3)+
 '<div class="field wide checkbox"><input id="workflowCloud" name="cloud_consent" type="checkbox"><label for="workflowCloud">I authorize sending selected evidence to the cloud provider for this manual run if selected.</label></div>'+
 '<div class="form-actions"><button class="btn" type="button" data-action="close">Cancel</button><button type="submit" class="btn primary">Run workflow</button></div></form>');
}

const fieldOpts=(items,current)=>selectChoices(items.map(x=>({id:x,label:x})),current);
function privateModal(kind,id=""){
 const o=state.ops,all={referee:o.referees,reference:o.references,milestone:o.milestones,evidence:o.claims,profile:o.profile?.id?[o.profile]:[]}[kind]||[];
 const r=all.find(x=>x.id===id)||{};
 let fields="";
 if(kind!=="profile")fields=textField("id","Unique private identifier",r.id||"");
 if(kind==="referee"){
  fields+=textField("name","Referee name",r.name||"")+textField("contact","Contact email, private",r.contact||"")+
  textField("affiliation","Institution / affiliation",r.affiliation||"")+area("notes","Notes",r.notes||"",3);
 }else if(kind==="reference"){
  fields+='<div class="field"><label>Referee</label><select name="referee_id" required>'+selectChoices(o.referees.map(x=>({id:x.id,label:x.name})),r.referee_id)+'</select></div>'+
  '<div class="field"><label>Application</label>'+appSelect("application_id",r.application_id||"")+'</div>'+
  '<div class="field"><label>Reference stage</label><select name="status">'+fieldOpts(["not_requested","requested","acknowledged","uploaded","portal_verified","declined"],r.status||"not_requested")+'</select></div>'+
  textField("deadline","Referee submission deadline",r.deadline||"","","date")+
  area("notes","Portal notes / verification",r.notes||"",3);
 }else if(kind==="milestone"){
  fields+='<div class="field"><label>Application</label>'+appSelect("application_id",r.application_id||"")+'</div>'+
  '<div class="field"><label>Milestone type</label><select name="kind">'+fieldOpts(["final","priority","scholarship","referee","supervisor_contact","interview","offer","registration","other"],r.kind||"final")+'</select></div>'+
  textField("date","Milestone date",r.date||"","","date")+textField("time","Cutoff time, when verified",r.time||"","Use HH:MM","time")+
  textField("timezone","Official IANA time zone",r.timezone||"","Example: Europe/London; required when entering a cutoff time")+
  '<div class="field"><label>Verification</label><select name="verification">'+fieldOpts(["unverified","primary_confirmed","needs_review","contradicted","superseded"],r.verification||"unverified")+'</select></div>'+
  textField("source_url","Official evidence URL",r.source_url||"")+area("notes","Evidence and route notes",r.notes||"",2);
 }else if(kind==="evidence"){
  fields+='<div class="field"><label>Application</label>'+appSelect("application_id",r.application_id||"")+'</div>'+
  textField("field","Claim field",r.field||"","Example: funding_eligibility or final_deadline")+
  '<div class="field"><label>Proof status</label><select name="status">'+fieldOpts(["unverified","primary_confirmed","needs_review","contradicted","superseded"],r.status||"unverified")+'</select></div>'+
  textField("source_url","Evidence URL",r.source_url||"")+textField("observed_at","Date inspected",r.observed_at||"","","date")+
  area("assertion","Exact claim or carefully attributed paraphrase",r.assertion||"",3)+area("excerpt","Short original supporting passage",r.excerpt||"",3)+area("notes","Contradictions or caveats",r.notes||"",2);
 }else if(kind==="profile"){
  fields=area("research_topics","Research topics, one per line",(r.research_topics||[]).join("\n"),3)+
  area("skills","Methodological skills, one per line",(r.skills||[]).join("\n"),3)+
  area("projects","Verified research projects, one per line",(r.projects||[]).join("\n"),3)+
  textField("hours_per_week","Available working hours per week",r.hours_per_week||"","Used in the scheduling heuristic","number")+
  '<div class="field wide"><label>Shared document effort in hours</label><small>Only owner-entered estimates; blank values remain unknown.</small>'+
  ["academic_cv","research_statement","transcripts","recommendations","english_proof","research_portfolio"].map(x=>
    '<div class="list-row"><span>'+escape(x.replaceAll("_"," "))+'</span><input aria-label="Hours for '+escape(x)+'" type="number" min="0" max="300" step="0.5" data-resource-hour="'+escape(x)+'" value="'+escape(r.document_effort?.[x]??"")+'"></div>').join("")+'</div>'+
  area("notes","Private profile notes",r.notes||"",2);
 }
 modal((id?"Edit ":"Add ")+kind.replaceAll("_"," "),
 '<form id="privateForm" class="form-grid" data-kind="'+escape(kind)+'">'+fields+
 '<div class="form-actions"><button class="btn" type="button" data-action="close">Cancel</button><button class="btn primary" type="submit">Save privately</button></div></form>');
}
async function submitPrivate(form){
 const kind=form.dataset.kind,value=Object.fromEntries(new FormData(form));
 if(kind==="profile"){
  for(const field of ["research_topics","skills","projects"])
   value[field]=value[field].split(/\n|,/).map(x=>x.trim()).filter(Boolean);
  value.hours_per_week=value.hours_per_week?Number(value.hours_per_week):null;
  value.document_effort=Object.fromEntries([...form.querySelectorAll("[data-resource-hour]")].filter(x=>x.value!=="").map(x=>[x.dataset.resourceHour,Number(x.value)]));
 }
 for(const field of ["date","deadline","time","timezone","source_url","observed_at"])
  if(value[field]==="")delete value[field];
 await api("/api/private/"+encodeURIComponent(kind),value);
 close();await load();toast("Private "+kind+" record saved");
}
async function generateSchedule(form){
 const hours=Number(new FormData(form).get("hours_per_week"));
 const result=await api("/api/schedule",{hours_per_week:hours});
 const warnings=result.unallocated.map(x=>'<div class="list-row"><div><strong>'+escape(x.application_id)+'</strong><p>'+escape(x.hours_unallocated)+' hours unallocated · '+escape(x.deadline)+'</p></div>'+tag("Capacity risk","warn")+'</div>').join("");
 const unknown=result.unknown_effort_or_date.slice(0,30).map(x=>'<div class="list-row"><strong>'+escape(x.application_id)+'</strong><span>'+escape(x.reason)+'</span></div>').join("");
 modal("Capacity plan · provisional",'<div class="notice">'+escape(result.caution)+'</div>'+
 '<div class="kpis">'+metric("SCHEDULED BLOCKS",result.scheduled.length,"Daily time allocations")+metric("AT-RISK APPLICATIONS",result.unallocated.length,"Insufficient hours before cutoff")+
 metric("UNKNOWN EFFORT",result.unknown_effort_or_date.length,"No guessed estimates")+metric("HOURS PER WEEK",result.available_hours_per_week,"Owner-entered")+'</div>'+
 '<div class="grid-two">'+panel("At-risk allocations","Check feasibility",warnings||'<div class="blank">No currently estimated application exceeds its simple capacity bound.</div>')+
 panel("Missing estimates","Enter hours in the relevant application detail",unknown||'<div class="blank">No unknown effort in the evaluated set.</div>')+'</div>'+
 '<p class="subtitle" style="margin-top:20px">The algorithm is deterministic earliest-deadline-first; it is not an admission predictor or fully optimized prerequisite scheduler.</p>');
}

async function viewRun(id){
 const run=state.data.runs.find(r=>r.id===id);if(!run)return;
 modal("Recorded AI analysis",'<div class="row-meta" style="margin-bottom:19px">'+tag(run.agent_id)+tag(run.provider_id)+tag(run.status)+'</div><pre class="terminal">'+escape(run.text||"No output")+'</pre><p class="subtitle" style="margin-top:15px">Proposed output. Source snapshot: '+escape(run.source_as_of||"unknown")+'. No application was automatically changed.</p>');
}
async function submitConfig(form){
 const kind=form.dataset.kind, raw=Object.fromEntries(new FormData(form));
 let body={...raw};
 if(kind==="provider"){
  body.local=form.elements.local.checked;
  body.max_output_tokens=Number(raw.max_output_tokens);
 }else if(kind==="agent"){
  if(body.tools.trim())body.tools=body.tools.split(",").map(x=>x.trim()).filter(Boolean);
  else delete body.tools;
 }else if(kind==="workflow"){
  body.enabled=form.elements.enabled.checked;
  body.cloud_consent=form.elements.cloud_consent.checked;
  body.steps=body.steps.split(",").map(x=>x.trim()).filter(Boolean);
 }
 await api("/api/catalog/"+kind,body);
 close();await load();toast("Configuration saved privately");
}
async function submitApplication(form){
 const id=form.dataset.id,r=state.data.records.find(x=>x.id===id),raw=Object.fromEntries(new FormData(form));
 const patch={status:raw.status,contact_status:raw.contact_status,priority:raw.priority,
  followup:raw.followup||null,next_step:raw.next_step,notes:raw.notes,receipt:raw.receipt,
  document_states:Object.fromEntries([...form.querySelectorAll("[data-doc]")].map(el=>[el.dataset.doc,el.value]))};
 if(raw.estimated_hours!=="")patch.estimated_hours=Number(raw.estimated_hours);
 if(raw.status==="submitted"&&r.status!=="submitted"){
  if(!form.elements.confirmed_submission.checked)throw Error("Actual portal submission must be explicitly confirmed");
  patch.confirmed_submission=true;
 }
 await api("/api/applications/"+encodeURIComponent(id)+"/update",{expected_version:r.private_version||0,patch});
 close();await load();toast("Private applicant state updated. Public GitHub source unchanged.");
}
async function execute(kind,data){
 if(state.busy)return;state.busy=true;
 const form=kind==="agent"?$("agentRunForm"):$("workflowRunForm");
 const submit=form?.querySelector('[type="submit"]');if(submit)submit.disabled=true;
 try{
  if(isCloud(data.provider_id) && data.cloud_consent!==true)throw Error("Cloud execution requires explicit disclosure consent");
  const result=await api(kind==="agent"?"/api/agents/run":"/api/workflows/run",data);
  await load();modal("Analysis completed · proposal",'<div class="row-meta" style="margin-bottom:15px">'+tag(result.agent_id)+tag(result.model)+tag("No external actions")+'</div><pre class="terminal">'+escape(result.text)+'</pre><p class="subtitle" style="margin-top:15px">Review before applying any recommendation. Model output is not verification, submission or correspondence.</p><div class="buttons" style="margin-top:15px">'+btn("Close","close","","primary")+'</div>');
 }catch(error){toast(error.message)}
 finally{state.busy=false;if(submit)submit.disabled=false}
}
async function load(){
 try{
  const data=await api("/api/bootstrap");
  state.data=data;state.ops=await api("/api/operations");$("connection").classList.add("live");$("connection").lastChild.textContent=" Private runtime connected";
  render();
 }catch(error){
  state.data=null;$("connection").classList.remove("live");$("connection").lastChild.textContent=" Private runtime unavailable";
  $("workspace").innerHTML='<section class="boot"><span class="boot-line"></span><p class="eyebrow">LOCAL EXECUTION REQUIRED</p><h1>AI Studio runs through a private local service.</h1><p>The public GitHub Pages site cannot securely host local LLM connections, cloud API keys, private applicant state or scheduled agent execution. Start the service from the repository checkout:</p><code class="instruction">python -m phd_agents serve --port 8765</code><p>Then open <strong>http://127.0.0.1:8765/ai-studio.html</strong> on that computer. No model calls occur before your explicit action.</p><button class="btn primary" type="button" data-action="refresh">Retry local connection</button></section>';
 }
}
document.addEventListener("click",async e=>{
 const view=e.target.closest("[data-view]");if(view){nav(view.dataset.view);return}
 const el=e.target.closest("[data-action]");if(!el)return;
 const action=el.dataset.action,id=el.dataset.id;
 if(action==="close"){close();return}
 if(action==="nav"){nav(id);return}
 if(action==="refresh"){await load();return}
 if(action==="new-agent"){configModal("agent");return}
 if(action==="new-provider"){configModal("provider");return}
 if(action==="new-workflow"){configModal("workflow");return}
 if(action==="edit-provider"){configModal("provider",id);return}
  if(action==="provider-models"){
   const provider=state.data.catalog.providers.find(p=>p.id===id);
   if(!provider||state.busy)return;
   const consent=!provider.local;
   if(consent&&!confirm("Query "+provider.label+" for available models? No applicant records are transmitted."))return;
   state.busy=true;
   try{
    const result=await api("/api/providers/models",{provider_id:id,cloud_consent:consent});
    await load();
    const list=result.models.slice(0,40).map(model=>
      '<div class="model-option"><div><strong>'+escape(model.name)+'</strong><small>'+escape(model.id)+'</small></div>'+
      '<button type="button" class="mini-button" data-action="select-model" data-id="'+escape(id)+'" data-model="'+escape(model.id)+'">Select model</button></div>').join("");
    modal("Model discovery · "+provider.label,'<p class="subtitle">Catalog responded in '+escape(result.latency_ms)+' ms. Listed models may not all support chat inference.</p>'+
     '<div class="model-browser">'+(list||'<div class="blank">No model IDs were returned. Check permissions and endpoint configuration.</div>')+'</div>');
   }catch(error){toast(error.message)}
   finally{state.busy=false}
   return;
  }
  if(action==="select-model"){
   const provider=state.data.catalog.providers.find(p=>p.id===id);
   if(!provider)return;
   try{
    await api("/api/catalog/provider",{...provider,model:el.dataset.model});
    close();await load();toast("Model configured. Test inference to verify compatibility.");
   }catch(error){toast(error.message)}
   return;
  }
 if(action==="edit-agent"){configModal("agent",id);return}
 if(action==="edit-workflow"){configModal("workflow",id);return}
 if(action==="inspect"){await inspect(id);return}
 if(action==="edit-application"){applicationModal(id);return}
 if(action==="private-ics"){window.location.assign("/api/calendar.ics");return}
 if(action==="provider-probe"){
   const p=state.data.catalog.providers.find(x=>x.id===id);
   if(!p||state.busy)return;
   const consent=!p.local;
   if(consent&&!confirm("Send a diagnostic request to "+p.label+"? This may incur API charges. No applicant records are included."))return;
   state.busy=true;
   try{
    const result=await api("/api/providers/probe",{provider_id:id,cloud_consent:consent});
    await load();
    modal("Inference check · "+p.label,'<div class="row-meta">'+tag(result.status)+tag(result.model)+'</div><pre class="terminal" style="margin-top:18px">'+escape(result.response)+'</pre><p class="subtitle" style="margin-top:12px">One successful response is not a guarantee of provider uptime or future model availability.</p>');
   }catch(error){toast(error.message)}
   finally{state.busy=false}
   return;
  }
 if(action==="new-private"){privateModal(id);return}
 if(action==="edit-private"){const at=id.indexOf(":");privateModal(id.slice(0,at),id.slice(at+1));return}
 if(action==="generate-schedule"){try{await generateSchedule($("capacityForm"))}catch(err){toast(err.message)}return}
 if(action==="workflow-run"){workflowRunModal(id);return}
 if(action==="view-run"){await viewRun(id);return}
 if(action==="select-agent"){
  nav("agents");const picker=document.querySelector('#agentRunForm [name="agent_id"]');if(picker)picker.value=id;return
 }
 if(action==="scheduler-tick"){
  if(!confirm("Run eligible, explicitly enabled schedules now? Configured local and approved cloud models may be invoked."))return;
  try{const r=await api("/api/scheduler/tick",{});toast("Scheduler checked "+r.results.length+" eligible workflows");await load()}catch(err){toast(err.message)}return
 }
});
document.addEventListener("submit",async e=>{
 const form=e.target;if(!["configForm","applicationForm","agentRunForm","workflowRunForm","privateForm","capacityForm","settingsForm"].includes(form.id))return;
 e.preventDefault();try{
 if(form.id==="configForm"){await submitConfig(form);return}
  if(form.id==="settingsForm"){
   const values=Object.fromEntries(new FormData(form));
   values.max_runs_per_tick=Number(values.max_runs_per_tick);
   values.max_cloud_model_calls_per_day=Number(values.max_cloud_model_calls_per_day);
   await api("/api/settings",values);
   await load();toast("Private runtime preferences saved");
   return;
  }
 if(form.id==="applicationForm"){await submitApplication(form);return}
 if(form.id==="privateForm"){await submitPrivate(form);return}
 if(form.id==="capacityForm"){await generateSchedule(form);return}
 const data=Object.fromEntries(new FormData(form));data.cloud_consent=form.elements.cloud_consent.checked;
 if(form.id==="workflowRunForm"){data.workflow_id=form.dataset.id;await execute("workflow",data)}
 else await execute("agent",data);
 }catch(error){toast(error.message)}
});
document.addEventListener("change",e=>{
 if(e.target.id==="mobileStudioView"){nav(e.target.value);return}
 if(e.target.id==="providerFilter"){state.providerFilter=e.target.value;render()}
});
document.addEventListener("input",e=>{
 if(e.target.id==="appSearch"){
  const pos=e.target.selectionStart;state.query=e.target.value;render();
  const search=$("appSearch");search?.focus();search?.setSelectionRange(pos,pos)
 }
});
document.addEventListener("keydown",e=>{
 if(e.key==="Escape"&&$("dialogLayer").children.length){close();return}
 if(e.key!=="Tab"||!$("dialogLayer").children.length)return;
 const nodes=[...$("dialogLayer").querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])')].filter(n=>n.getClientRects().length);
 if(!nodes.length)return;
 const first=nodes[0],last=nodes[nodes.length-1];
 if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
 else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
});
$("refresh").addEventListener("click",load);
const initial=location.hash.replace("#","");if(VIEWS[initial])state.view=initial;
window.addEventListener("hashchange",()=>{const view=location.hash.replace("#","");if(VIEWS[view]&&state.view!==view){state.view=view;render()}});
load();
})();
