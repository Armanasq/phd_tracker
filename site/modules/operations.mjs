import {renderCapacityReport, capacityCsv} from "./capacity-view.mjs";
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const title=x=>String(x||"").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const opt=(pairs,selected)=>pairs.map(([value,label])=>'<option value="'+esc(value)+'"'+(value===selected?' selected':'')+'>'+esc(label)+'</option>').join("");
const input=(name,label,value="",type="text",extra="")=>'<label class="os-field"><span>'+esc(label)+'</span><input name="'+name+'" type="'+type+'" value="'+esc(value)+'" '+extra+'></label>';
const select=(name,label,choices,selected="")=>'<label class="os-field"><span>'+esc(label)+'</span><select name="'+name+'">'+opt(choices,selected)+'</select></label>';
const area=(name,label,value="",rows=3)=>'<label class="os-field"><span>'+esc(label)+'</span><textarea name="'+name+'" rows="'+rows+'" maxlength="3000">'+esc(value)+'</textarea></label>';
const button=(label,action,id="",kind="quiet")=>'<button type="button" class="os-btn '+kind+'" data-ops-action="'+action+'" data-id="'+esc(id)+'">'+esc(label)+'</button>';
const section=(label,description,body)=>'<section class="os-panel"><div class="os-panel-heading"><div><h2>'+esc(label)+'</h2><p>'+esc(description)+'</p></div></div>'+body+'</section>';
const stages=["not_requested","requested","acknowledged","uploaded","portal_verified","declined"];
const statuses=["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"];
const priorities=["high","normal","low"];
const verification=["unverified","primary_confirmed","needs_review","contradicted","superseded"];
const kinds=["final","priority","scholarship","referee","supervisor_contact","interview","offer","registration","other"];
const dates=x=>!x?"Unrecorded":String(x);
const options=choices=>choices.map(x=>[x,title(x)]);

