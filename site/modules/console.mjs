import {createOperations} from "./operations.mjs";
import {createBrowserModel} from "./browser-model.mjs";
import {renderSourceObservations} from "./source-observations.mjs";
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pretty = value => String(value ?? "").replaceAll("_"," ").replace(/\b\w/g, c => c.toUpperCase());
const short = (value, length=125) => String(value ?? "").slice(0,length);
const choose = (items,current) => items.map(([value,title]) => '<option value="'+esc(value)+'"'+(value===current?' selected':'')+'>'+esc(title)+'</option>').join('');
const btn = (title,action,id="",kind="quiet",extra="") => '<button type="button" class="os-btn '+kind+'" data-os-action="'+esc(action)+'" data-id="'+esc(id)+'" '+extra+'>'+title+'</button>';
const stamp = value => value ? new Date(value).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"}) : "Not tested";
const cleanId = value => String(value||"").trim().toLowerCase().replace(/[^a-z0-9_-]+/g,"_").replace(/^_+/,"").slice(0,64);
const opt = (items,value) => choose(items,value);

export function createConsole({notify,onChange,navigate,getRecords,getSourceRecords,onReload,getView}) {
 const state = {online:false,loading:false,data:null,tab:"connections",selectedProvider:null,selectedAgent:null,selectedWorkflow:null,showAllProviders:false,models:{},schedulePreview:null,schedulePreviewRequested:false,workflowPreview:null,scheduleTick:null,diagnostics:null,latestBackup:null,busy:false,prompt:"",lastAnswer:null,selectedApplication:"",sourceView:"dashboard",routeDraft:null,message:"",jobs:[],observability:null,sourceObservations:[],sourceObservationsLoading:false,sourceObservationsError:"",sourceObservationFilter:"all"};
 const providers = () => state.data?.catalog?.providers || [];
 const agents = () => state.data?.catalog?.agents || [];
 const workflows = () => state.data?.catalog?.workflows || [];
 const prefs = () => state.data?.settings || {};
 const checks = () => state.data?.provider_states || {};
 const routing = () => state.data?.routing || {};
 const active = () => providers().find(p => p.id === prefs().default_provider);
 const isLive = () => state.online && !!state.data;
 const stateText = name => ({responded:"Verified inference",reachable:"Catalog reachable",stale:"Retest required",needs_reverification:"Credential changed · retest",ready_to_test:"Not tested",needs_setup:"Needs setup",failed:"Test failed"})[name] || "Not tested";
 const checkTone = name => name==="responded"?"good":name==="needs_setup"||name==="needs_reverification"||name==="stale"||name==="failed"?"warn":"muted";
 const status = p => checks()[p.id]?.state || "ready_to_test";
 const routeFor = agent => routing().agent_assignments?.[agent] || null;
 const loadingNotice = message => '<div class="os-hint" role="status">'+esc(message)+'</div>';

 function heading(kicker,title,description,actions="") {
  return '<div class="os-head"><div><div class="os-kicker">'+esc(kicker)+'</div><h1>'+esc(title)+'</h1><p>'+esc(description)+'</p></div><div class="os-head-actions">'+actions+'</div></div>';
 }
 function box(title,desc,body,extraClass="") {
  return '<section class="os-panel '+extraClass+'"><div class="os-panel-heading"><div><h2>'+esc(title)+'</h2>'+(desc?'<p>'+esc(desc)+'</p>':'')+'</div></div>'+body+'</section>';
 }
 function field(label,name,value="",type="text",more="") {
  return '<label class="os-field"><span>'+esc(label)+'</span><input name="'+esc(name)+'" type="'+esc(type)+'" value="'+esc(value)+'" '+more+'></label>';
 }
 function selector(label,name,values,value="") {
  return '<label class="os-field"><span>'+esc(label)+'</span><select name="'+esc(name)+'">'+opt(values,value)+'</select></label>';
 }
 function footnote(text) {return '<p class="os-footnote">'+esc(text)+'</p>';}
 function note() {return state.message?'<div class="os-message" role="status">'+esc(state.message)+'</div>':'';}
 function connectionChip(p,more="") {
  const item = p ? checks()[p.id] : null;
  const label = item?.state || "needs_setup";
  return '<span class="os-chip '+checkTone(label)+'"><span class="os-dot"></span>'+esc(more||stateText(label))+'</span>';
 }
 function providerLink(p) {
  return '<span class="os-provider-name">'+esc(p.label)+'</span><span class="os-meta">'+esc(p.model)+'</span>';
 }
 function routeDescription(agentId) {
  const route=routeFor(agentId);
  if(!route) return 'Routing unavailable';
  return route.provider_label+' · '+route.model+' · '+(route.source==="agent_assignment"?"Agent override":"Workspace default");
 }
 function providerForAgent(agentId,override="auto") {
  const id=override&&override!=="auto"?override:routeFor(agentId)?.provider_id;
  return providers().find(provider=>provider.id===id)||null;
 }
 function cloudConsentForAgents(agentIds,override="auto") {
  const destinations=agentIds.map(agentId=>providerForAgent(agentId,override));
  if(destinations.some(provider=>!provider)){
   notify("Cannot verify the selected provider route. Reconfigure agent routing in Settings.");
   return {allowed:false,cloud_consent:false};
  }
  const remote=[...new Map(destinations.filter(provider=>!provider.local).map(provider=>[provider.id,provider])).values()];
  if(!remote.length)return {allowed:true,cloud_consent:false};
  const labels=remote.map(provider=>provider.label+" ("+provider.base_url+")").join(", ");
  const allowed=window.confirm("Send applicant evidence and your task to "+labels+"? Cloud processing can incur charges. Consent is limited to this run. No faculty emails or university submissions will be sent.");
  return {allowed,cloud_consent:allowed};
 }
 function badge(text,tone="") {return '<span class="os-badge '+tone+'">'+esc(text)+'</span>';}

 async function request(path,body) {
  const controller = new AbortController();
  const options = {cache:"no-store",signal:controller.signal,headers:{"Accept":"application/json"}};
  if(body!==undefined){options.method="POST";options.headers["Content-Type"]="application/json";options.body=JSON.stringify(body);if(["/api/agents/run","/api/workflows/run"].includes(path)&&globalThis.crypto?.randomUUID)options.headers["Idempotency-Key"]=globalThis.crypto.randomUUID();}
  const response = await fetch("./"+path.replace(/^\//,""),options);
  const result = await response.json().catch(()=>({error:"The private backend returned an unreadable response"}));
  if(!response.ok) throw new Error(result.error || "Private runtime returned HTTP "+response.status);
  return result;
 }
 async function connect({silent=false}={}) {
  if(!["localhost","127.0.0.1"].includes(location.hostname)||location.protocol!=="http:"){
   state.online=false;
   state.message="";
   if(!silent)onChange();
   return false;
  }
  try{
   const data=await request("/api/bootstrap");
   if(data.security?.local_only!==true||!Array.isArray(data.catalog?.providers))throw new Error("Private runtime identity could not be verified");
   state.online=true;
   state.data=data;
   const jobs=await request("/api/jobs").catch(()=>({jobs:[]}));
   state.jobs=Array.isArray(jobs.jobs)?jobs.jobs:[];
   const observations=await request("/api/source-observations").catch(error=>({error:String(error.message||error)}));
   state.sourceObservationsError=observations.error||"";
   state.sourceObservations=Array.isArray(observations.observations)?observations.observations:[];
   const observed=await request("/api/observability").catch(()=>null);
   state.observability=observed?.schema_version===1?observed:null;
   state.selectedAgent=agents().some(a=>a.id===state.selectedAgent)?state.selectedAgent:(prefs().default_agent||agents()[0]?.id);
   state.selectedProvider=providers().some(p=>p.id===state.selectedProvider)?state.selectedProvider:prefs().default_provider;
   state.selectedWorkflow=workflows().some(w=>w.id===state.selectedWorkflow)?state.selectedWorkflow:workflows()[0]?.id;
   if(!silent)onChange();
   return true;
  }catch(error){
   state.online=false;
   state.data=null;
   if(!silent)onChange();
   return false;
  }
 }
 async function change(task) {
  if(state.busy)return;
  state.busy=true;
  state.message="";
  onChange();
  try{
   await task();
   await connect({silent:true});
   state.schedulePreviewRequested=false;state.schedulePreview=null;
  }catch(error){
   state.message=short(error.message || "Operation failed",260);
   notify(state.message);
  }finally{
   state.busy=false;
   onChange();
  }
 }
 function chooseTemplate() {
  const available = providers().slice().sort((a,b)=>
   Number(a.id!==prefs().default_provider)-Number(b.id!==prefs().default_provider)||
   Number(status(b)==="responded")-Number(status(a)==="responded")||
   a.label.localeCompare(b.label));
  return available;
 }
 function offline(view) {
  return '<div class="os-page">'+heading("PRIVATE INFERENCE / CONNECTION REQUIRED","Connect the private workspace",
    "Use the same interface locally for interactive models. On GitHub Pages, authenticated scheduled AI workflows run in GitHub Actions with repository or environment secrets, never in the browser.")+
   '<div class="os-offline"><div class="os-offline-graphic"><div class="os-core"></div><div class="os-orbit a"></div><div class="os-orbit b"></div></div>'+
   '<div><div class="os-kicker">SAME INTERFACE · PRIVATE BACKEND</div><h2>Start your workspace locally</h2><p>From the repository checkout, start the Python service. Open the resulting local address and configure a model once in Settings. No separate AI Studio or external credentials are needed for an unauthenticated local model.</p>'+
   '<div class="os-code">python -m phd_agents serve --port 8765</div>'+
   '<div class="os-actions">'+btn("Copy start command","copy-command","","primary")+btn("Retry connection","reconnect","","quiet")+'</div>'+
   '<p class="os-note">Then open <strong>http://127.0.0.1:8765/#settings</strong>. The public site never receives provider keys, private applicant data, or agent execution logs.</p></div></div>'+
   '<section class="os-panel"><div class="os-panel-heading"><div><h2>Run AI workflows on GitHub</h2><p>Configure encrypted environment secrets for scheduled verification triage; no local server is required for batch jobs.</p></div></div>'+
   '<div class="os-actions"><a class="os-btn quiet" href="'+esc((document.querySelector(".side-link")?.href||"https://github.com/Armanasq/phd_tracker")+"/actions/workflows/hosted-ai-advisories.yml")+'" target="_blank" rel="noopener noreferrer">Hosted AI workflow</a> '+
   '<a class="os-btn quiet" href="'+esc((document.querySelector(".side-link")?.href||"https://github.com/Armanasq/phd_tracker")+"/blob/main/docs/HOSTED_ACTIONS_AI.md")+'" target="_blank" rel="noopener noreferrer">Setup and security</a></div>'+
   '<p class="os-note">Secrets stay in GitHub Actions. Hosted verification proposals are batch results, not live chatbot replies. Interactive chat still requires an authenticated private service.</p></section></div>';
 }

 function steps() {
  const p=active(),ok=p&&status(p)==="responded";
  return '<div class="os-connection-steps"><div class="os-step '+(p?"done":"")+'"><strong>01</strong><span>Register endpoint</span></div>'+
   '<div class="os-step '+(ok?"done":"")+'"><strong>02</strong><span>Verify response</span></div>'+
   '<div class="os-step '+(ok?"done":"")+'"><strong>03</strong><span>Automatic routing</span></div></div>';
 }
 function tabs() {
  const all=[["connections","Connections"],["routing","Model routing"],["agents","Agent builder"],["workflows","Automations"],["preferences","Preferences"]];
  return '<nav class="os-tabs" aria-label="Settings sections">'+all.map(([name,title])=>
   '<button type="button" class="'+(state.tab===name?"active":"")+'" data-os-action="tab" data-id="'+name+'"'+(state.tab===name?' aria-current="page"':'')+'>'+title+'</button>').join("")+'</nav>';
 }
 function providerEdit() {
  if(state.selectedProvider==="__new__")return null;
  return providers().find(p=>p.id===state.selectedProvider) || active() || null;
 }
 function registry() {
  const ordered=chooseTemplate();
  const visible=state.showAllProviders?ordered:ordered.filter(p=>
   p.id===prefs().default_provider||status(p)==="responded"||
   !["ollama","vllm","openai","azure","azure_deploy","anthropic","gemini","openrouter","lmstudio","groq","deepseek","xai","together","fireworks","mistral","cerebras"].includes(p.id));
  const limited=visible.length?visible:ordered.slice(0,2);
  return '<div class="os-registry">'+limited.map(p=>{
   const isActive=p.id===prefs().default_provider;
   const st=checks()[p.id]||{};
   return '<article class="os-provider-row '+(isActive?"is-default ":"")+(p.id===state.selectedProvider?"is-selected":"")+'">'+
    '<button type="button" class="os-provider-select" data-os-action="edit-provider" data-id="'+esc(p.id)+'"><span class="os-provider-icon">'+(p.local?"L":"C")+'</span>'+
    '<span><strong>'+esc(p.label)+'</strong><small>'+esc(p.model)+'</small></span></button>'+
    '<div class="os-provider-tail">'+connectionChip(p,isActive&&st.state==="responded"?"Active model":null)+
    (isActive?badge("Default","solid"):"")+'</div>'+
    '<div class="os-provider-row-actions">'+btn("Discover","models",p.id,"link")+
    btn("Test","test",p.id,"link")+
    btn("Use","activate",p.id,"link")+'</div></article>';
  }).join("")+'</div>'+
   '<div class="os-registry-bottom">'+btn(state.showAllProviders?"Show configured":"View all provider templates","toggle-providers","","quiet")+
   '<span class="os-meta">'+providers().length+' registered · '+providers().filter(p=>status(p)==="responded").length+' verified</span></div>';
 }
 function providerForm() {
  const original=providerEdit(),isNew=!original;
  const p=original||{id:"",label:"",kind:"openai_compatible",base_url:"http://127.0.0.1:8000/v1",model:"",api_key_env:"",local:true,max_output_tokens:1200,token_parameter:"max_tokens"};
  const health=original?checks()[original.id]:null;
  const options=[["openai_compatible","OpenAI-compatible · Chat Completions"],["azure_openai","Azure OpenAI v1"],["azure_deployment","Azure deployment API"],["anthropic","Anthropic native API"]];
  return '<div class="os-editor-top"><div><div class="os-kicker">CONNECTION EDITOR</div><h2>'+(isNew?"Register endpoint":esc(p.label))+'</h2></div>'+
   (isNew?badge("New connection","primary"):connectionChip(p))+'</div>'+
   '<form data-os-form="provider" class="os-form" autocomplete="off">'+
   '<div class="os-form-two">'+field("Connection ID","id",p.id,"text",'required pattern="[a-z][a-z0-9_-]{1,63}" '+(isNew?"":'readonly'))+
   field("Display name","label",p.label,"text","required maxlength=100")+'</div>'+
   selector("API adapter","kind",options,p.kind)+
   field("Base URL","base_url",p.base_url,"url",'required spellcheck="false"')+
   '<div class="os-form-two">'+field("Model / deployment ID","model",p.model,"text",'required maxlength=128 spellcheck="false"')+
   field("Credential variable","api_key_env",p.api_key_env||"","text",'placeholder="e.g. OPENAI_API_KEY" spellcheck="false"')+'</div>'+
   field("API key (private runtime only)","credential","","password",'placeholder="'+(health?.credential_configured?"Leave blank to preserve saved key":"Enter credential if required")+'" autocomplete="new-password"')+
   '<div class="os-form-two">'+field("Max output tokens","max_output_tokens",p.max_output_tokens??1200,"number",'min="64" max="16384" step="1" required')+
   field("Request timeout (seconds)","timeout_seconds",p.timeout_seconds??55,"number",'min="10" max="180" step="1" required')+'</div>'+
   '<div class="os-form-two">'+field("Temperature · optional","temperature",p.temperature??"","number",'min="0" max="'+(p.kind==="anthropic"?"1":"2")+'" step="0.05" placeholder="Model default"')+
   selector("Token limit parameter","token_parameter",[["max_tokens","max_tokens"],["max_completion_tokens","max_completion_tokens"]],p.token_parameter||"max_tokens")+'</div>'+
   (p.kind==="azure_deployment"?field("Azure API version","api_version",p.api_version||"2024-10-21","text",'pattern="20[2-9][0-9]-[0-9]{2}-[0-9]{2}(-preview)?"'):field("Azure API version (deployment adapter only)","api_version",p.api_version||"","text",'placeholder="Used for Azure deployment API only"'))+
   '<label class="os-check"><input name="local" type="checkbox" '+(p.local?"checked":"")+'> <span>Local endpoint (HTTP permitted on loopback only)</span></label>'+
   '<label class="os-check"><input name="auto_activate" type="checkbox" checked> <span>Set as default model after successful inference test</span></label>'+
   '<label class="os-check os-approval"><input name="cloud_approval" type="checkbox"> <span>For cloud endpoints: authorize this provider to process PhD application evidence on future agent runs without repeated prompts</span></label>'+
   '<div class="os-form-footer"><button type="submit" class="os-btn primary" name="mode" value="verify" '+(state.busy?"disabled":"")+'>Save, test & activate</button>'+
   '<button type="submit" class="os-btn quiet" name="mode" value="save" '+(state.busy?"disabled":"")+'>Save without testing</button></div>'+
   '<p class="os-form-caption">A saved key is never returned by the API. Successful inference—not possession of a key—establishes connection status. Only the explicitly approved cloud provider receives future application context.</p>'+
   '</form>';
 }
 function modelBrowser() {
  const id=state.selectedProvider;
  const data=state.models[id];
  if(!data)return '';
  return '<section class="os-panel os-model-results"><div class="os-panel-heading"><div><h2>Models discovered</h2><p>'+esc(data.models?.length||0)+' from '+esc(id)+' · '+esc(data.latency_ms)+' ms</p></div>'+
   btn("Close","close-models","","quiet")+'</div>'+
   '<div class="os-model-grid">'+(data.models||[]).slice(0,40).map(m=>
    '<div class="os-model-result"><span><strong>'+esc(m.name||m.id)+'</strong><small>'+esc(m.id)+'</small></span>'+
    btn("Use model","use-model",id,"quiet",'data-model="'+esc(m.id)+'"')+'</div>').join("")+'</div>'+
   footnote("Discovery proves catalog access, not model compatibility. Changing models invalidates the previous inference test.")+'</section>';
 }
 function connections() {
  return steps()+
   '<div class="os-connection-layout"><section class="os-panel os-registry-panel">'+
   '<div class="os-panel-heading"><div><h2>Inference connections</h2><p>One registry for local runtimes, cloud models and custom gateways</p></div>'+btn("Add endpoint","new-provider","","primary")+'</div>'+
   registry()+'</section><section class="os-panel os-editor">'+providerForm()+'</section></div>'+
   modelBrowser()+note();
 }
 function routePanel() {
  const p=active(),assignments=routing().agent_assignments||{};
  return '<div class="os-routing-grid">'+
   box("Workspace default","Automatically selected whenever an agent has no model override.",
     '<div class="os-active-provider"><div class="os-active-icon">AI</div><div><div class="os-kicker">CURRENT DEFAULT</div><strong>'+esc(p?.label||"No provider")+'</strong>'+
     '<small>'+esc(p?.model||"None")+'</small></div>'+(p?connectionChip(p):"")+'</div>'+
     '<p class="os-note">To change the default, verify and activate a provider in Connections. This selection is persisted by the Python backend and reused across future runs.</p>'+
     btn("Manage connections","tab","connections","primary"))+
   box("Per-agent model assignments","Optional overrides. Leaving an agent on automatic follows the workspace default.",
   '<form data-os-form="routing"><div class="os-assignment-list">'+agents().map(agent=>{
    const override=(prefs().agent_routes||{})[agent.id]||"auto";
    return '<div class="os-assignment"><label for="agent-route-'+esc(agent.id)+'"><strong>'+esc(agent.label)+'</strong><small>'+esc(agent.id)+'</small></label>'+
     '<select id="agent-route-'+esc(agent.id)+'" name="'+esc(agent.id)+'">'+opt([["auto","Automatic · default model"],...providers().map(p=>[p.id,p.label+" / "+p.model])],override)+'</select></div>';
   }).join("")+'</div><div class="os-form-footer"><button class="os-btn primary" type="submit">Save agent routing</button>'+
   btn("Clear overrides","clear-routes","","quiet")+'</div></form>')+'</div>'+
   '<div class="os-hint">Cloud routes require explicit approval. Assigning an unapproved or untested provider does not silently authorize transmission of application evidence.</div>'+note();
 }
 function agentPanel() {
  const list=agents(),agent=list.find(x=>x.id===state.selectedAgent)||list[0]||null,isNew=state.selectedAgent==="__new__";
  const item=isNew?{id:"",label:"",description:"",instructions:"",tools:[]}:agent||{id:"",label:"",description:"",instructions:"",tools:[]};
  const selectedTools=Array.isArray(item.tools)?item.tools:(state.data?.default_tools?.[item.id]||[]);
  const tools=state.data?.tool_names||[];
  const modelChoice=(prefs().agent_routes||{})[item.id]||"auto";
  return '<div class="os-builder-layout">'+
   '<section class="os-panel os-builder-list"><div class="os-panel-heading"><div><h2>Agent registry</h2><p>Instructions, capabilities and routing are editable</p></div>'+
   btn("New agent","new-agent","","primary")+'</div>'+
   '<div class="os-agent-list">'+list.map(a=>'<button type="button" data-os-action="edit-agent" data-id="'+esc(a.id)+'" class="os-agent-row '+(a.id===state.selectedAgent?"active":"")+'"><span class="os-avatar">'+esc((a.label||"A").slice(0,1))+'</span><span><strong>'+esc(a.label)+'</strong><small>'+esc(routeDescription(a.id))+'</small></span></button>').join("")+'</div></section>'+
   '<section class="os-panel os-editor"><div class="os-editor-top"><div><div class="os-kicker">AGENT DEFINITION</div><h2>'+(isNew?"New research agent":esc(item.label||"Select agent"))+'</h2></div>'+
   badge("Human-reviewed output")+'</div>'+
   '<form data-os-form="agent" class="os-form">'+
   '<div class="os-form-two">'+field("Agent ID","id",item.id,"text",'required pattern="[a-z][a-z0-9_-]{1,63}" '+(!isNew?'readonly':''))+
   field("Name","label",item.label,"text","required maxlength=100")+'</div>'+
   field("Responsibility","description",item.description||"","text",'maxlength=400 placeholder="What this agent is accountable for"')+
   '<label class="os-field"><span>System instructions</span><textarea name="instructions" rows="9" minlength="1" maxlength="5000" required>'+esc(item.instructions||"")+'</textarea></label>'+
   selector("Model route","provider_id",[["auto","Automatic · workspace default"],...providers().map(p=>[p.id,p.label+" · "+p.model])],modelChoice)+
   '<fieldset class="os-tool-field"><legend>Allowed deterministic tools</legend><div class="os-tool-grid">'+tools.map(name=>
    '<label class="os-tool"><input type="checkbox" name="tools" value="'+esc(name)+'" '+(selectedTools.includes(name)?"checked":"")+'><span>'+esc(pretty(name))+'</span></label>').join("")+'</div></fieldset>'+
   '<div class="os-form-footer"><button type="submit" class="os-btn primary" '+(state.busy?"disabled":"")+'>Save agent definition</button>'+
   (isNew?'':btn("Run this agent","run-selected-agent",item.id,"quiet"))+'</div>'+
   footnote("Agents can analyze evidence using allowlisted local tools. They cannot send mail, submit applications or change records without a separate, audited authorization workflow.")+
   '</form></section></div>'+note();
 }
 function schedulerPanel(){
  if(!state.schedulePreviewRequested){
   state.schedulePreviewRequested=true;
   request("/api/scheduler/preview").then(data=>{
    state.schedulePreview=data;onChange();
   }).catch(error=>{
    state.schedulePreview={error:error.message,workflows:[]};onChange();
   });
  }
  const plan=state.schedulePreview;
  if(!plan)return '<section class="os-panel"><div class="os-panel-heading"><div><h2>Automation execution plan</h2><p>Preparing an execution forecast without invoking models.</p></div></div></section>';
  const labels={due:"Ready to attempt",disabled:"Disabled",manual_only:"Manual",already_executed:"Completed this period",
   cloud_disclosure_not_approved:"Disclosure approval required",provider_not_approved:"Cloud provider not activated",
   cloud_budget_disabled:"Cloud budget disabled",cloud_daily_limit:"Daily cloud limit reached"};
  const rows=(plan.workflows||[]).map(w=>
   '<div class="os-schedule-row"><div><strong>'+esc(w.label)+'</strong><small>'+esc(pretty(w.schedule))+
   ' · '+esc(w.stages.map(x=>x.agent_id+" → "+x.model).join(" / "))+'</small></div>'+
   '<span class="os-badge '+(w.state==="due"?"good":w.state==="disabled"||w.state==="manual_only"?"":"warn")+'">'+esc(labels[w.state]||w.state)+'</span></div>').join("");
  const results=state.scheduleTick?.results||[];
  return '<section class="os-panel"><div class="os-panel-heading"><div><h2>Automation execution plan</h2><p>Read-only status, agent model assignments and reasons for skipped workflows</p></div>'+
   '<div class="os-inline-actions">'+btn("Refresh preview","refresh-preview","","quiet")+btn("Run due workflows","run-due","","primary")+'</div></div>'+
   '<div class="os-schedule-summary"><span>'+esc(plan.due||0)+' due</span><span>Timezone: '+esc(plan.timezone||"—")+'</span>'+
   '<span>Cloud usage: '+esc(plan.recorded_daily_cloud_calls??0)+' / '+esc(plan.daily_cloud_call_cap??0)+'</span></div>'+
   '<div class="os-schedule-list">'+(rows||'<p class="os-empty">No workflows configured.</p>')+'</div>'+
   (results.length?'<div class="os-schedule-results"><strong>Most recent manual scheduler check</strong>'+results.map(x=>
    '<p>'+esc(x.workflow_id)+' · '+esc(x.status)+(x.reason?' · '+esc(x.reason):'')+'</p>').join("")+'</div>':"")+
   '<p class="os-footnote" style="padding:0 20px 20px">'+esc(plan.notice||"")+'</p></section>';
 }
 function workflowPanel() {
  const list=workflows(),workflow=list.find(x=>x.id===state.selectedWorkflow)||list[0]||null,isNew=state.selectedWorkflow==="__new__";
  const item=isNew?{id:"",label:"",agent_id:agents()[0]?.id,schedule:"manual",enabled:false,steps:[],provider_id:"auto",cloud_consent:false,prompt:""}:workflow||{};
  const steps=item.steps||[item.agent_id];
  const agentOpts=[["","No additional step"],...agents().map(x=>[x.id,x.label])];
  const activeFlow=list.filter(x=>x.enabled).length;
  return '<div class="os-kpi-strip"><div><strong>'+list.length+'</strong><span>Registered workflows</span></div><div><strong>'+activeFlow+'</strong><span>Enabled rules</span></div><div><strong>'+esc(prefs().max_cloud_model_calls_per_day??0)+'</strong><span>Scheduled cloud-call daily cap</span></div></div>'+
   '<div class="os-builder-layout"><section class="os-panel os-builder-list"><div class="os-panel-heading"><div><h2>Workflow registry</h2><p>Manual and scheduled orchestration</p></div>'+btn("Create","new-workflow","","primary")+'</div>'+
   '<div class="os-agent-list">'+list.map(w=>'<button type="button" data-os-action="edit-workflow" data-id="'+esc(w.id)+'" class="os-agent-row '+(w.id===state.selectedWorkflow?"active":"")+'"><span class="os-workflow-mark">'+(w.enabled?"●":"○")+'</span><span><strong>'+esc(w.label)+'</strong><small>'+esc(pretty(w.schedule||"manual"))+' · '+(w.enabled?"Enabled":"Off")+'</small></span></button>').join("")+'</div></section>'+
   '<section class="os-panel os-editor"><div class="os-editor-top"><div><div class="os-kicker">AUTOMATION CONTRACT</div><h2>'+esc(isNew?"Create workflow":item.label||"Workflow")+'</h2></div>'+badge(item.enabled?"Enabled":"Disabled",item.enabled?"good":"")+'</div>'+
   '<form data-os-form="workflow" class="os-form">'+
   '<div class="os-form-two">'+field("Workflow ID","id",item.id||"","text",'required pattern="[a-z][a-z0-9_-]{1,63}" '+(isNew?"":"readonly"))+
   field("Name","label",item.label||"","text","required")+'</div>'+
   '<label class="os-field"><span>Objective and constraints</span><textarea name="prompt" rows="5" maxlength="3000" placeholder="Describe the bounded task and required output">'+esc(item.prompt||item.description||"")+'</textarea></label>'+
   '<div class="os-form-two">'+selector("Stage 1","step1",agents().map(x=>[x.id,x.label]),steps[0]||item.agent_id)+
   selector("Stage 2 (optional)","step2",agentOpts,steps[1]||"")+'</div>'+
   '<div class="os-form-two">'+selector("Stage 3 (optional)","step3",agentOpts,steps[2]||"")+
   selector("Cadence","schedule",[["manual","Manual"],["daily","Daily"],["twice_daily","Twice daily"],["weekly","Weekly"]],item.schedule||"manual")+'</div>'+
   selector("Provider policy","provider_id",[["auto","Automatic · follow each agent's route"],...providers().map(p=>[p.id,p.label])],item.provider_id||"auto")+
   '<label class="os-check"><input type="checkbox" name="enabled" '+(item.enabled?"checked":"")+'> <span>Enable scheduled evaluation for this workflow</span></label>'+
   '<label class="os-check"><input type="checkbox" name="cloud_consent" '+(item.cloud_consent?"checked":"")+'> <span>Approve this workflow to use configured, explicitly approved cloud models</span></label>'+
   '<div class="os-form-footer"><button class="os-btn primary" type="submit" '+(state.busy?"disabled":"")+'>Save workflow</button>'+
   (isNew?"":btn("Preview routes","preview-workflow",item.id,"quiet")+btn("Run now","run-workflow",item.id,"quiet"))+'</div>'+
   footnote("Automation creates reviewable proposals, not submissions. Recurring runs require an enabled private scheduler and the daily cloud-call budget.")+
   '</form></section></div>'+
   (state.workflowPreview?.workflow_id===item.id?
     box("Workflow route preview","Read-only preflight; no model was called.",
       '<div class="os-policy">'+state.workflowPreview.stages.map(stage=>
         '<div><strong>'+esc(stage.agent_id)+' · '+esc(stage.model)+'</strong><p>'+esc(stage.provider_label)+
         ' · '+esc(stage.route_source)+(stage.cloud?' · Cloud provider':' · Local provider')+'</p></div>').join("")+
       '<div><strong>'+esc(state.workflowPreview.model_calls)+' planned model calls</strong><p>'+
       (state.workflowPreview.manual_ready?'Routes resolved; actual model health and quotas require verification':'Manual execution requires fresh cloud-data consent')+
       '</p></div></div>'):"")+schedulerPanel()+note();
 }
 function preferencesPanel() {
  const p=prefs();
  return '<div class="os-pref-layout">'+
   box("Workspace behavior","Stored privately in SQLite; never exposed in the static Pages snapshot.",
    '<form data-os-form="preferences" class="os-form">'+
    selector("Default assistant","default_agent",agents().map(a=>[a.id,a.label]),p.default_agent||agents()[0]?.id)+
    field("Time zone","timezone",p.timezone||"Europe/Berlin","text",'required placeholder="Europe/Berlin"')+
    '<div class="os-form-two">'+field("Maximum scheduled workflows per tick","max_runs_per_tick",p.max_runs_per_tick??3,"number",'min="1" max="10" step="1" required')+
    field("Daily cloud-model call cap","max_cloud_model_calls_per_day",p.max_cloud_model_calls_per_day??0,"number",'min="0" max="100" step="1" required')+'</div>'+
    '<div class="os-form-footer"><button type="submit" class="os-btn primary">Save preferences</button></div>'+
    '</form>')+
   box("Security & deployment","Important boundaries for models that access application evidence.",
    '<div class="os-policy"><div><strong>Credentials</strong><p>Kept in the private local runtime. Local key storage uses restrictive file permissions but is not encrypted at rest.</p></div>'+
    '<div><strong>Cloud data disclosure</strong><p>Manual cloud inference requires consent on every run. Scheduled cloud routes require separately approved providers, workflow consent and daily quotas; editing a provider revokes approval.</p></div>'+
    '<div><strong>Model behavior</strong><p>Replies are reviewable proposals. No automatic faculty messages or application submissions.</p></div>'+
    '<div><strong>Scheduler</strong><p>Disabled until you enable workflows and run the external scheduler. Cloud calls remain capped separately.</p></div></div>'+
    btn("View run history","go","activity","quiet"))+
   box("Private state resilience","Inspect local SQLite health and create a consistent, owner-only backup without uploading applicant data.",
    '<div class="os-policy"><div><strong>SQLite state</strong><p>'+
    (state.diagnostics?esc("Integrity: "+state.diagnostics.database.integrity+
       " · WAL: "+state.diagnostics.database.journal_mode+
       " · Active workflow claims: "+state.diagnostics.scheduler.active_claims+
       " · Existing backups: "+state.diagnostics.backups.count):
       "Not checked during this session. Health inspection performs no external requests.")+'</p></div>'+
    (state.latestBackup?'<div><strong>Last saved backup</strong><p>'+esc(state.latestBackup.filename)+
       ' · SHA-256 '+esc(state.latestBackup.sha256.slice(0,16))+
       '… · Owner-only directory: '+esc(state.latestBackup.directory)+'</p></div>':'')+
    '<div><strong>Recovery boundary</strong><p>Backups include private SQLite state but exclude provider credentials. Restore only with the runtime stopped.</p></div></div>'+
    btn("Verify local database","state-diagnostics","","quiet")+
    btn("Create private backup","state-backup","","quiet"))+'</div>'+note();
 }
 function settings() {
  const current=active();
  return '<section class="os-page">'+heading("SYSTEM / MODEL ORCHESTRATION","Settings","Register models, verify provider access, assign agents and control what is allowed to run. Configuration persists across sessions.",
     '<div class="os-active-status"><span class="os-status-dot '+(current&&status(current)==="responded"?"is-live":"")+'"></span><span><small>DEFAULT INFERENCE</small><strong>'+esc(current?.label||"Not configured")+'</strong></span></div>')+
   tabs()+(state.tab==="connections"?connections():state.tab==="routing"?routePanel():state.tab==="agents"?agentPanel():state.tab==="workflows"?workflowPanel():preferencesPanel())+'</section>';
 }
 function copilot(records) {
  const agentId=state.selectedAgent||prefs().default_agent||agents()[0]?.id;
  const route=routeFor(agentId);
  const visibleRecords=(records||[]).filter(r=>r.record_type==="tracked").slice(0,300);
  const options=[["","Portfolio · all tracked opportunities"],...visibleRecords.map(r=>[r.id,short(r.name,85)])];
  const recent=(state.data.runs||[]).slice(0,6);
  const scoped=(records||[]).find(r=>r.id===state.selectedApplication);
  const context=scoped?'<div class="os-context-banner"><div><span class="os-kicker">APPLICATION IN CONTEXT</span><strong>'+esc(short(scoped.name,125))+'</strong><small>'+esc(scoped.id)+' · Evidence '+esc(state.data.as_of||"unknown")+'</small></div>'+btn("Clear context","clear-application","","quiet")+'</div>':'';
  return '<section class="os-page">'+heading("AI / RESEARCH COPILOT","Research Copilot","Evidence-backed analysis and application decisions, driven by the model and agent routes configured in Settings.",
    btn("Configure AI","go","settings","quiet"))+context+
   '<div class="os-copilot-layout"><section class="os-panel os-chat-panel"><div class="os-copilot-banner"><div class="os-avatar-large">A</div><div><div class="os-kicker">AUTOMATIC INFERENCE</div>'+
   '<h2>What should we investigate?</h2><p>One workspace. One model configuration. No provider selection per request.</p></div></div>'+
   '<form data-os-form="run" class="os-form os-copilot-form">'+
   selector("Agent", "agent_id", agents().map(a=>[a.id,a.label]),agentId)+
   selector("Evidence scope","application_id",options,state.selectedApplication)+
   '<label class="os-field"><span>Research question or task</span><textarea id="osPrompt" name="prompt" rows="7" placeholder="Review my current applications, unresolved eligibility conditions and highest-value next actions." maxlength="5000">'+esc(state.prompt)+'</textarea></label>'+
   '<div class="os-prompt-templates">'+btn("Prioritize next actions","prompt","priorities","chip")+
    btn("Audit evidence gaps","prompt","evidence","chip")+
    btn("Compare research fit","prompt","fit","chip")+
    btn("Prepare next steps","prompt","steps","chip")+'</div>'+
   '<div class="os-run-footer"><div class="os-route-description">'+
   '<span class="os-status-dot '+(route?.state==="responded"?"is-live":"")+'"></span><div><strong>'+esc(route?.provider_label||"No route")+'</strong><small>'+esc(route?.model||"Configure provider")+' · '+esc(route?.source==="agent_assignment"?"Agent route":"Workspace route")+'</small></div></div>'+
   '<button type="submit" class="os-btn primary" '+(state.busy||!route?.allowed?"disabled":"")+'>Run analysis</button>'+
   '<button type="button" class="os-btn quiet" data-os-action="queue-agent" '+(state.busy||!route?.allowed||!providerForAgent(agentId)?.local?"disabled":"")+'>Queue locally</button></div>'+
   (!route?.allowed?'<p class="os-warning">This agent is assigned to a cloud provider that has not been approved for automatic use. Activate it in Settings first.</p>':'')+
   '</form></section>'+
   '<aside class="os-copilot-side">'+box("Operating context","Evidence and actions remain traceable.",
    '<div class="os-context-grid"><div><span>Agent</span><strong>'+esc(agents().find(a=>a.id===agentId)?.label||"Unknown")+'</strong></div>'+
    '<div><span>Provider</span><strong>'+esc(route?.provider_label||"Unconfigured")+'</strong></div>'+
    '<div><span>State</span><strong>'+esc(route?stateText(route.state):"Offline")+'</strong></div>'+
    '<div><span>Source</span><strong>'+esc(state.data.as_of||"Unknown")+'</strong></div></div>')+
    box("Recent analyses","Stored locally; available for review.",
    '<div class="os-compact-runs">'+recent.map(r=>'<div><strong>'+esc(agents().find(a=>a.id===r.agent_id)?.label||r.agent_id)+'</strong><small>'+esc(stamp(r.created_at))+' · '+esc(r.provider_id)+'</small></div>').join("")+'</div>'+
    btn("Open run ledger","go","activity","quiet"))+'</aside></div>'+
   (state.lastAnswer?'<section class="os-panel os-answer"><div class="os-panel-heading"><div><h2>Generated analysis</h2><p>Unverified AI proposal · '+esc(state.lastAnswer.model||"")+' · '+esc(state.lastAnswer.provider_id||"")+'</p></div>'+
    badge("Review before acting")+'</div><pre class="os-answer-text">'+esc(state.lastAnswer.text||"")+'</pre></section>':'')+note()+'</section>';
 }
 function activity() {
  const data=state.data,stats=data.usage_summary||{},runs=data.runs||[];
  const ledger=runs.length?runs.map(r=>
    '<article class="os-ledger-row"><div><strong>'+esc(agents().find(a=>a.id===r.agent_id)?.label||r.agent_id)+'</strong><small>'+esc(stamp(r.created_at))+' · '+esc(r.provider_id)+' · '+esc(r.model||"Unknown model")+'</small></div>'+
    badge(r.status,r.status==="failed"?"warn":"good")+
    '<span class="os-meta">'+esc(r.latency_ms==null?"—":r.latency_ms+" ms")+'</span></article>').join(""):'<p class="os-empty">No AI executions recorded. Connect a model to begin.</p>';
  const usage=(stats.provider_usage||[]).map(p=>'<div class="os-ledger-row"><strong>'+esc(p.provider_id)+'</strong><span>'+esc(p.calls)+' calls</span><span>'+esc(p.input_tokens)+' in / '+esc(p.output_tokens)+' out</span><span>'+esc(p.average_latency_ms??"—")+' ms avg.</span></div>').join("");
  return '<section class="os-page">'+heading("AI / OBSERVABILITY","Run history","A factual ledger of execution, model selection, usage and failed operations.",btn("Refresh","reconnect","","quiet"))+
   '<div class="os-kpi-strip"><div><strong>'+esc(stats.sampled_runs??0)+'</strong><span>Recorded calls</span></div>'+
   '<div><strong>'+esc(stats.total_input_tokens??0)+'</strong><span>Reported input tokens</span></div>'+
   '<div><strong>'+esc(stats.total_output_tokens??0)+'</strong><span>Reported output tokens</span></div>'+
   '<div><strong>'+esc(stats.total_failed??0)+'</strong><span>Failures</span></div></div>'+
   box("Agent executions","Costs are not inferred without verified provider pricing.",'<div class="os-ledger">'+ledger+'</div>')+
   box("Per-provider usage","Only measured calls and reported tokens are included.",'<div class="os-ledger">'+usage+'</div>')+
   box("Private reliability signals","Observed local runtime calls only; no hosted SLA or applicant text in traces.",
     '<div class="os-kpi-strip">'+
       '<div><strong>'+esc(state.observability?.window?.completed_calls??"—")+'</strong><span>Calls in window</span></div>'+
       '<div><strong>'+esc(state.observability?.window?.error_rate==null?"Unmeasured":(100*state.observability.window.error_rate).toFixed(1)+"%")+'</strong><span>Observed error rate</span></div>'+
       '<div><strong>'+esc(state.observability?.window?.p95_latency_ms??"—")+'</strong><span>p95 latency (ms)</span></div>'+
       '<div><strong>'+esc(pretty(state.observability?.objectives?.status||"not_available"))+'</strong><span>Local objective status</span></div></div>'+
     '<div class="os-ledger">'+(state.observability?.recent_traces||[]).slice(0,8).map(item=>
       '<article class="os-ledger-row"><div><strong>'+esc(item.agent_id)+'</strong><small>'+
       esc(short(item.run_id,12))+' · '+esc(stamp(item.created_at))+' · '+esc(item.provider_id)+
       '</small></div>'+badge(item.status,item.status==="failed"?"warn":"good")+
       '<span class="os-meta">'+esc(item.error_type||((item.latency_ms??"—")+" ms"))+'</span></article>').join("")+
     '</div><p class="os-footnote">Objective requires at least 20 recent calls and measured latencies. A citation or healthy model is not evidence that an admission fact is true.</p>','os-observability')+
   box("Private local background jobs","Durable SQLite queue. A separate worker process must be running; cloud jobs are not permitted.",
     '<div class="os-actions">'+btn("Copy worker command","copy-worker-command","","quiet")+'</div>'+
     '<div class="os-ledger">'+(state.jobs.length?state.jobs.map(job=>
       '<article class="os-ledger-row"><div><strong>'+esc(job.agent_id)+'</strong><small>'+
       esc(job.id.slice(0,12))+' · '+esc(job.attempts)+'/'+esc(job.max_attempts)+
       ' attempts · '+esc(stamp(job.updated_at))+'</small></div>'+
       badge(job.status,job.status==="failed"?"warn":job.status==="succeeded"?"good":"")+
       ((!["succeeded","failed","canceled"].includes(job.status)&&!job.cancel_requested)?
         btn("Request cancel","cancel-job",job.id,"quiet"):"")+'</article>').join(""):
       '<p class="os-empty">No local jobs queued. Use Queue locally from Copilot.</p>')+'</div>')+'</section>';
 }
 const operations=createOperations({request,onChange,onReload,getRecords:getSourceRecords||getRecords,notify});
 const browserModel=createBrowserModel({notify,onChange,navigate,getSourceRecords:getSourceRecords||getRecords});
 function view(name,{records=[]}={}) {
  if(!isLive())return ["ai","settings"].includes(name)?browserModel.render(name):offline(name);
  if(name==="ai")return copilot(records);
  if(name==="operations")return operations.view();
  if(name==="settings")return settings();
  if(name==="agents")return '<section class="os-page">'+heading("AI / AGENT DEFINITIONS","Agent builder","Configure each research agent's instructions, deterministic tools and automatic model assignment.",btn("Model settings","go","settings","quiet"))+agentPanel()+'</section>';
  if(name==="automations")return '<section class="os-page">'+heading("AI / WORKFLOW ENGINE","Automations","Compose multi-agent workflows, inspect scheduling rules and control approvals.",btn("Runtime settings","go","settings","quiet"))+workflowPanel()+'</section>';
  if(name==="activity")return activity();
  if(name==="source-observations")return renderSourceObservations({records:state.sourceObservations,loading:state.sourceObservationsLoading,error:state.sourceObservationsError,filter:state.sourceObservationFilter});
  return '';
 }
 function selectConnection(id) {state.selectedProvider=id;state.models={};onChange();}
 function selectAgent(id) {state.selectedAgent=id;onChange();}
 function selectWorkflow(id) {state.selectedWorkflow=id;state.workflowPreview=null;onChange();}
 async function handleAction(element) {
  const action=element.dataset.osAction,id=element.dataset.id||"";
  if(action==="go"){navigate(id);return;}
  if(action==="tab"){state.tab=id;onChange();return;}
  if(action==="reconnect"){await connect();return;}
  if(action==="refresh-observations"){
   if(!isLive()||state.sourceObservationsLoading)return;
   state.sourceObservationsLoading=true;state.sourceObservationsError="";onChange();
   try{
    const response=await request("/api/source-observations");
    if(!Array.isArray(response.observations))throw new Error("Invalid source observation response");
    state.sourceObservations=response.observations;
   }catch(error){state.sourceObservationsError=String(error.message||error).slice(0,200);}
   finally{state.sourceObservationsLoading=false;onChange();}
   return;
  }
  if(action==="copy-observer-command"){
   if(!isLive())return;
   try{await navigator.clipboard.writeText("python -m phd_agents observe-sources --limit 8");notify("Source observation command copied.");}
   catch{notify("Copy unavailable. Select the visible command manually.");}
   return;
  }
  if(action.startsWith("bm-")){await browserModel.action(action.slice(3));return;}
  if(action==="state-diagnostics"){
   if(!isLive())return;
   await change(async()=>{
    state.diagnostics=await request("/api/diagnostics");
    state.message="SQLite integrity: "+state.diagnostics.database.integrity+
      ". Active workflow claims: "+state.diagnostics.scheduler.active_claims+".";
   });return;
  }
  if(action==="state-backup"){
   if(!isLive()||!window.confirm("Create a local SQLite backup in the private state directory? No data will be uploaded."))return;
   await change(async()=>{
    const output=await request("/api/maintenance/backup",{retain:7});
    state.latestBackup=output.backup;
    state.diagnostics=await request("/api/diagnostics");
    state.message="Backup verified: "+state.latestBackup.filename+". Stored locally; provider credentials excluded.";
   });return;
  }
  if(action==="copy-command"){await navigator.clipboard?.writeText("python -m phd_agents serve --port 8765");notify("Start command copied");return;}
  if(action==="copy-worker-command"){await navigator.clipboard?.writeText("python -m phd_agents worker-loop --interval-seconds 3");notify("Local worker command copied");return;}
  if(!isLive())return;
  if(action==="queue-agent"){
   const form=document.querySelector('form[data-os-form="run"]');
   if(!form)return;
   const agentId=form.elements.agent_id.value;
   const provider=providerForAgent(agentId);
   if(!provider?.local){notify("Queued jobs are local-only. Select a verified local model.");return;}
   const input=String(form.elements.prompt.value||"").trim();
   if(!input||input.length>5000){notify("Enter a research question before queueing.");return;}
   await change(async()=>{
    const result=await request("/api/jobs/enqueue",{agent_id:agentId,provider_id:provider.id,
     input_text:input,application_id:form.elements.application_id.value||null});
    state.message="Queued job "+result.job.id.slice(0,12)+". Start a private worker process to execute independently of this tab.";
    navigate("activity");
   });return;
  }
  if(action==="cancel-job"){
   await change(async()=>{
    const result=await request("/api/jobs/"+encodeURIComponent(id)+"/cancel",{});
    state.message=result.job.status==="running"?
     "Cancellation requested. An in-flight model call may still complete.":
     "Queued job cancelled.";
   });return;
  }
  if(action==="new-provider"){selectConnection("__new__");state.tab="connections";return;}
  if(action==="edit-provider"){selectConnection(id);state.tab="connections";return;}
  if(action==="toggle-providers"){state.showAllProviders=!state.showAllProviders;onChange();return;}
  if(action==="close-models"){state.models={};onChange();return;}
  if(action==="new-agent"){selectAgent("__new__");return;}
  if(action==="edit-agent"){selectAgent(id);return;}
  if(action==="new-workflow"){selectWorkflow("__new__");return;}
  if(action==="edit-workflow"){selectWorkflow(id);return;}
  if(action==="run-selected-agent"){state.selectedAgent=id;navigate("ai");return;}
  if(action==="clear-application"){state.selectedApplication="";state.prompt="";state.lastAnswer=null;onChange();return;}
  if(action==="prompt"){
   const suggestions={priorities:"Identify the three highest-value actions I can complete today, with supporting evidence and unknowns.",evidence:"Audit application evidence conflicts, missing primary sources and incomplete documentation.",fit:"Compare my documented work against current research requirements without inventing supervisor availability.",steps:"Produce a prioritized dependency-aware application action plan with explicit proof obligations."};
   state.prompt=suggestions[id]||"";onChange();const el=document.getElementById("osPrompt");if(el)el.focus();return;
  }
  if(action==="clear-routes"){
   await change(async()=>{await request("/api/settings",{agent_routes:{}});state.message="All agents now follow the default model."});return;
  }
  if(action==="models"){
   const provider=providers().find(p=>p.id===id);if(!provider)return;
   if(!provider.local&&!window.confirm("Query "+provider.label+" for its model catalog? This contacts the provider but sends no applicant evidence."))return;
   await change(async()=>{
    const result=await request("/api/providers/models",{provider_id:id,cloud_consent:!provider.local});
    state.models={[id]:result};state.selectedProvider=id;state.tab="connections";
    state.message="Catalog retrieved. Select a model, then verify it before activation.";
   });return;
  }
  if(action==="use-model"){
   const provider=providers().find(p=>p.id===id),model=element.dataset.model;
   if(!provider||!model)return;
   await change(async()=>{
    await request("/api/catalog/provider",{...provider,model});
    state.selectedProvider=id;state.models={};
    state.message="Model saved. Previous inference verification was cleared; retest before activating.";
   });return;
  }
  if(action==="test"){
   const provider=providers().find(p=>p.id===id);if(!provider)return;
   if(!provider.local&&!window.confirm("Send a short inference test to "+provider.label+"? This may incur API charges but contains no applicant data."))return;
   await change(async()=>{
    const result=await request("/api/providers/probe",{provider_id:id,cloud_consent:!provider.local});
    state.selectedProvider=id;state.message="Inference verified with "+result.model+". Activate to make this model the automatic default.";
   });return;
  }
  if(action==="activate"){
   const provider=providers().find(p=>p.id===id);if(!provider)return;
   if(!provider.local&&!window.confirm("Approve "+provider.label+" as a cloud route for scheduled workflows? Manual cloud runs will still ask for consent every time."))return;
   await change(async()=>{
    await request("/api/providers/activate",{provider_id:id,allow_cloud_data:!provider.local});
    state.selectedProvider=id;state.message=provider.label+" is now the automatic workspace model.";
   });return;
  }
  if(action==="refresh-preview"){
   state.schedulePreviewRequested=false;state.schedulePreview=null;onChange();return;
  }
  if(action==="run-due"){
   if(!window.confirm("Run all due and explicitly enabled workflows now? Approved cloud routes may incur token charges and may receive application evidence. No submissions or messages will be sent."))return;
   await change(async()=>{
    state.scheduleTick=await request("/api/scheduler/tick",{});
    state.message="Scheduler check completed. Review attempted, skipped and failed workflows below.";
   });return;
  }
  if(action==="preview-workflow"){
   await change(async()=>{
    state.workflowPreview=await request("/api/workflows/preview",{workflow_id:id});
    state.message="Read-only route preflight completed; no model inference performed.";
   });return;
  }
  if(action==="run-workflow"){
   const workflow=workflows().find(item=>item.id===id);
   if(!workflow)return;
   const consent=cloudConsentForAgents(workflow.steps?.length?workflow.steps:[workflow.agent_id],workflow.provider_id||"auto");
   if(!consent.allowed)return;
   await change(async()=>{
    const result=await request("/api/workflows/run",{workflow_id:id,cloud_consent:consent.cloud_consent});
    state.lastAnswer=result;state.selectedAgent=result.agent_id;
    state.message="Workflow completed as a proposal. No external action was performed.";
    navigate("ai");
   });return;
  }
 }
 async function handleForm(event) {
  const form=event.target,kind=form.dataset.osForm;
  if(!kind)return;
  event.preventDefault();
  if(kind.startsWith("bm-")){try{await browserModel.submit(event);}catch(error){notify(short(error.message,220));}return;}
  const values=Object.fromEntries(new FormData(form));
  if(kind==="provider"){
   const id=cleanId(values.id||values.label);
   const isLocal=form.elements.local.checked;
   const variable=String(values.api_key_env||"").trim()||(isLocal?"":id.toUpperCase()+"_API_KEY");
   const provider={id,label:values.label,kind:values.kind,base_url:values.base_url,
                   model:values.model,api_key_env:variable,local:isLocal,
                   max_output_tokens:Number(values.max_output_tokens||1200),
                   timeout_seconds:Number(values.timeout_seconds||55),
                   token_parameter:values.token_parameter};
   if(values.temperature!=="")provider.temperature=Number(values.temperature);
   if(provider.kind==="azure_deployment")provider.api_version=values.api_version||"2024-10-21";
   const credential=form.elements.credential.value;
   const mode=event.submitter?.value||"verify";
   const auto=form.elements.auto_activate.checked;
   const cloudApproval=form.elements.cloud_approval.checked;
   if(mode!=="save"&&!isLocal&&!window.confirm("Verify "+provider.label+" using an external inference request? This may incur API charges."))return;
   await change(async()=>{
    const payload={provider};
    if(credential)payload.credential=credential;
    await request("/api/providers/setup",payload);
    state.selectedProvider=id;
    if(mode==="save"){state.message="Endpoint saved. Test inference to verify the model.";return;}
    const tested=await request("/api/providers/probe",{provider_id:id,cloud_consent:!isLocal});
    if(auto){
     if(!isLocal&&!cloudApproval){state.message="Inference verified with "+tested.model+". To activate cloud routing, explicitly approve application-data disclosure.";return;}
     await request("/api/providers/activate",{provider_id:id,allow_cloud_data:cloudApproval});
     state.message="Connected and activated "+provider.label+". Future agents use this model automatically.";
    }else state.message="Inference verified. Activate this provider whenever you want to use it automatically.";
   });return;
  }
  if(kind==="agent"){
   const agent={id:cleanId(values.id||values.label),label:values.label,description:values.description,
                instructions:values.instructions,tools:new FormData(form).getAll("tools")};
   const route=values.provider_id;
   await change(async()=>{
    await request("/api/catalog/agent",agent);
    const routes={...(prefs().agent_routes||{})};
    if(route&&route!=="auto")routes[agent.id]=route;
    else delete routes[agent.id];
    await request("/api/settings",{agent_routes:routes});
    state.selectedAgent=agent.id;
    state.message="Agent definition saved. Future executions use its assigned route automatically.";
   });return;
  }
  if(kind==="routing"){
   const routes={};
   for(const [agent,provider] of new FormData(form))if(provider&&provider!=="auto")routes[agent]=provider;
   await change(async()=>{await request("/api/settings",{agent_routes:routes});state.message="Agent model routing saved.";});return;
  }
  if(kind==="workflow"){
   const steps=[values.step1,values.step2,values.step3].filter(Boolean);
   const workflow={id:cleanId(values.id||values.label),label:values.label,description:String(values.prompt||"").slice(0,200),
        prompt:values.prompt,agent_id:steps[0],steps,
        provider_id:values.provider_id||"auto",schedule:values.schedule,
        enabled:form.elements.enabled.checked,cloud_consent:form.elements.cloud_consent.checked};
   await change(async()=>{await request("/api/catalog/workflow",workflow);state.selectedWorkflow=workflow.id;state.message="Workflow saved. Scheduled execution still requires the private scheduler.";});return;
  }
  if(kind==="preferences"){
   await change(async()=>{
    await request("/api/settings",{default_agent:values.default_agent,timezone:values.timezone,
        max_runs_per_tick:Number(values.max_runs_per_tick),
        max_cloud_model_calls_per_day:Number(values.max_cloud_model_calls_per_day)});
    state.message="Workspace preferences saved.";
   });return;
  }
  if(kind==="run"){
   const consent=cloudConsentForAgents([values.agent_id]);
   if(!consent.allowed)return;
   state.selectedAgent=values.agent_id;state.selectedApplication=values.application_id;state.prompt=values.prompt;
   await change(async()=>{
    const result=await request("/api/agents/run",{agent_id:values.agent_id,
       ...(values.application_id?{application_id:values.application_id}:{}),input_text:values.prompt,
       cloud_consent:consent.cloud_consent});
    state.lastAnswer=result;state.message="Inference completed. Review the proposal against official evidence.";
   });return;
  }
 }
 function setupEvents() {
  document.addEventListener("click",event=>{
   const element=event.target.closest("[data-os-action]");
   if(!element)return;
   event.preventDefault();
   handleAction(element).catch(error=>notify(short(error.message,220)));
  });
  document.addEventListener("submit",event=>{
   if(!event.target.matches("form[data-os-form]"))return;
   handleForm(event).catch(error=>notify(short(error.message,220)));
  });
  document.addEventListener("change",event=>{
   if(event.target.matches("[data-os-observation-filter]")){
    state.sourceObservationFilter=event.target.value;
    onChange();return;
   }
   if(event.target.matches('select[name="agent_id"]')&&event.target.closest('form[data-os-form="run"]')){
    const form=event.target.form;
    state.prompt=form.elements.prompt.value;
    state.selectedAgent=event.target.value;
    state.selectedApplication=form.elements.application_id.value;
    onChange();
   }
  });
  document.addEventListener("input",event=>{
   if(event.target.id==="osPrompt")state.prompt=event.target.value;
   browserModel.input(event);
  });
 }
 setupEvents();
 return {connect,view,isLive,browserModel,activeLabel:()=>active()?.label||"Configure a model",
  activeModel:()=>active()?.model||"",isVerified:()=>!!active()&&status(active())==="responded",
  settings:()=>prefs(),setContext:view=>{state.sourceView=view},
  selectApplication:id=>{state.selectedApplication=id;state.prompt="Audit this application's official-source evidence, eligibility, exact deadline, documents, blockers and next actions. Separate verified facts from unknowns.";state.lastAnswer=null;},
  selectTab:tab=>{state.tab=tab;onChange()},openApplication:id=>operations.selectApplication(id)};
}
