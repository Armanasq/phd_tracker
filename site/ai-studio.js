(() => {
"use strict";
const $ = id => document.getElementById(id);
const escape = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = {data:null,view:"overview",query:"",selected:"",busy:false,filter:"all"};
const VIEWS = {overview:"Decision desk",agents:"AI agents",workflows:"Automation",providers:"Models & providers",applications:"Applications",activity:"Run history"};
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
function providerSelect(name="provider_id",current="ollama"){
 return '<select name="'+name+'" required>'+selectChoices(state.data.catalog.providers.map(p=>({id:p.id,label:p.label+" / "+p.model})),current)+'</select>';
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
 '<form id="agentRunForm" class="form-grid"><div class="field"><label>Research agent</label><select name="agent_id" required>'+selectChoices(d.catalog.agents.map(a=>({id:a.id,label:a.label})),d.catalog.agents[0]?.id)+'</select></div>'+
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
 '<div class="cards two">'+d.catalog.workflows.map(w=>'<article class="catalog-card"><div class="catalog-top"><span class="catalog-badge">'+escape(w.id)+'</span>'+tag(w.enabled?"Enabled":"Disabled",w.enabled?"":"warn")+'</div><h3>'+escape(w.label)+'</h3><p>'+escape(w.description)+'</p><div class="row-meta">'+tag(w.schedule)+tag(w.agent_id)+tag(w.provider_id||"ollama")+'</div><div class="buttons">'+minor("Edit workflow","edit-workflow",w.id)+minor("Run now","workflow-run",w.id)+'</div></article>').join("")+'</div>';
}
function providers(){
 const d=state.data;
 return heading("04 / MODEL INFRASTRUCTURE","Local and cloud models","Configure OpenAI-compatible inference, Azure OpenAI, Anthropic, Gemini or OpenRouter; use the local runtime for credentials and execution.",btn("Add model provider","new-provider","","primary"))+
 '<div class="notice">Provider entries contain model identifiers and credential environment-variable names only. No secret values are saved or displayed. A listed provider is not necessarily reachable until its endpoint and credentials are configured.</div>'+
 '<div class="cards">'+d.catalog.providers.map(p=>'<article class="catalog-card"><div class="catalog-top"><span class="catalog-badge">'+escape(p.kind)+'</span>'+tag(p.local?"Local":"Cloud",p.local?"":"warn")+'</div><h3>'+escape(p.label)+'</h3><p class="mono">'+escape(p.model)+'<br>'+escape(p.base_url)+'</p><div class="row-meta">'+tag(p.api_key_env||"No key required")+'</div><div class="buttons">'+minor("Configure","edit-provider",p.id)+'</div></article>').join("")+'</div>';
}
function applications(){
 const list=state.data.records.filter(r=>r.record_type==="tracked").filter(r=>(r.name+" "+r.id+" "+r.topic).toLowerCase().includes(state.query.toLowerCase())).slice(0,160);
 return heading("05 / APPLICATION CONTROL","Evidence-backed applications","Inspect preflight proof obligations, update private owner state, and retain status after portal submission.",btn("Run preflight agent","nav","agents","primary"))+
 '<div class="controls"><input id="appSearch" class="search" type="search" placeholder="Find a programme, identifier or topic…" value="'+escape(state.query)+'" aria-label="Filter applications"><span class="tag neutral">'+list.length+' applications</span></div>'+
 '<section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Opportunity</th><th>Deadline</th><th>Stage</th><th>Source</th><th>Actions</th></tr></thead><tbody>'+
 list.map(r=>'<tr><td><strong>'+escape(r.name)+'</strong><small>'+escape(r.id)+'</small></td><td>'+escape(r.deadline||"Unknown")+(isExpired(r)?'<small>Recorded date passed</small>':'')+'</td><td>'+tag(r.status,"neutral")+'</td><td>'+tag(r.verification,["source_verified","owner_verified"].includes(r.verification)?"":"warn")+'</td><td>'+minor("Preflight","inspect",r.id)+' '+minor("Update","edit-application",r.id)+'</td></tr>').join("")+'</tbody></table></div></section>';
}
function activity(){
 const runs=state.data.runs||[],audit=state.data.activity||[];
 return heading("06 / PROVENANCE","Run history and audit trail","Stored analysis proposals and owner actions. No generated answer silently updates an application.",btn("Refresh","refresh"))+
 '<div class="grid-two">'+panel("Agent run ledger",runs.map(r=>'<div class="list-row"><div><strong>'+escape(r.agent_id)+'</strong><p>'+escape(r.created_at)+' · '+escape(r.provider_id)+' · '+escape(r.status)+'</p><div class="row-meta">'+tag(r.model||"model unavailable")+(r.application_id?tag(r.application_id):"")+'</div></div>'+minor("Read output","view-run",r.id)+'</div>').join("")||'<div class="blank">No AI runs have been recorded.</div>')+
 panel("Audit events",'<div class="timeline">'+audit.map(a=>'<div class="timeline-item"><strong>'+escape(a.action)+'</strong><time>'+escape(a.created_at)+'</time><span class="code">'+escape(a.subject)+'</span></div>').join("")+'</div>'||'<div class="blank">No recorded events.</div>')+'</div>';
}
function render(){
 const d=state.data;if(!d)return;
 const actual={overview,agents,workflows,providers,applications,activity};
 $("crumb").textContent=VIEWS[state.view];
 document.querySelectorAll("[data-view]").forEach(b=>{b.classList.toggle("active",b.dataset.view===state.view);if(b.dataset.view===state.view)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current")});
 $("workspace").innerHTML=actual[state.view]();
}
function modal(title,body){
 $("dialogLayer").innerHTML='<div class="overlay"><section class="dialog" role="dialog" aria-modal="true" aria-label="'+escape(title)+'"><div class="dialog-head"><h2>'+escape(title)+'</h2><button type="button" class="dialog-close" data-action="close" aria-label="Close dialog">×</button></div><div class="dialog-body">'+body+'</div></section></div>';
 $("dialogLayer").querySelector(".dialog-close")?.focus();
}
function close(){ $("dialogLayer").innerHTML="" }
const textField=(name,label,value="",hint="",type="text")=>'<div class="field"><label for="f_'+escape(name)+'">'+escape(label)+'</label><input id="f_'+escape(name)+'" type="'+type+'" name="'+escape(name)+'" value="'+escape(value)+'"'+(name==="id"?' required pattern="[a-z][a-z0-9_-]{1,63}"':"")+'>'+ (hint?'<small>'+escape(hint)+'</small>':"")+'</div>';
const area=(name,label,value="",rows=4)=>'<div class="field wide"><label for="f_'+escape(name)+'">'+escape(label)+'</label><textarea id="f_'+escape(name)+'" name="'+escape(name)+'" rows="'+rows+'">'+escape(value)+'</textarea></div>';
function configModal(kind,id=""){
 const d=state.data,entries=d.catalog[kind+"s"]||[],old=entries.find(p=>p.id===id)||{};
 let body="";
 if(kind==="provider"){
  body=textField("id","Provider identifier",old.id||"")+textField("label","Display name",old.label||"")+
   '<div class="field"><label>Adapter</label><select name="kind">'+selectChoices(["openai_compatible","azure_openai","anthropic"].map(z=>({id:z,label:z})),old.kind||"openai_compatible")+'</select></div>'+
   textField("model","Model ID / deployment",old.model||"")+textField("base_url","API base URL",old.base_url||"http://127.0.0.1:11434/v1","Local HTTP requires a loopback address")+
   textField("api_key_env","Credential environment variable",old.api_key_env||"","Never enter the credential value here")+
   textField("max_output_tokens","Max response tokens",old.max_output_tokens||1200,"64–4096","number")+
   '<div class="field"><label>Token parameter</label><select name="token_parameter">'+selectChoices(["max_tokens","max_completion_tokens"].map(z=>({id:z,label:z})),old.token_parameter||"max_tokens")+'</select></div>'+
   '<div class="field wide checkbox"><input type="checkbox" id="localProvider" name="local" '+(old.local?"checked":"")+'><label for="localProvider">Local or self-hosted endpoint (HTTP only permitted on loopback)</label></div>';
 }else if(kind==="agent"){
  body=textField("id","Agent identifier",old.id||"")+textField("label","Agent name",old.label||"")+
  area("description","Purpose and human-facing description",old.description||"",2)+
  area("instructions","Specialized system instructions",old.instructions||"",7);
 }else{
  body=textField("id","Workflow identifier",old.id||"")+textField("label","Workflow name",old.label||"")+
  '<div class="field"><label>Assigned agent</label><select name="agent_id">'+selectChoices(d.catalog.agents.map(x=>({id:x.id,label:x.label})),old.agent_id||"portfolio_planner")+'</select></div>'+
  '<div class="field"><label>Schedule</label><select name="schedule">'+selectChoices(["manual","daily","twice_daily","weekly"].map(z=>({id:z,label:z})),old.schedule||"manual")+'</select></div>'+
  '<div class="field"><label>Provider for scheduled runs</label>'+providerSelect("provider_id",old.provider_id||"ollama")+'</div>'+
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
 }else if(kind==="workflow"){
  body.enabled=form.elements.enabled.checked;
  body.cloud_consent=form.elements.cloud_consent.checked;
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
  state.data=data;$("connection").classList.add("live");$("connection").lastChild.textContent=" Private runtime connected";
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
 if(action==="edit-agent"){configModal("agent",id);return}
 if(action==="edit-workflow"){configModal("workflow",id);return}
 if(action==="inspect"){await inspect(id);return}
 if(action==="edit-application"){applicationModal(id);return}
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
 const form=e.target;if(!["configForm","applicationForm","agentRunForm","workflowRunForm"].includes(form.id))return;
 e.preventDefault();try{
 if(form.id==="configForm"){await submitConfig(form);return}
 if(form.id==="applicationForm"){await submitApplication(form);return}
 const data=Object.fromEntries(new FormData(form));data.cloud_consent=form.elements.cloud_consent.checked;
 if(form.id==="workflowRunForm"){data.workflow_id=form.dataset.id;await execute("workflow",data)}
 else await execute("agent",data);
 }catch(error){toast(error.message)}
});
document.addEventListener("input",e=>{
 if(e.target.id==="appSearch"){
  const pos=e.target.selectionStart;state.query=e.target.value;render();
  const search=$("appSearch");search?.focus();search?.setSelectionRange(pos,pos)
 }
});
document.addEventListener("keydown",e=>{if(e.key==="Escape")close()});
$("refresh").addEventListener("click",load);
const initial=location.hash.replace("#","");if(VIEWS[initial])state.view=initial;
window.addEventListener("hashchange",()=>{const view=location.hash.replace("#","");if(VIEWS[view]&&state.view!==view){state.view=view;render()}});
load();
})();
