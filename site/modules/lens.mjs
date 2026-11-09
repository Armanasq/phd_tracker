const byId=id=>document.getElementById(id);
const escapeHTML=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const short=(value,n=160)=>String(value??"").slice(0,n);
const safeLink=value=>{try{const u=new URL(value);return u.protocol==="https:"?u.href:null}catch{return null}};
const icon=(name)=>({lens:'<circle cx="12" cy="12" r="4"/><ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(35 12 12)"/>',close:'<path d="m5 5 14 14M19 5 5 19"/>',expand:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 4v7H4m16 2h-7v7"/>',shrink:'<path d="M4 4h8v8H4zm8 8h8v8h-8z"/>',plus:'<path d="M12 4v16M4 12h16"/>',send:'<path d="m5 12 14-7-5 14-2.5-6.5L5 12zm6.5.5L19 5"/>',arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',history:'<path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5"/><path d="M12 7v5l3 2"/>',copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',settings:'<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>'})[name]||"";
const svg=name=>'<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6">'+icon(name)+'</svg>';
const card=(number,label)=>'<div><strong>'+escapeHTML(number)+'</strong><small>'+escapeHTML(label)+'</small></div>';
const prompts=[
 {title:"What should I work on today?",code:"01",value:"Prioritize today's outstanding application actions using recorded deadlines, owner state, and evidence gaps. Clearly distinguish confirmed facts from unverified records."},
 {title:"Check upcoming deadlines",code:"02",value:"Audit upcoming PhD application deadlines and evidence obligations. Identify missing official verification and do not infer portal cutoff times."},
 {title:"Compare research fit",code:"03",value:"Assess research alignment among tracked opportunities using recorded research focus, faculty, funding, and eligibility evidence. Separate unknown fit from supported fit."},
 {title:"Plan next steps",code:"04",value:"Develop a realistic prioritized sequence of next application actions, faculty follow-ups, referee checks, and document preparation based only on available records."}
];
export function mountAtlasLens({getRecords,getView,getSelectedApplication,openSettings,onFocusApplication,onRunComplete}){
 if(byId("atlasLens"))return;
 const state={open:false,expanded:false,busy:false,connected:false,verified:false,provider:"",model:"",agent:"",agents:[],applicationId:"",turns:[],draft:"",trace:null,abort:null,error:"",sourceAsOf:"",providerStates:{},providers:[],routes:{},routeSource:"",routeState:"",routeReason:"",conversationId:null,conversations:[],historyOpen:false,hydrated:false};
 const root=document.createElement("div");root.id="atlasLens";document.body.appendChild(root);
 const focusable='button:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href]';
 let focusReturn=null;let requestSequence=0;
 const records=()=>{try{const data=getRecords?.();return Array.isArray(data)?data:[]}catch{return []}};
 const isLocal=()=>["localhost","127.0.0.1"].includes(location.hostname)&&location.protocol==="http:";
 const selected=()=>records().find(x=>x.id===state.applicationId);
 const threadStorageKey="phd-atlas-private-thread-v1";
 const routeNames={request_override:"Request override",agent_assignment:"Agent assignment",workspace_default:"Workspace default"};
 function syncRoute(){
   const route=state.routes[state.agent];
   const provider=state.providers.find(p=>p.id===route?.provider_id);
   state.provider=route?.provider_label||provider?.label||"Not configured";
   state.model=route?.model||provider?.model||"";
   state.routeSource=routeNames[route?.source]||"Not assigned";
   state.routeState=route?.state||"needs_setup";
   state.routeReason=state.providerStates[route?.provider_id]?.reason||"";
   state.verified=Boolean(route?.allowed&&route?.state==="responded");
 }
 function clearThread(){
   state.conversationId=null;state.turns=[];state.historyOpen=false;state.error="";
   try{localStorage.removeItem(threadStorageKey)}catch{}
 }
 async function fetchThreads(){
   if(!state.connected)return;
   try{
     const r=await fetch("./api/conversations",{cache:"no-store"});
     if(r.ok){const data=await r.json();state.conversations=Array.isArray(data.conversations)?data.conversations:[]}
   }catch{}
 }
 async function openThread(identity,{silent=false}={}){
   if(!state.connected||!/^[a-f0-9]{32}$/.test(String(identity)))return;
   const response=await fetch("./api/conversations/"+encodeURIComponent(identity),{cache:"no-store"});
   if(!response.ok)throw Error("Conversation not available");
   const data=await response.json();
   if(!state.agents.some(a=>a.id===data.agent_id))throw Error("Conversation agent is no longer registered");
   state.agent=data.agent_id;
   state.applicationId=typeof data.application_id==="string"?data.application_id:"";
   state.conversationId=data.id;
   state.turns=(data.messages||[]).map(m=>({role:m.role,text:m.content,model:m.model,provider:m.provider_id,agent:data.agent_id,
     id:m.run_id,latency:m.latency_ms,sourceAsOf:m.source_as_of,evidence_refs:m.evidence_refs||[],retrievalMethod:m.retrieval_method,tools:m.tools||[],openTrace:false}));
   state.historyOpen=false;state.error="";syncRoute();
   try{localStorage.setItem(threadStorageKey,data.id)}catch{}
   if(!silent){render();const h=byId("lensHistory");if(h)h.scrollTop=h.scrollHeight}
 }
 async function deleteThread(identity){
   if(!state.connected||!window.confirm("Delete this private conversation and its messages?"))return;
   const r=await fetch("./api/conversations/"+encodeURIComponent(identity)+"/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
   if(!r.ok)throw Error("Could not delete conversation");
   if(identity===state.conversationId)clearThread();
   await fetchThreads();render();
 }
 function historyMenu(){
   if(!state.historyOpen)return "";
   return '<div class="lens-thread-menu" role="group" aria-label="Recent private conversations"><div class="lens-thread-heading">Recent conversations</div>'+
     (state.conversations.length?state.conversations.slice(0,15).map(item=>
       '<div class="lens-thread-row"><button type="button" class="lens-thread-open" data-lens="open-thread" data-id="'+escapeHTML(item.id)+'"><strong>'+escapeHTML(short(item.title,85))+'</strong><small>'+escapeHTML(item.updated_at||"")+'</small></button>'+
       '<button type="button" class="lens-thread-remove" data-lens="delete-thread" data-id="'+escapeHTML(item.id)+'" aria-label="Delete conversation '+escapeHTML(short(item.title,45))+'">Delete</button></div>'
     ).join(""):'<p class="lens-thread-empty">No saved conversations yet.</p>')+'</div>';
 }
 function contextOptions(){
 const rows=records().filter(x=>x.record_type==="tracked"||x.record_type==="candidate").slice(0,400);
 return '<option value="">Portfolio · all applications</option>'+(state.applicationId&&!rows.some(x=>x.id===state.applicationId)?'<option value="'+escapeHTML(state.applicationId)+'" selected>Unavailable in snapshot · '+escapeHTML(short(state.applicationId,35))+'</option>':"")+rows.map(x=>'<option value="'+escapeHTML(x.id)+'"'+(state.applicationId===x.id?" selected":"")+'>'+escapeHTML(short(x.name,69))+'</option>').join("");
 }
 function agentOptions(){return state.agents.map(a=>'<option value="'+escapeHTML(a.id)+'"'+(state.agent===a.id?" selected":"")+'>'+escapeHTML(short(a.label,45))+'</option>').join("")}
 function counts(){
 const data=records().filter(x=>x.record_type==="tracked");
 const unknown=data.filter(x=>!["source_verified","owner_verified"].includes(x.verification)).length;
 const upcoming=data.filter(x=>x.deadline&&x.deadline>=new Date().toISOString().slice(0,10)&&!["submitted","archived","withdrawn","rejected"].includes(x.status)).length;
 return {tracked:data.length,unknown,upcoming};
 }
 function hero(){
 const c=counts();const chosen=selected();
 return '<section class="lens-hero"><h2>'+(chosen?'Ask about this application':'How can I help?')+'</h2><p>'+(chosen?'Review its deadlines, requirements, and unresolved evidence.':'Ask about your applications, deadlines, research fit, or next actions.')+'</p><div class="lens-facts">'+card(c.tracked,"Tracked records")+card(c.upcoming,"Future dated records")+card(c.unknown,"Not verified")+'</div><div class="lens-section-label">Suggested questions</div><div class="lens-prompts">'+prompts.map(p=>'<button type="button" class="lens-prompt" data-lens="prompt" data-value="'+escapeHTML(p.value)+'"><strong>'+escapeHTML(p.title)+'</strong>'+svg("arrow")+'</button>').join("")+'</div></section>';
 }
 function offline(){
   if(!state.connected)return '<div class="lens-offline"><h3>Private model unavailable</h3><p>GitHub Pages cannot run private inference. Open Atlas through the locally hosted runtime.</p><code>python -m phd_agents serve --port 8765</code><button type="button" data-lens="refresh">Retry connection</button></div>';
   return '<div class="lens-offline"><h3>Model needs verification</h3><p>'+escapeHTML(state.routeReason||"Verify the selected agent's model in Settings before sending messages.")+'</p><button type="button" data-lens="settings">Open model settings</button> <button type="button" data-lens="refresh">Retry</button></div>';
 }
 function evidenceBlock(turn){
   const refs=Array.isArray(turn.evidence_refs)?turn.evidence_refs.slice(0,10):[];
   if(!refs.length)return "";
   const method=turn.retrievalMethod==="weighted_lexical"?"Query-matched records":turn.retrievalMethod==="selected_application"?"Selected application":"Deadline-ordered records";
   return '<details class="lens-evidence"><summary>'+escapeHTML(method)+' · '+refs.length+'</summary><div class="lens-evidence-items">'+refs.map(item=>{
      const url=safeLink(item.source_url);
      return '<div class="lens-evidence-item"><div><button type="button" data-lens="focus-record" data-id="'+escapeHTML(item.application_id)+'">'+escapeHTML(short(item.name||item.application_id,110))+'</button><small>'+escapeHTML(item.verification||"unknown")+' · '+escapeHTML((item.matched_fields||[]).filter(x=>x!=="selected_application").join(", ")||"Context")+'</small></div>'+
        (url?'<a href="'+escapeHTML(url)+'" target="_blank" rel="noopener noreferrer" aria-label="Open original source for '+escapeHTML(short(item.name,80))+'">Source ↗</a>':"")+'</div>';
   }).join("")+'</div><p>Retrieved records are context, not independently verified citations.</p></details>';
 }
 function feed(){
 if(!state.turns.length)return hero()+(state.verified?"":offline());
 return '<div class="lens-feed">'+state.turns.map((t,i)=>{
 if(t.role==="user")return '<div class="lens-turn user" data-index="'+i+'"><div class="lens-body">'+escapeHTML(t.text)+'</div></div>';
 return '<article class="lens-turn assistant" data-index="'+i+'"><div class="lens-speaker"><span>Atlas</span> / '+escapeHTML(t.model||"Assistant")+'</div><div class="lens-body">'+escapeHTML(t.text)+'</div>'+
 '<div class="lens-turn-actions"><button class="lens-mini" data-lens="copy" data-index="'+i+'">Copy response</button><button class="lens-mini" data-lens="trace" data-index="'+i+'" aria-expanded="'+(!!t.openTrace)+'">Run details</button></div>'+
 (t.openTrace?'<div class="lens-trace"><div><strong>Provider</strong> '+escapeHTML(t.provider||"Unknown")+'</div><div><strong>Model</strong> '+escapeHTML(t.model||"Unknown")+'</div><div><strong>Agent</strong> '+escapeHTML(t.agent||"Unknown")+'</div><div><strong>Run ID</strong> <code>'+escapeHTML(t.id||"Not recorded")+'</code></div><div><strong>Latency</strong> '+escapeHTML(t.latency==null?"Not recorded":t.latency+" ms")+'</div><div><strong>Evidence observed</strong> '+escapeHTML(t.sourceAsOf||"Unknown")+'</div><div><strong>Tools</strong> '+escapeHTML((t.tools||[]).join(", ")||"No tools reported")+'</div><div><strong>Status</strong> Proposal only; no external application action performed</div></div>':"")+
 '<div class="lens-source">Assistant response · Check original sources before acting.</div>'+evidenceBlock(t)+'</article>';
 }).join("")+(state.busy?'<div class="lens-wait" role="status"><span class="lens-wait-orbit"></span>Analyzing application evidence…</div>':"")+'</div>'+(state.error?'<div role="alert" class="lens-alert">'+escapeHTML(state.error)+'</div>':"");
 }
 function sidecar(){
 const record=selected();
 const c=counts();
 const route=state.routes[state.agent]||{};
 const endpoint=state.providers.find(p=>p.id===route.provider_id)||{};
 const diagnostics=state.providerStates[route.provider_id]||{};
 return '<aside class="lens-sidecar"><div class="lens-aside-kicker">Current context</div><div class="lens-aside-card"><h3>Evidence workspace</h3><div class="lens-aside-row"><span>Scope</span><strong>'+escapeHTML(record?short(record.name,32):"Full portfolio")+'</strong></div><div class="lens-aside-row"><span>Tracked</span><strong>'+c.tracked+'</strong></div><div class="lens-aside-row"><span>Verification</span><strong>'+escapeHTML(record?.verification||"Mixed")+'</strong></div><div class="lens-aside-row"><span>Observed</span><strong>'+escapeHTML(state.sourceAsOf||"Not loaded")+'</strong></div>'+(record&&safeLink(record.source_url)?'<a class="lens-evidence-link" href="'+escapeHTML(safeLink(record.source_url))+'" target="_blank" rel="noopener noreferrer">Open original source</a>':"")+'</div><div class="lens-aside-card"><h3>Permissions</h3><p>The assistant produces evidence-based proposals. It cannot silently change application status, send faculty emails, or submit applications. Private credentials never enter the public GitHub Pages frontend.</p></div><div class="lens-aside-card"><h3>Model route</h3><div class="lens-aside-row"><span>Endpoint</span><strong>'+escapeHTML(state.provider||"Not connected")+'</strong></div><div class="lens-aside-row"><span>Route</span><strong>'+escapeHTML(state.routeSource||"Not assigned")+'</strong></div><div class="lens-aside-row"><span>Status</span><strong>'+escapeHTML(state.routeState||"unknown")+'</strong></div><div class="lens-aside-row"><span>Model</span><strong>'+escapeHTML(state.model||"Not selected")+'</strong></div><div class="lens-aside-row"><span>API type</span><strong>'+escapeHTML(endpoint.kind||"unknown")+'</strong></div><div class="lens-aside-row"><span>Endpoint</span><strong>'+escapeHTML(short(endpoint.base_url||"Unknown",140))+'</strong></div><div class="lens-aside-row"><span>Credential</span><strong>'+escapeHTML(diagnostics.credential_configured===true?"Configured":diagnostics.credential_configured===false?"Not configured":"Not required")+'</strong></div><div class="lens-aside-row"><span>Last check</span><strong>'+escapeHTML(diagnostics.last_checked||"Never")+'</strong></div><div class="lens-aside-row"><span>Verified</span><strong>'+(state.verified?"Yes":"No")+'</strong></div></div></aside>';
 }
 function render(){
 const live=state.connected&&state.verified;
 root.innerHTML='<button type="button" class="lens-launcher" data-lens="toggle" aria-label="'+(state.open?"Close":"Open")+' Atlas Lens" aria-haspopup="dialog" aria-expanded="'+state.open+'"><span class="lens-launcher-icon">'+svg("lens")+'</span><span class="lens-launcher-word"><strong>Ask Atlas</strong><small>Assistant</small></span><span class="lens-live-dot '+(live?"online":"")+'"></span></button>'+
 '<section class="lens-panel '+(state.expanded?"expanded":"")+'" id="atlasLensPanel" role="dialog" aria-modal="false" aria-label="Atlas Lens research assistant" '+(state.open?"":"hidden")+'>'+
 '<header class="lens-header"><div class="lens-identity"><span class="lens-symbol" aria-hidden="true">'+svg("lens")+'</span><div class="lens-identity-copy"><strong>Atlas assistant</strong><small>'+(live?"Verified · "+escapeHTML(short(state.model,42)):state.connected?"Route not verified · "+escapeHTML(short(state.model,35)):"Private runtime unavailable")+'</small></div></div><div class="lens-header-tools"><button type="button" class="lens-icon-btn" data-lens="history" title="Recent conversations" aria-label="Recent conversations" aria-expanded="'+state.historyOpen+'">'+svg("history")+'</button><button type="button" class="lens-icon-btn" data-lens="settings" title="Model settings" aria-label="Model settings">'+svg("settings")+'</button><button type="button" class="lens-icon-btn" data-lens="new" title="New conversation" aria-label="New conversation" '+(state.busy?"disabled":"")+'>'+svg("plus")+'</button><button type="button" class="lens-icon-btn" data-lens="expand" title="'+(state.expanded?"Compact panel":"Expand workspace")+'" aria-label="'+(state.expanded?"Compact panel":"Expand workspace")+'">'+svg(state.expanded?"shrink":"expand")+'</button><button type="button" class="lens-icon-btn" data-lens="close" title="Close assistant" aria-label="Close assistant">'+svg("close")+'</button></div></header>'+historyMenu()+
 '<div class="lens-context"><span class="lens-context-prefix">Context</span><select aria-label="Application context" id="lensScope" '+(state.busy?"disabled":"")+'>'+contextOptions()+'</select><span class="lens-context-arrow">⌄</span><span class="lens-provider" title="'+escapeHTML(state.model||"No verified model")+'"><i class="lens-status-dot '+(live?"online":"")+'"></i><span>'+escapeHTML(short(state.provider||"Offline",21))+'</span></span></div>'+
 '<div class="lens-layout"><div class="lens-main"><div class="lens-history" id="lensHistory" aria-live="polite" aria-relevant="additions">'+feed()+'</div><div class="lens-composer-area"><form id="lensForm" class="lens-composer"><textarea id="lensInput" aria-label="Ask Atlas Lens" maxlength="1600" rows="1" placeholder="'+(state.connected?"Ask about deadlines, evidence, or research fit…":"Connect a model to ask about your applications…")+'" '+(state.busy?"disabled":"")+'>'+escapeHTML(state.draft)+'</textarea><button class="lens-send" type="'+(state.busy?"button":"submit")+'" data-lens="'+(state.busy?"stop":"send")+'" aria-label="'+(state.busy?"Stop waiting (model may continue)":"Send message")+'" '+(!state.connected||(!state.verified&&!state.busy)?"disabled":"")+'>'+svg(state.busy?"stop":"send")+'</button></form><div class="lens-composer-bottom"><select id="lensAgent" class="lens-agent-select" aria-label="Research agent" '+(!state.connected||state.busy?"disabled":"")+'>'+agentOptions()+'</select><span class="lens-composer-hint">Enter to send · Shift+Enter for line</span></div></div></div>'+sidecar()+'</div>'+
 '<footer class="lens-footer-status"><span>Read-only suggestions · Verify against sources</span><span>'+(state.busy?"Processing":live?"Private inference ready":"Read-only preview")+'</span></footer></section>';
 }
 function setOpen(v){
 const panel=byId("atlasLensPanel");
 if(v&&!state.open)focusReturn=document.activeElement;
 state.open=v;render();
 if(v){byId("lensInput")?.focus();const h=byId("lensHistory");if(h&&state.turns.length)h.scrollTop=h.scrollHeight;void refresh().then(()=>{if(state.open)byId("lensInput")?.focus()})}
 else if(focusReturn?.isConnected)focusReturn.focus();
 }
 async function refresh({silent=false}={}){
   if(!isLocal()){state.connected=false;state.verified=false;if(!silent)render();return}
   try{
     const response=await fetch("./api/assistant/bootstrap",{headers:{"Accept":"application/json"},cache:"no-store"});
     if(!response.ok)throw Error("Private AI runtime unavailable");
     const data=await response.json();
     if(data.security?.local_only!==true||!Array.isArray(data.catalog?.agents))throw Error("Invalid private runtime response");
     state.connected=true;state.agents=data.catalog.agents;
     state.providers=Array.isArray(data.catalog.providers)?data.catalog.providers:[];
     state.providerStates=data.provider_states||{};
     state.routes=data.routing?.agent_assignments||{};
     state.conversations=Array.isArray(data.conversations)?data.conversations:[];
     const prefs=data.settings||{};
     state.agent=state.agents.some(a=>a.id===state.agent)?state.agent:(prefs.default_agent||state.agents[0]?.id||"");
     state.sourceAsOf=data.as_of||state.sourceAsOf;syncRoute();
     if(!state.hydrated){
       state.hydrated=true;
       try{
         const saved=localStorage.getItem(threadStorageKey);
         if(saved&&!state.applicationId&&!state.turns.length&&state.conversations.some(x=>x.id===saved))
           await openThread(saved,{silent:true});
       }catch{}
     }
   }catch(error){
     state.connected=false;state.verified=false;state.provider="Not connected";
     state.model="";state.routeState="unavailable";state.routeReason=String(error.message||"");
   }
   if(!silent)render();
 }
 function context(value){
   if(state.busy)return;
   const next=value&&records().some(x=>x.id===value)?value:"";
   if(next!==state.applicationId){clearThread();state.applicationId=next}
   if(state.open)render();
 }
 async function submit(value){
   const text=String(value??state.draft).trim();
   if(!text||state.busy||!state.connected||!state.verified)return;
   state.draft="";state.error="";
   const turn={role:"user",text};state.turns.push(turn);
   const controller=new AbortController();state.abort=controller;state.busy=true;
   const sequence=++requestSequence;
   render();const history=byId("lensHistory");if(history)history.scrollTop=history.scrollHeight;
   try{
     const body={agent_id:state.agent,input_text:text,conversation:true,
       ...(state.applicationId?{application_id:state.applicationId}:{}),
       ...(state.conversationId?{conversation_id:state.conversationId}:{})};
     const response=await fetch("./api/agents/run",{method:"POST",
       headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:controller.signal});
     let result={};try{result=await response.json()}catch{}
     if(!response.ok)throw Error(result.error||"The model request failed");
     if(sequence!==requestSequence)return;
     state.conversationId=result.conversation_id||state.conversationId;
     if(state.conversationId){try{localStorage.setItem(threadStorageKey,state.conversationId)}catch{}}
     state.turns.push({role:"assistant",text:String(result.text||"No model response returned."),
       id:result.id,model:result.model,provider:result.provider_id,agent:result.agent_id,
       latency:result.latency_ms,sourceAsOf:result.source_as_of,tools:result.tools||[],
       evidence_refs:result.evidence_refs||[],retrievalMethod:result.retrieval_method,openTrace:false});
     state.sourceAsOf=result.source_as_of||state.sourceAsOf;
     void fetchThreads();
     try{Promise.resolve(onRunComplete?.(result)).catch(()=>{})}catch{}
   }catch(error){
     if(sequence!==requestSequence)return;
     if(state.turns.at(-1)===turn)state.turns.pop();
     state.draft=text;
     state.error=error.name==="AbortError"
       ?"Stopped waiting. The model may still finish; check recent conversations."
       :short(error.message||"Inference failed",240);
   }finally{
     if(sequence===requestSequence){
       state.busy=false;state.abort=null;render();
       const h=byId("lensHistory");if(h)h.scrollTop=h.scrollHeight;
     }
   }
 }
 root.addEventListener("click",event=>{
 const button=event.target.closest("[data-lens]");if(!button)return;
 const action=button.dataset.lens;
 if(action==="toggle"){setOpen(!state.open);return}
 if(action==="close"){setOpen(false);return}
 if(action==="expand"){state.expanded=!state.expanded;render();byId("lensInput")?.focus();return}
 if(action==="new"){if(state.busy)return;clearThread();state.draft="";render();byId("lensInput")?.focus();return}
 if(action==="history"){if(state.busy||!state.connected)return;state.historyOpen=!state.historyOpen;void fetchThreads().then(()=>render());render();return}
 if(action==="open-thread"){if(state.busy)return;void openThread(button.dataset.id).catch(error=>{state.error=short(error.message,200);render()});return}
 if(action==="delete-thread"){if(state.busy)return;void deleteThread(button.dataset.id).catch(error=>{state.error=short(error.message,200);render()});return}
 if(action==="settings"){setOpen(false);openSettings?.();return}
 if(action==="focus-record"){setOpen(false);onFocusApplication?.(button.dataset.id);return}
 if(action==="refresh"){refresh();return}
 if(action==="prompt"){state.draft=button.dataset.value||"";render();byId("lensInput")?.focus();return}
 if(action==="stop"){state.abort?.abort();return}
 if(action==="copy"){const t=state.turns[Number(button.dataset.index)];if(t&&navigator.clipboard)navigator.clipboard.writeText(t.text);return}
 if(action==="trace"){const t=state.turns[Number(button.dataset.index)];if(t){t.openTrace=!t.openTrace;render();}return}
 });
 root.addEventListener("submit",event=>{if(event.target.id!=="lensForm")return;event.preventDefault();submit();});
 root.addEventListener("input",event=>{if(event.target.id==="lensInput")state.draft=event.target.value;});
 root.addEventListener("change",event=>{if(event.target.id==="lensScope")context(event.target.value);if(event.target.id==="lensAgent"&&!state.busy){if(state.agent!==event.target.value){clearThread();state.agent=event.target.value;syncRoute();render();byId("lensInput")?.focus()}}});
 root.addEventListener("keydown",event=>{
 if(event.target.id==="lensInput"&&event.key==="Enter"&&!event.shiftKey&&!event.isComposing){event.preventDefault();submit();}
 if(event.key==="Escape"&&state.open){event.preventDefault();setOpen(false);}
 });
 document.addEventListener("keydown",event=>{
 if(event.key==="Escape"&&state.open&&!event.defaultPrevented&&!document.body.classList.contains("modal-open")){event.preventDefault();setOpen(false)}
 if((event.ctrlKey||event.metaKey)&&event.shiftKey&&event.key.toLowerCase()==="j"){event.preventDefault();setOpen(!state.open)}
 });
 render();refresh();
 return {open:()=>setOpen(true),setApplication:context,refresh,refreshData:()=>{if(state.open)render()},inspect:()=>({...state,abort:undefined})};
}