export function createOperations({request,onChange,onReload,getRecords,notify}){
 const state={data:null,loading:false,loadedAttempt:false,tab:"overview",busy:false,editing:null,kind:null,applicationId:"",schedule:null,showProof:false,message:""};
 const records=()=>getRecords().filter(x=>x.record_type==="tracked");
 const apps=()=>records().map(r=>[r.id,r.name]);
 const byId=id=>records().find(x=>x.id===id)||null;
 const d=()=>state.data||{};
 const refs=()=>d().referees||[];
 const storeItems=kind=>kind==="profile"?(d().profile?.id?[d().profile]:[]):kind==="referee"?refs():kind==="reference"?d().references||[]:kind==="milestone"?d().milestones||[]:d().claims||[];
 function selectApp() {if(!byId(state.applicationId))state.applicationId=records()[0]?.id||"";return state.applicationId;}
 function tabs(){return '<nav class="os-tabs" aria-label="Application operation sections">'+[
  ["overview","Control center"],["application","Private application"],["referees","References"],["milestones","Deadlines"],["evidence","Evidence ledger"],["capacity","Capacity planning"]
 ].map(([id,label])=>'<button type="button" data-ops-action="tab" data-id="'+id+'" class="'+(state.tab===id?"active":"")+'">'+label+'</button>').join("")+'</nav>';}
 function cards(){
  const matrix=d().referee_matrix||{},events=d().deadline_events||[],conflicts=d().evidence_conflicts||[];
  const unresolved=events.filter(x=>x.days_left!==null&&x.days_left>=0&&x.days_left<=14&&!x.cutoff_fully_verified);
  return '<div class="os-kpi-strip ops-metrics">'+[
   [records().length,"Tracked applications"],[matrix.pending||0,"References unverified"],[unresolved.length,"Deadline checks within 14d"],[conflicts.length,"Unresolved evidence conflicts"]
  ].map(([v,label])=>'<div><strong>'+v+'</strong><span>'+label+'</span></div>').join("")+'</div>';
 }
 function overview(){
  const queue=d().proof_queue||{total:0,items:[]};
  const proofItems=state.showProof?queue.items:(queue.items||[]).slice(0,10);
  const proofPanel=section("Priority evidence work queue",
   "Transparent proof-obligation triage, not admissions probability. Every action requires original evidence.",
   '<div class="ops-rows">'+proofItems.map(item=>
    '<div class="ops-row"><div><strong>'+esc(item.application)+'</strong><small>'+esc(item.action)+' · '+esc(item.proof_needed)+'</small></div>'+
    '<div class="os-actions"><span class="os-badge">'+esc(item.heuristic_priority)+' triage</span>'+button("Inspect","proof",item.id)+'</div></div>').join("")+
   (proofItems.length?"":'<p class="os-empty">No outstanding proof obligations identified in the tracked data.</p>')+'</div>'+
   (queue.total>10?'<div class="os-form-footer" style="padding:10px 20px 20px">'+button(state.showProof?"Show top ten":"Show all "+queue.items.length,"toggle-proof")+'</div>':""));
  const matrix=d().referee_matrix||{},urgent=(matrix.requests||[]).filter(r=>r.needs_attention).slice(0,12),
   conflicts=d().evidence_conflicts||[],
   upcoming=(d().deadline_events||[]).filter(e=>e.days_left!==null&&e.days_left>=0).slice(0,12);
  return proofPanel+'<div class="ops-columns">'+
   section("Upcoming proof obligations","Dates are not fully verified until an official cutoff time, time zone and primary source agree.",
   '<div class="ops-rows">'+upcoming.map(item=>
    '<div class="ops-row"><div><strong>'+esc(byId(item.application_id)?.name||item.application_id)+'</strong><small>'+esc(item.kind)+' · '+esc(item.date||"Unknown")+' · '+(item.cutoff_fully_verified?"Cutoff verified":"Cutoff unverified")+'</small></div><span class="os-badge '+(item.cutoff_fully_verified?"good":"warn")+'">'+esc(item.days_left)+' days</span></div>').join("")+
   (!upcoming.length?'<p class="os-empty">No upcoming dated milestones are recorded.</p>':'')+'</div>')+
   section("Referee dependencies","Recommender requests are tracked separately from successful portal verification.",
    '<div class="ops-rows">'+urgent.map(row=>
     '<div class="ops-row"><div><strong>'+esc(row.referee)+'</strong><small>'+esc(byId(row.application_id)?.name||row.application_id)+' · '+esc(title(row.status))+'</small></div><span class="os-badge warn">'+esc(row.days_left)+' days</span></div>').join("")+
    (!urgent.length?'<p class="os-empty">No urgent known referee deadlines.</p>':'')+'</div>')+
   '</div>'+
   section("Conflicting evidence","Source contradictions require independent verification rather than automatic reconciliation.",
    '<div class="ops-rows">'+conflicts.slice(0,12).map(item=>
     '<div class="ops-row"><div><strong>'+esc(byId(item.application_id)?.name||item.application_id)+'</strong><small>'+esc(item.field)+' · '+esc(item.claim_ids.length)+' conflicting claims</small></div>'+
     button("Review","tab","evidence")+'</div>').join("")+(conflicts.length===0?'<p class="os-empty">No contradictions detected among privately recorded evidence claims.</p>':'')+'</div>')+
   '<div class="os-hint">This control center displays evidence and operational state; it does not estimate acceptance probability or contact a university.</div>';
 }
 function editor(kind,id){
  state.kind=kind;
  const selected=storeItems(kind).find(x=>x.id===id)||{};
  const existing=Boolean(selected.id);
  const formId=selected.id||"";
  let body=kind!=="profile"?input("id","Record identifier",formId,"text",existing?"readonly":'placeholder="e.g. deadline_portal_1" required pattern="[A-Za-z0-9][A-Za-z0-9:_.-]{1,100}"'):"";
  if(kind==="referee"){
   body+=input("name","Referee name",selected.name||"","text","required maxlength=500")+
    input("contact","Private contact",selected.contact||"")+input("affiliation","Institution",selected.affiliation||"")+
    area("notes","Notes",selected.notes||"");
  }else if(kind==="reference"){
   body+=select("referee_id","Referee",refs().map(x=>[x.id,x.name]),selected.referee_id||refs()[0]?.id)+
    select("application_id","Application",apps(),selected.application_id||selectApp())+
    select("status","Portal progress",options(stages),selected.status||"not_requested")+
    input("deadline","Referee deadline",selected.deadline||"","date")+
    area("notes","Portal verification notes",selected.notes||"");
  }else if(kind==="milestone"){
   body+=select("application_id","Application",apps(),selected.application_id||selectApp())+
    select("kind","Milestone",options(kinds),selected.kind||"final")+
    '<div class="os-form-two">'+input("date","Official date",selected.date||"","date","required")+
    input("time","Official time",selected.time||"","time")+'</div>'+
    input("timezone","Official IANA timezone",selected.timezone||"","","placeholder='e.g. Europe/London'")+
    select("verification","Source verification",options(verification),selected.verification||"unverified")+
    input("source_url","Official HTTPS source",selected.source_url||"","url")+
    area("notes","Evidence notes",selected.notes||"");
  }else if(kind==="evidence"){
   body+=select("application_id","Application",apps(),selected.application_id||selectApp())+
    input("field","Claim field",selected.field||"","","required placeholder='e.g. funding_eligibility'")+
    select("status","Evidence status",options(verification),selected.status||"unverified")+
    input("source_url","Source URL (HTTPS)",selected.source_url||"","url")+
    input("observed_at","Date inspected",selected.observed_at||"","date")+
    area("assertion","Claim or attributed paraphrase",selected.assertion||"")+
    area("excerpt","Short supporting excerpt",selected.excerpt||"")+
    area("notes","Caveats or contradictions",selected.notes||"");
  }else if(kind==="profile"){
   body=area("research_topics","Research topics (one per line)",(selected.research_topics||[]).join("\n"))+
    area("skills","Research skills (one per line)",(selected.skills||[]).join("\n"))+
    area("projects","Verified projects (one per line)",(selected.projects||[]).join("\n"))+
    input("hours_per_week","Available hours per week",selected.hours_per_week??"","number",'step="0.5" min="0.5" max="168"')+
    '<fieldset class="os-tool-field"><legend>Shared document effort (hours; optional)</legend><div class="ops-document-grid">'+
    ["academic_cv","research_statement","transcripts","recommendations","english_proof","research_portfolio"].map(key=>
      input("document_"+key,title(key),selected.document_effort?.[key]??"","number",'min="0" max="300" step="0.5"')).join("")+'</div></fieldset>'+
    area("notes","Private applicant profile",selected.notes||"");
  }
  return '<section class="os-panel ops-edit"><div class="os-panel-heading"><div><h2>'+(existing?"Edit "+title(kind):"Add "+title(kind))+'</h2><p>Saved in the private database. Nothing is published to GitHub Pages.</p></div>'+button("Close","close-edit")+'</div>'+
   '<form data-ops-form="private" data-kind="'+kind+'" class="os-form">'+body+
   '<div class="os-form-footer"><button type="submit" class="os-btn primary">Save private record</button>'+
   (existing&&kind!=="profile"?button("Delete","delete",kind+":"+formId):"")+'</div></form></section>';
 }
 function listData(kind){
  const array=storeItems(kind);
  if(!array.length)return '<p class="os-empty">No private '+title(kind)+' records. Add the first verified entry.</p>';
  return '<div class="ops-rows">'+array.map(item=>{
   const id=item.id;
   const label=kind==="referee"?item.name:kind==="reference"?
    ((refs().find(r=>r.id===item.referee_id)?.name||item.referee_id)+" · "+(byId(item.application_id)?.name||item.application_id)):
    kind==="milestone"?((byId(item.application_id)?.name||item.application_id)+" · "+title(item.kind)):
    (byId(item.application_id)?.name||item.application_id)+" · "+title(item.field);
   const detail=kind==="referee"?item.affiliation:kind==="reference"?(title(item.status)+" · "+dates(item.deadline)):
    kind==="milestone"?(dates(item.date)+" · "+(item.time||"Time unverified")+" · "+(item.timezone||"Time zone unverified")):
    (item.assertion||"").slice(0,160);
   return '<div class="ops-row"><div><strong>'+esc(label)+'</strong><small>'+esc(detail)+'</small></div>'+button("Edit","edit",kind+":"+id)+'</div>';
  }).join("")+'</div>';
 }
 function referees(){
  const metrics=d().referee_matrix||{};
  return '<div class="os-actions ops-action-line">'+button("Add referee","new","referee","primary")+
   button("New reference request","new","reference")+'</div>'+
   '<div class="ops-columns">'+section("Referee directory",refs().length+" privately maintained contacts.",listData("referee"))+
   section("Reference requests",(metrics.pending||0)+" pending · "+(metrics.urgent||0)+" urgent",listData("reference"))+'</div>'+
   (state.kind==="referee"||state.kind==="reference"?editor(state.kind,state.editing):"");
 }
 function milestones(){
  const events=d().deadline_events||[];
  return '<div class="os-actions ops-action-line">'+button("Record verified deadline","new","milestone","primary")+'</div>'+
   section("Multiple independent cutoff clocks","Keep priority, scholarship, final, referee and interview deadlines separate.",
    '<div class="ops-rows">'+events.slice(0,65).map(item=>
     '<div class="ops-row"><div><strong>'+esc(byId(item.application_id)?.name||item.application_id)+'</strong>'+
     '<small>'+esc(title(item.kind))+' · '+esc(item.date||"Unknown")+(item.time?" "+esc(item.time):"")+
     (item.timezone?" "+esc(item.timezone):"")+' · '+esc(item.provenance||"Source")+'</small></div>'+
     '<div class="os-actions"><span class="os-badge '+(item.cutoff_fully_verified?"good":"warn")+'">'+(item.cutoff_fully_verified?"Verified clock":"Needs cutoff evidence")+'</span>'+
     (item.provenance?.startsWith("Private")?button("Edit","edit","milestone:"+item.id):"")+'</div></div>').join("")+'</div>')+
   (state.kind==="milestone"?editor("milestone",state.editing):"");
 }
 function evidence(){
  const conflicts=d().evidence_conflicts||[];
  return '<div class="os-actions ops-action-line">'+button("Add source claim","new","evidence","primary")+'</div>'+
   (conflicts.length?'<div class="os-hint">'+conflicts.length+' unresolved claim groups require manual comparison.</div>':'')+
   section("Claim-level provenance","Source URL, observed date, assertion, and verification state.",listData("evidence"))+
   (state.kind==="evidence"?editor("evidence",state.editing):"");
 }
 function application(){
  const id=selectApp(),r=byId(id);
  if(!r)return '<p class="os-empty">No tracked applications were found in the current verified snapshot.</p>';
  const docs=Object.entries(r.document_states||{});
  return '<section class="os-panel"><div class="os-panel-heading"><div><h2>Owner-maintained application state</h2><p>Private edits take precedence over the public source snapshot. Optimistic version checks prevent overwrites.</p></div></div>'+
   '<form data-ops-form="application" class="os-form">'+
   select("application_id","Application",apps(),id)+
   '<div class="os-form-two">'+select("status","Preparation stage",options(statuses),r.status||"unconfirmed")+
   select("priority","Owner priority",options(priorities),r.priority||"normal")+'</div>'+
   input("followup","Follow-up date",r.followup||"","date")+
   input("estimated_hours","Estimated remaining work (hours)",r.estimated_hours??"","number",'min="0" max="400" step="0.5"')+
   area("next_step","Next concrete action",r.next_step||"")+
   area("notes","Private application notes",r.notes||"")+
   input("receipt","Submission receipt / verified reference",r.receipt||"")+
   '<label class="os-check os-approval"><input type="checkbox" name="confirmed_submission"><span>I independently verified the portal submission and explicitly confirm a status change to Submitted.</span></label>'+
   (docs.length?'<fieldset class="os-tool-field"><legend>Document readiness</legend><div class="ops-document-grid">'+docs.map(([name,readiness])=>
    select(name,title(name),options(["unknown","not_started","in_progress","ready","not_applicable"]),readiness)).join("")+'</div></fieldset>':'')+
   '<input type="hidden" name="private_version" value="'+esc(r.private_version||0)+'">'+
   '<div class="os-form-footer"><button type="submit" class="os-btn primary">Save private application state</button>'+
   '<span class="os-meta">Version '+esc(r.private_version||0)+' · application evidence remains independent</span></div></form></section>';
 }
 function capacity(){
  const profile=d().profile||{};
  const result=state.schedule;
  return '<div class="ops-columns">'+
   section("Applicant research profile","Record actual skills, projects and available work hours. Avoid generated qualifications.",
    '<div class="os-form">'+
    '<div class="ops-rows">'+[["Research topics",(profile.research_topics||[]).join(", ")],["Skills",(profile.skills||[]).join(", ")],["Projects",(profile.projects||[]).join(", ")],["Weekly hours",profile.hours_per_week??"Unrecorded"]].map(([a,b])=>
     '<div class="ops-row"><div><strong>'+esc(a)+'</strong><small>'+esc(b||"Not recorded")+'</small></div></div>').join("")+'</div>'+button("Edit private profile","new","profile","primary")+'</div>')+
   section("Capacity scenario","Deterministic scheduling using owner-provided effort estimates.",
    '<form data-ops-form="capacity" class="os-form">'+input("hours_per_week","Available hours per week",profile.hours_per_week??"","number",'required min="0.5" max="168" step="0.5"')+
    '<button class="os-btn primary" type="submit">Evaluate capacity</button><p class="os-footnote">Missing effort estimates remain unknown. The algorithm is an earliest-deadline-first heuristic, not an optimal project scheduler.</p></form>')+'</div>'+
   (result?renderCapacityReport({report:result,esc,byId,button}):"")+
   (state.kind==="profile"?editor("profile","applicant"):"");
 }
 function view(){
  if(!state.data&&!state.loading&&!state.loadedAttempt){
   state.loading=true;state.loadedAttempt=true;
   request("/api/operations").then(result=>{state.data=result;state.loading=false;onChange();})
    .catch(error=>{state.loading=false;state.message=error.message;onChange();});
  }
  if(!state.data)return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE / PORTFOLIO</div><h1>Application operations</h1><p>'+esc(state.message||"Loading verified application dependencies and private records…")+'</p></div></div></section>';
  return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE / APPLICANT OPERATIONS</div><h1>Application operations</h1>'+
   '<p>Manage private applicant state, recommendations, independent deadline clocks, claim evidence and realistic workload in the same workspace.</p></div>'+
   '<div class="os-head-actions">'+button("Refresh evidence","refresh","","quiet")+'</div></div>'+
   cards()+tabs()+
   (state.tab==="overview"?overview():state.tab==="application"?application():state.tab==="referees"?referees():
    state.tab==="milestones"?milestones():state.tab==="evidence"?evidence():capacity())+
   (state.message?'<div class="os-message" role="status">'+esc(state.message)+'</div>':"")+'</section>';
 }
 async function reload(){
  state.loading=true;state.loadedAttempt=true;
  try{state.data=await request("/api/operations");state.message="";}finally{state.loading=false;onChange();}
 }
 document.addEventListener("click",async event=>{
  const element=event.target.closest("[data-ops-action]");if(!element)return;
  event.preventDefault();
  const action=element.dataset.opsAction,id=element.dataset.id||"";
  if(action==="tab"){state.tab=id;state.editing=null;state.kind=null;onChange();return;}
  if(action==="toggle-proof"){state.showProof=!state.showProof;onChange();return;}
  if(action==="capacity-export"){
   if(!state.schedule)return;
   const data=capacityCsv(state.schedule);
   const blob=new Blob([data],{type:"text/csv;charset=utf-8"});
   const objectUrl=URL.createObjectURL(blob);
   const anchor=document.createElement("a");
   anchor.href=objectUrl;anchor.download="phd-atlas-private-capacity.csv";anchor.click();
   setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
   return;
  }
  if(action==="proof"){
   const task=d().proof_queue?.items?.find(x=>x.id===id);
   if(task){state.applicationId=task.application_id;state.tab=task.target_section;state.editing=null;state.kind=null;onChange();}
   return;
  }
  if(action==="new"){state.kind=id;state.editing=null;onChange();return;}
  if(action==="close-edit"){state.kind=null;state.editing=null;onChange();return;}
  if(action==="edit"){const [kind,...parts]=id.split(":");state.kind=kind;state.editing=parts.join(":");onChange();return;}
  if(action==="refresh"){await reload().catch(error=>notify(error.message));return;}
  if(action==="delete"){
   const [kind,...parts]=id.split(":"),identity=parts.join(":");
   if(!window.confirm("Delete private "+kind+" record "+identity+"? This action is recorded in the local audit log."))return;
   try{
    await request("/api/private/"+encodeURIComponent(kind)+"/"+encodeURIComponent(identity)+"/delete",{});
    state.kind=null;state.editing=null;await reload();
   }catch(error){notify(error.message);}
  }
 });
 document.addEventListener("change",event=>{
  if(event.target.matches('form[data-ops-form="application"] select[name="application_id"]')){
   state.applicationId=event.target.value;onChange();
  }
 });
 document.addEventListener("submit",async event=>{
  const form=event.target;if(!form.matches("[data-ops-form]"))return;
  event.preventDefault();
  if(state.busy)return;state.busy=true;
  const kind=form.dataset.opsForm,values=Object.fromEntries(new FormData(form));
  try{
   if(kind==="private"){
    const name=form.dataset.kind;
    if(name==="profile"){
     for(const key of ["research_topics","skills","projects"])values[key]=values[key].split(/\n|,/).map(x=>x.trim()).filter(Boolean);
     values.hours_per_week=values.hours_per_week?Number(values.hours_per_week):null;
     values.document_effort={};
     for(const key of ["academic_cv","research_statement","transcripts","recommendations","english_proof","research_portfolio"]){
      const val=values["document_"+key];delete values["document_"+key];
      if(val!=="")values.document_effort[key]=Number(val);
     }
    }
    for(const key of ["date","deadline","time","timezone","source_url","observed_at"])
     if(values[key]==="")delete values[key];
    await request("/api/private/"+encodeURIComponent(name),values);
    state.editing=null;state.kind=null;await reload();notify(title(name)+" saved privately.");
   }else if(kind==="application"){
    const id=values.application_id,version=Number(values.private_version);
    const patch={status:values.status,priority:values.priority,next_step:values.next_step,
                 notes:values.notes,receipt:values.receipt};
    patch.followup=values.followup||null;
    patch.estimated_hours=values.estimated_hours===""?null:Number(values.estimated_hours);
    const record=byId(id);
    const documents={};
    for(const key of Object.keys(record?.document_states||{}))if(key in values)documents[key]=values[key];
    if(Object.keys(documents).length)patch.document_states=documents;
    if(values.status==="submitted"&&values.confirmed_submission==="on")patch.confirmed_submission=true;
    await request("/api/applications/"+encodeURIComponent(id)+"/update",{expected_version:version,patch});
    await onReload();await reload();notify("Private application state updated.");
   }else if(kind==="capacity"){
    state.schedule=await request("/api/schedule",{hours_per_week:Number(values.hours_per_week)});
    onChange();
   }
  }catch(error){state.message=error.message;notify(error.message);onChange();}
  finally{state.busy=false;}
 });
 return {view,reload,selectApplication:id=>{state.applicationId=id;state.tab="application";state.kind=null;onChange();}};
}
