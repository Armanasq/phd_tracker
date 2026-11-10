import {daysUntil,isActionable,isClosed as domainClosed,riskSignal,priorityScore,validateSnapshot,documentReadiness,applyRecordFilters,draftState,deadlineCollisions,freshnessState} from "./modules/domain.mjs";
import {storageKey,legacyKeyForMigration} from "./modules/storage.mjs";
import {hostedAdvisories,hostedStatus} from "./modules/hosted-ai.mjs";
import {calendarEvents,cutoffDescription,cutoffRisk,exactCutoffReminder,verifiedCutoff} from "./modules/deadline-cutoff.mjs";
import {assessApplication,portfolioReadiness} from "./modules/readiness.mjs";
import {renderReadinessView} from "./modules/readiness-view.mjs";
import {createLocalRecord,normalizeLocalRecords,mergeLocalRecords,exportIndependentSource} from "./modules/local-records.mjs";
import {createConsole} from "./modules/console.mjs";
import {candidateQueue} from "./modules/discovery.mjs";
import {runtimeCapabilities} from "./modules/runtime-capabilities.mjs";
import {portfolioDocumentInventory} from "./modules/documents.mjs";
import {VIEWS,resolveWorkspaceRoute} from "./modules/routes.mjs";
import {mountAtlasLens} from "./modules/lens.mjs";
import {auditWorkspace} from "./modules/assurance.mjs";
import {renderAssurance,renderCoverage} from "./modules/assurance-view.mjs";
(() => {
"use strict";
const FALLBACK_REPO="https://github.com/Armanasq/phd_tracker";
let selectedAuditCategory="all",assuranceLimit=75;
let readinessFilter="all";
let discoveryFilter="all",discoveryQuery="";
let ledgerQuery="",ledgerType="all",ledgerPage=1;
const STORE=storageKey("phd-atlas-drafts-v1"),PREFS=storageKey("phd-atlas-prefs-v1"),VIEW_STORE=storageKey("phd-atlas-views-v2"),COMPARE_STORE=storageKey("phd-atlas-compare-v1"),LOCAL_STORE=storageKey("phd-atlas-local-records-v1");
const $=id=>document.getElementById(id);
const escapeHTML=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeURL=value=>{try{const u=new URL(String(value));return u.protocol==="https:"?u.href:""}catch{return""}};
const ownerRepo=()=>safeURL(state.data?.source_links?.repository)||safeURL(document.querySelector(".side-link")?.href)||FALLBACK_REPO;
const readStore=(k,d)=>{try{
 let raw=localStorage.getItem(k);
 if(raw===null){
  const oldKey=legacyKeyForMigration(k.slice(k.lastIndexOf(":")+1));
  if(oldKey){const older=localStorage.getItem(oldKey);if(older!==null){JSON.parse(older);localStorage.setItem(k,older);localStorage.removeItem(oldKey);raw=older}}
 }
 return raw===null?d:(JSON.parse(raw)??d);
 }catch{return d}};
const saveStore=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch{notify("Local storage unavailable. Export drafts as JSON.")}};
const storedViews=readStore(VIEW_STORE,{saved:[],last:{scope:"tracked",query:"",status:"all",verification:"all",country:"all",horizon:"all",sort:"deadline"}});
const readLocalRecords=()=>{try{return normalizeLocalRecords(readStore(LOCAL_STORE,[]))}catch{return []}};
const state={data:null,view:"dashboard",scope:storedViews.last?.scope||"tracked",query:storedViews.last?.query||"",status:storedViews.last?.status||"all",verification:storedViews.last?.verification||"all",country:storedViews.last?.country||"all",horizon:storedViews.last?.horizon||"all",sort:storedViews.last?.sort||"deadline",presets:Array.isArray(storedViews.saved)?storedViews.saved:[],activePreset:"",compare:readStore(COMPARE_STORE,[]),selected:null,drafts:readStore(STORE,{}),localRecords:readLocalRecords(),prefs:readStore(PREFS,{theme:"light",horizon:7,reminders:true,notified:{}}),modal:"",focus:null,calendarMonth:null,selectedDate:null,draggedId:null};
const TODAY=()=>{const zone=state.data?.timezone||"Europe/Berlin";const parts=new Intl.DateTimeFormat("en-US",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());const get=k=>parts.find(p=>p.type===k)?.value||"";return get("year")+"-"+get("month")+"-"+get("day")};
const days=due=>daysUntil(due,TODAY());
const remainingDeadlineDays=r=>{const exact=verifiedCutoff(r);return exact===null?days(r?.deadline):Math.floor((exact-Date.now())/86400000)};
const stamp=due=>due?new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"}).format(new Date(due+"T12:00:00Z")):"Unverified";
const statusLabel=s=>({unconfirmed:"Unconfirmed",shortlisted:"Shortlisted",preparing:"Preparing",submitted:"Submitted",interview:"Interview",offer:"Offer",rejected:"Rejected",withdrawn:"Withdrawn",blocked:"Blocked",archived:"Archived"})[s]||s;
const verifiedLabel=s=>({source_verified:"Source reviewed",owner_verified:"Owner verified",needs_review:"Review required",unverified:"Unverified"})[s]||"Unverified";
const isClosed=domainClosed;
const risk=r=>riskSignal(r,TODAY());
const pill=(t,style)=>'<span class="pill '+(style||"")+'">'+escapeHTML(t)+'</span>';
const link=(url,name)=>{const u=safeURL(url);return u?'<a href="'+escapeHTML(u)+'" target="_blank" rel="noopener noreferrer">'+escapeHTML(name)+' ↗</a>':""};
const count=(key)=>records().filter(key).length;
const records=()=>[...state.data.records,...state.localRecords.filter(r=>!state.data.records.some(source=>source.id===r.id))].map(r=>{if(r.local_only)return r;const draft=state.drafts[r.id]||{};const {documents:localDocs,...fields}=draft;return {...r,...fields,document_states:{...(r.document_states||{}),...(localDocs||{})}}});
const getRecord=id=>records().find(x=>x.id===id);
const thisWeek=r=>{const d=days(r.status==="submitted"?r.followup:r.deadline);return d!==null&&d>=0&&d<=7};
const open=r=>isActionable(r,TODAY());
function notify(message){const el=$("toast");el.textContent=message;el.style.display="block";clearTimeout(notify.timer);notify.timer=setTimeout(()=>el.style.display="none",3600)}
function copyText(text){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(()=>notify("Copied to clipboard."),()=>fallbackCopy(text))}else fallbackCopy(text)}
function fallbackCopy(text){const t=document.createElement("textarea");t.value=text;t.style.position="fixed";t.style.left="-10000px";document.body.appendChild(t);t.select();try{document.execCommand("copy");notify("Copied to clipboard.")}catch{notify("Use the text box to copy the command.")}t.remove()}
function dateRisk(d){if(d===null)return pill("Date unknown","neutral");if(d<0)return pill("Expired "+Math.abs(d)+"d","red");if(d===0)return pill("Today","red");if(d<=3)return pill(d+"d left","red");if(d<=7)return pill(d+"d left","warning");return pill(d+"d left","neutral")}
const deadlineRisk=r=>{const exact=cutoffRisk(r);return exact?pill(exact.label,exact.urgency):dateRisk(days(r.deadline))};
function verificationPill(r){return pill(verifiedLabel(r.verification),r.verification==="source_verified"||r.verification==="owner_verified"?"green":"warning")}
function riskPill(r){let x=risk(r);return pill(x,["Expired","Blocked","Confirmed gap","Cutoff elapsed"].includes(x)?"red":["Verify","Urgent","Duplicate route caution"].includes(x)?"warning":"neutral")}
function priority(r){return priorityScore(r,TODAY())}
function filters(list){return applyRecordFilters(list,state,TODAY())}
function sortList(list){return list.slice().sort((a,b)=>state.sort==="priority"?priority(b)-priority(a):state.sort==="name"?a.name.localeCompare(b.name):state.sort==="updated"?String(b.updated_at||"").localeCompare(String(a.updated_at||"")):(a.deadline||"9999").localeCompare(b.deadline||"9999")||a.name.localeCompare(b.name))}
function heading(title,desc,buttons=""){const n=VIEWS.findIndex(([id])=>id===state.view)+1;return '<header class="heading"><div><div class="page-context"><span class="page-index">'+String(n).padStart(2,"0")+' / '+VIEWS.length+'</span><span class="context-divider" aria-hidden="true"></span><span>PHD APPLICATION WORKSPACE</span></div><h1>'+escapeHTML(title)+'</h1><p>'+desc+'</p></div><div class="buttons">'+buttons+'</div></header>'}
function kpi(name,value,caption){return'<div class="kpi"><div class="label">'+escapeHTML(name)+'</div><strong>'+escapeHTML(value)+'</strong><small>'+escapeHTML(caption)+'</small></div>'}
function statCard(title,body){return'<section class="panel"><div class="panel-header"><h2>'+escapeHTML(title)+'</h2></div>'+body+'</section>'}
function button(label,action,value,variant="secondary"){return'<button class="btn '+variant+'" type="button" data-action="'+escapeHTML(action)+'" data-value="'+escapeHTML(value||"")+'">'+escapeHTML(label)+'</button>'}
function rowButton(r){return'<button class="rowbutton" data-action="record" data-value="'+escapeHTML(r.id)+'">'+escapeHTML(r.name)+'</button>'}
function row(r,showCompare=false){return'<tr><td>'+rowButton(r)+'<small>'+escapeHTML(r.id)+' · '+(r.record_type==="candidate"?"Candidate · Not promoted":escapeHTML(r.country||"Country unrecorded"))+'</small></td><td>'+deadlineRisk(r)+'<small>'+escapeHTML(stamp(r.deadline))+'</small></td><td>'+verificationPill(r)+'</td><td>'+pill(statusLabel(r.status),r.status==="submitted"?"green":"neutral")+'</td><td>'+riskPill(r)+'</td><td>'+escapeHTML(r.next_step||"Next step unrecorded").slice(0,165)+'</td>'+(showCompare?'<td><input class="check" type="checkbox" data-compare="'+escapeHTML(r.id)+'" aria-label="Compare '+escapeHTML(r.name)+'" '+(state.compare.includes(r.id)?"checked":"")+'></td>':"")+'</tr>'}
function table(list,compare=false){
 const desktop='<div class="tablewrap desktop-table"><table class="table"><thead><tr><th>Opportunity</th><th>Deadline</th><th>Evidence</th><th>Owner status</th><th>Risk signal</th><th>Next action</th>'+(compare?'<th>Compare</th>':"")+'</tr></thead><tbody>'+list.map(r=>row(r,compare)).join("")+'</tbody></table></div>';
 const mobile='<div class="app-card-list">'+list.map(r=>
  '<article class="app-card"><div class="app-card-top"><div class="app-card-title">'+rowButton(r)+
  '<small>'+escapeHTML(r.id)+' · '+(r.record_type==="candidate"?"Candidate · Not promoted":escapeHTML(r.country||"Country unrecorded"))+'</small></div>'+
  '<div class="app-card-due">'+deadlineRisk(r)+'<small>'+escapeHTML(stamp(r.deadline))+'</small></div></div>'+
  '<div class="app-card-labels">'+verificationPill(r)+' '+pill(statusLabel(r.status),r.status==="submitted"?"green":"neutral")+' '+riskPill(r)+'</div>'+
  '<div class="app-card-action">'+escapeHTML(r.next_step||"Next step unrecorded")+'</div>'+
  (compare?'<label class="app-card-compare"><input class="check" type="checkbox" data-compare="'+escapeHTML(r.id)+'" aria-label="Compare '+escapeHTML(r.name)+'" '+(state.compare.includes(r.id)?"checked":"")+'><span>Compare this opportunity</span></label>':"")+
  '</article>'
 ).join("")+'</div>';
 return desktop+mobile;
}
const filterFields=["scope","query","status","verification","country","horizon","sort"];
function currentFilters(){return Object.fromEntries(filterFields.map(k=>[k,state[k]]))}
function persistViews(){saveStore(VIEW_STORE,{saved:state.presets,last:currentFilters()})}
function resetFilters(){Object.assign(state,{scope:"tracked",query:"",status:"all",verification:"all",country:"all",horizon:"all",sort:"deadline",activePreset:""});persistViews();render();notify("Filters cleared.")}
function applySavedView(name){
 const view=state.presets.find(x=>x.name===name);
 if(!view)return;
 for(const k of filterFields)if(typeof view.filters?.[k]==="string")state[k]=view.filters[k];
 state.activePreset=name;persistViews();render();notify("Restored view: "+name);
}
function saveCurrentView(){
 openModal("<h2>Save this view</h2>",'<div class="field"><label for="viewName">View name</label><input id="viewName" class="input" maxlength="42" autocomplete="off" placeholder="e.g. Near-term verified calls" value="'+escapeHTML(state.activePreset)+'"><p class="subtle">Saved on this device. Includes the current search, scope, filters, and sort order.</p><p id="viewError" class="form-error" role="alert"></p></div><div class="buttons">'+button("Save view","confirm-view","","primary")+button("Cancel","close")+'</div>');
 $("viewName")?.focus();
}
function commitSavedView(){
 const name=$("viewName")?.value.trim()||"";
 const error=$("viewError");
 if(name.length<2||name.length>42){if(error)error.textContent="Use a name between 2 and 42 characters.";return}
 const saved=state.presets.filter(x=>x.name.toLocaleLowerCase()!==name.toLocaleLowerCase());
 if(saved.length>=12){if(error)error.textContent="Maximum 12 saved views. Delete an unused view first.";return}
 state.presets=[...saved,{name,filters:currentFilters()}].sort((a,b)=>a.name.localeCompare(b.name));
 state.activePreset=name;persistViews();closeModal();render();notify("Saved view “"+name+"” on this device.");
}
function deleteSavedView(){
 const name=state.activePreset;
 if(!name)return;
 if(!confirm("Delete saved view “"+name+"”? Current filters will remain."))return;
 state.presets=state.presets.filter(x=>x.name!==name);state.activePreset="";persistViews();render();notify("Saved view deleted.");
}
function toolbar(list){
 const countries=[...new Set(records().map(r=>r.country).filter(Boolean))].sort();
 const options=(values,current)=>values.map(([value,label])=>'<option value="'+escapeHTML(value)+'"'+(value===current?" selected":"")+'>'+escapeHTML(label)+'</option>').join("");
 return '<div class="view-presets"><label for="viewPreset">Saved view</label><select id="viewPreset" class="select" aria-label="Choose a saved view">'+options([["","Choose a view…"],...state.presets.map(x=>[x.name,x.name])],state.activePreset)+'</select>'+button("Save view","save-view")+ (state.activePreset?button("Delete","delete-view"):"")+'<span class="view-presets-note">Stored on this device</span></div>'+
 '<div class="toolbar"><input class="input" type="search" id="filterQuery" placeholder="Search programme, faculty, topic, source ID…" value="'+escapeHTML(state.query)+'" aria-label="Search applications">'+
 '<select class="select" id="filterScope" aria-label="Application lifecycle scope">'+options([["tracked","Tracked applications"],["candidate","Research candidates"],["all","All records"]],state.scope)+'</select>'+
 '<select class="select" id="filterStatus" aria-label="Filter by owner status">'+options([["all","All statuses"],...["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"].map(v=>[v,statusLabel(v)])],state.status)+'</select>'+
 '<select class="select" id="filterVerify" aria-label="Filter by evidence">'+options([["all","All evidence"],["source_verified","Source reviewed"],["owner_verified","Owner verified"],["needs_review","Needs review"],["unverified","Unverified"]],state.verification)+'</select>'+
 '<select class="select" id="filterHorizon" aria-label="Filter by deadline">'+options([["all","Any deadline"],["3","Next 3 days"],["7","Next 7 days"],["14","Next 14 days"],["30","Next 30 days"],["expired","Expired"],["unknown","Undated"]],state.horizon)+'</select>'+
 '<select class="select" id="filterCountry" aria-label="Filter by country">'+options([["all","All countries"],...countries.map(x=>[x,x])],state.country)+'</select>'+
 '<select class="select" id="filterSort" aria-label="Sort order">'+options([["deadline","Soonest first"],["priority","Priority first"],["name","Name A–Z"],["updated","Recently edited"]],state.sort)+'</select>'+
 button("Clear","clear-filters")+'<span class="count" aria-live="polite">'+list.length+' records</span></div>';
}
function dashboard(){
 if(state.data.instance?.data_mode==="starter"&&!state.localRecords.length)return heading("Set up your PhD workspace","This independent deployment starts without inherited applications or unverified opportunity claims.",button("Create local opportunity","new-local","","primary")+button("Setup guide","url",ownerRepo()+"/blob/main/docs/SELF_HOSTING.md")+button("Repository","url",ownerRepo()))+
 '<div class="info">No PhD application evidence has been imported. This does not mean no opportunities exist. Add your own reviewed sources, then enable source mode in this repository’s Actions settings.</div>'+
 statCard("First-run checklist",'<div class="mini-list"><div class="mini-row"><strong>01 · Export local opportunities to data/user_opportunities.json</strong></div><div class="mini-row"><strong>02 · Review your own primary university evidence before publishing</strong></div><div class="mini-row"><strong>03 · Set PHD_ATLAS_DATA_MODE to source in GitHub Actions variables</strong></div><div class="mini-row"><strong>04 · Rerun the Pages publisher and inspect the release manifest</strong></div></div>');
 const all=records(),tracked=all.filter(r=>r.record_type==="tracked");
 const active=tracked.filter(open),today=active.filter(r=>r.status!=="submitted"&&days(r.deadline)===0),week=active.filter(thisWeek);
 const verify=active.filter(r=>r.verification!=="source_verified"&&r.verification!=="owner_verified");
 const queue=active.slice().sort((a,b)=>priority(b)-priority(a)).slice(0,9);
 const bins=[["Today",0,0],["1–3 days",1,3],["4–7 days",4,7],["8–14 days",8,14],["15–30 days",15,30]];
 const distribution=bins.map(([name,from,to])=>[name,active.filter(r=>days(r.deadline)>=from&&days(r.deadline)<=to).length]),max=Math.max(1,...distribution.map(x=>x[1]));
 const unknownDocs=tracked.filter(r=>Object.values(r.document_states||{}).includes("unknown")).length;
 const dupRoutes=tracked.filter(r=>r.duplicate_submission_advisory).length;
 const followups=active.filter(r=>r.followup&&days(r.followup)!==null&&days(r.followup)<=0).length;
 const failing=state.data.providers.filter(p=>p.health!=="ok").length;
 const collisions=deadlineCollisions(active,TODAY());
 const nearest=active.filter(r=>{const d=days(r.deadline);return r.status!=="submitted"&&d!==null&&d>=0}).sort((a,b)=>days(a.deadline)-days(b.deadline)||priority(b)-priority(a))[0]||null;
 const closingDays=nearest?days(nearest.deadline):null;
 const timeZero=new Date(TODAY()+"T12:00:00Z");
 const runway=Array.from({length:7},(_,offset)=>{
  const date=new Date(timeZero);date.setUTCDate(date.getUTCDate()+offset);
  const iso=date.toISOString().slice(0,10),due=active.filter(r=>r.deadline===iso).length;
  const weekday=offset===0?"TODAY":new Intl.DateTimeFormat("en-GB",{weekday:"short",timeZone:"UTC"}).format(date).toUpperCase();
  return '<button type="button" class="runway-day'+(due?' has-due':'')+(offset===0?' is-today':'')+'" data-action="nav" data-value="calendar"><span class="runway-weekday">'+weekday+'</span><span class="runway-daynumber">'+date.getUTCDate()+'</span><span class="runway-due">'+(due?due+' due':'—')+'</span><span class="sr-only"> '+escapeHTML(stamp(iso))+'; open calendar</span></button>';
 }).join("");
 return '<div class="operational-hero"><div class="today-head"><div><div class="desk-kicker">Fall 2027 · '+escapeHTML(stamp(TODAY()))+'</div><h1>Today’s work</h1><p>Deadlines, decisions and evidence requiring attention.</p></div><div class="buttons">'+button("All applications","nav","applications")+button("Readiness","nav","readiness")+button("Open actions","nav","actions","primary")+'</div></div>'+
 '<section class="decision-brief" aria-label="Next recorded application closing"><div class="decision-brief-label"><span>Next recorded deadline</span><span>Official cutoff unverified</span></div>' +
 (nearest?'<div class="decision-brief-body"><div class="decision-brief-days"><strong>'+(closingDays===0?'00':String(closingDays).padStart(2,'0'))+'</strong><span>'+(closingDays===0?'Due today':'Days remaining')+'</span></div><div class="decision-brief-context"><button type="button" class="decision-brief-link" data-action="record" data-value="'+escapeHTML(nearest.id)+'">'+escapeHTML(nearest.name)+'</button><span>'+escapeHTML(stamp(nearest.deadline))+' · '+escapeHTML(nearest.country||'Country unrecorded')+'</span></div></div>':'<div class="decision-brief-none">No upcoming dated calls are recorded. Undated opportunities remain in the registry.</div>')+
 '<div class="decision-brief-bottom"><span>Whole dates are not verified portal closing times.</span><button type="button" data-action="nav" data-value="calendar">Open calendar ↗</button></div></section></div>'+
 '<div class="source-strip"><span><strong>Evidence dated '+escapeHTML(stamp(state.data.as_of))+'</strong> &nbsp;·&nbsp; '+tracked.length+' tracked applications &nbsp;·&nbsp; '+state.data.meta.candidates+' additional candidates</span>'+link(state.data.source_links.opportunities,"Source records")+'</div>'+
 '<div class="kpis">'+kpi("Tracked applications",tracked.length,"Source-backed records")+kpi("Due today",today.length,"Check portal cutoff")+kpi("Next 7 days",week.length,"Recorded dates")+kpi("Needs verification",verify.length,"Official evidence review")+kpi("Owner-marked submitted",tracked.filter(r=>r.status==="submitted"&&r.status_confirmed).length,"Check portal receipt")+'</div>'+
 '<section class="runway" aria-label="Seven-day recorded deadline runway"><div class="runway-intro"><div><span class="runway-overline">Upcoming</span><h2>Next seven days</h2></div><span>Recorded closing dates · source-backed</span></div><div class="runway-days">'+runway+'</div></section>'+
 '<div class="desk-grid"><section class="desk-section"><div class="desk-header"><h2>Priority queue</h2><span>'+queue.length+' next decisions</span></div><div class="agenda">'+queue.map((r,i)=>
  '<div class="agenda-item"><span class="agenda-number">'+String(i+1).padStart(2,"0")+'</span><div class="agenda-main">'+rowButton(r)+
  '<div class="agenda-meta"><span>'+escapeHTML(r.id)+'</span><span>·</span><span>'+escapeHTML(stamp(r.deadline))+'</span><span>·</span><span>'+escapeHTML(verifiedLabel(r.verification))+'</span></div>'+
  '<div class="agenda-next">'+escapeHTML(r.next_step||"Confirm the next action")+'</div></div>'+dateRisk(days(r.deadline))+'</div>'
 ).join("")+'</div><div class="desk-foot"><span>Sorted by date, recorded follow-ups and evidence needs</span>'+button("View all","nav","actions","ghost")+'</div></section>'+
 '<div class="desk-side-stack"><section class="desk-section"><div class="desk-header"><h2>Deadline horizon</h2>'+button("Calendar","nav","calendar","ghost")+'</div><div style="padding:8px 20px 16px">'+distribution.map(([label,n])=>'<div class="week-row"><span>'+label+'</span><div class="week-track"><span style="width:'+(100*n/max).toFixed(1)+'%"></span></div><strong>'+n+'</strong></div>').join("")+'<p class="footnote">Dates alone do not verify portal availability.</p></div></section>'+
 '<section class="desk-section"><div class="desk-header"><h2>Needs attention</h2><span>Unknown ≠ missing</span></div><div class="attention-list" style="padding:5px 20px 11px">'+[
  ["Verify official information",verify.length,"Application source review","review"],
  ["Check document readiness",unknownDocs,"Unknown document states","applications"],
  ["Review submission routes",dupRoutes,"Potential duplicate pathways","review"],
  ["Faculty follow-ups",followups,"Follow-up date reached","contacts"],
  ["Deadline collisions",collisions.length,"Days with two or more open calls","calendar"]
 ].map(([name,n,help,view])=>'<div class="attention-item"><div><button data-action="nav" data-value="'+view+'">'+escapeHTML(name)+'</button><small>'+escapeHTML(help)+'</small></div><strong>'+n+'</strong></div>').join("")+'</div></section>'+
 '<section class="desk-section"><div class="desk-header"><h2>Source checks</h2>'+link(state.data.source_links.source_monitor,"Monitoring")+'</div><div style="padding:9px 20px 16px"><p style="margin:0 0 11px;font-size:11px;color:var(--muted)">'+failing+' of '+state.data.providers.length+' feeds need attention</p>'+state.data.providers.map(p=>'<div class="week-row" style="grid-template-columns:minmax(0,1fr) auto"><span>'+escapeHTML(p.name)+'</span>'+pill(p.health,p.health==="ok"?"green":"warning")+'</div>').join("")+'</div></section></div></div>';
}
function applications(){
 const list=sortList(filters(records()));
 const dueSoon=list.filter(r=>{const d=days(r.deadline);return d!==null&&d>=0&&d<=7}).length;
 const needsEvidence=list.filter(r=>r.verification!=="source_verified"&&r.verification!=="owner_verified").length;
 const candidates=list.filter(r=>r.record_type==="candidate").length;
 return heading("Applications","Tracked opportunities and research candidates, with source provenance and device-local views.",button("Add opportunity","new-local","","primary")+button("Compare selected ("+state.compare.length+")","nav","compare")+button("Export filtered CSV","export","csv")+button("Local backup","export","local")+button("Import backup","import-local"))+
 '<input id="localImportFile" type="file" accept=".json,application/json" hidden aria-label="Import local opportunity backup">'+
 '<div class="registry-summary" aria-label="Current filtered results"><div><span>RECORDS IN VIEW</span><strong>'+list.length+'</strong><small>current filters</small></div><div><span>DUE WITHIN 7 DAYS</span><strong>'+dueSoon+'</strong><small>recorded dates</small></div><div><span>NEEDS VERIFICATION</span><strong>'+needsEvidence+'</strong><small>source or owner review</small></div><div><span>RESEARCH CANDIDATES</span><strong>'+candidates+'</strong><small>not promoted</small></div></div>'+
 '<div class="info">Deadline dates may omit portal cutoff times and time zones. Source review does not establish current availability. Device-local records are never published automatically. Source-record edits require explicit GitHub confirmation.</div>'+
 statCard("Application registry",toolbar(list)+(list.length?table(list,true):'<div class="empty">No records match these filters. Clear filters or select a saved view.</div>'));
}
function deploymentView(){
 const report=runtimeCapabilities({privateConnected:aiConsole.isLive(),privateModelVerified:aiConsole.isVerified(),browserModelVerified:aiConsole.browserModel.isVerified()});
 const labels={private:"Private Python workspace", "browser-local":"Browser-local model","static":"Public static workspace"};
 const rows=report.capabilities.map(item=>
  '<div class="mini-row"><div><strong>'+escapeHTML(item.label)+'</strong><small>'+escapeHTML(item.reason)+'</small></div>'+
  pill(item.available?"Available":item.id==="cloud_batch"?"Requires fork setup":"Unavailable",item.available?"green":"neutral")+'</div>').join("");
 return heading("Deployment & capabilities","Inspect execution boundaries, connect a provider, and deploy an independent fork without exposing secrets.",
   button("Configure model","nav","settings","primary")+
   button("Self-hosting guide","url",ownerRepo()+"/blob/main/docs/SELF_HOSTING.md"))+
  '<div class="kpis">'+kpi("Execution mode",labels[report.mode],"Determined from this browser session")+
  kpi("Available capabilities",report.available.length,"Verified or supported locally")+
  kpi("Private runtime",aiConsole.isLive()?"Connected":"Not connected","Single owner, loopback only")+
  kpi("Browser model",aiConsole.browserModel.isVerified()?"Verified":"Not tested","Direct inference only")+'</div>'+
  statCard("Runtime capability contract",'<div class="mini-list">'+rows+'</div>')+
  statCard("Choose an execution boundary",'<div class="mini-list">'+
   '<div class="mini-row"><div><strong>GitHub Pages</strong><small>Read-only committed research data, local drafts, and offline deterministic assessment.</small></div>'+button("Open workspace","nav","dashboard")+'</div>'+
   '<div class="mini-row"><div><strong>Pages + local model</strong><small>Browser-initiated /v1 inference. Requires an origin-approved model server and browser network permission.</small></div>'+button("Configure","nav","settings")+'</div>'+
   '<div class="mini-row"><div><strong>GitHub Actions</strong><small>Opt-in, asynchronous cloud validation. Model keys remain in GitHub environment secrets.</small></div>'+button("Workflow","url",ownerRepo()+"/actions/workflows/hosted-ai-advisories.yml")+'</div>'+
   '<div class="mini-row"><div><strong>Private Python or Linux Docker</strong><small>SQLite, model routes, agents and scheduled workflows; service remains bound to loopback.</small></div>'+button("Instructions","url",ownerRepo()+"/blob/main/docs/DOCKER_LOCAL.md")+'</div>'+
   '<div class="mini-row"><div><strong>Authenticated cloud edition</strong><small>Not implemented; identity, per-user authorization, hardened API and durable workers are mandatory before exposure.</small></div></div>')+
  '<div class="info">Capabilities are evaluated for this session only. A passing code-quality check does not prove that a model endpoint is running or that university evidence is current.</div>';
}
function documentsView(){
 const inventory=portfolioDocumentInventory(records());
 const labels=state.data.documents||{};
 const rows=inventory.items.map(item=>{
  const related=item.applications.filter(r=>r.active);
  const details=related.slice(0,25).map(record=>
   '<div class="mini-row"><div>'+button(record.name,"record",record.id)+
   '<small>'+escapeHTML(record.status)+' · '+escapeHTML(({
    ready:"Reported ready",unknown:"Readiness unknown",in_progress:"In progress",
    not_started:"Not started",not_applicable:"Not applicable"
   })[record.state]||"Unknown")+(record.verified_requirements?" · Source requirement recorded":" · Requirement evidence unconfirmed")+
   '</small></div><small>'+escapeHTML(record.deadline||"No recorded deadline")+'</small></div>').join("");
  return '<details class="os-panel document-group"><summary><strong>'+escapeHTML(labels[item.id]||item.id)+'</strong>'+
   '<span>'+item.active+' active · '+item.unknown_or_unstarted+' unresolved · '+item.reported_ready+' reported ready</span></summary>'+
   '<p class="subtle">Shared requirements are aggregated across application records. A marked-ready file is not verified against a current portal specification.</p>'+
   '<div class="mini-list">'+details+(related.length>25?'<p class="subtle">Showing 25 of '+related.length+' records. Open Applications for the complete inventory.</p>':"")+'</div></details>';
 }).join("");
 const stats=inventory.summary;
 return heading("Document inventory","Consolidated dossier demand, declared requirements and readiness across your recorded applications.",
  button("Applications","nav","applications","primary")+button("Readiness","nav","readiness"))+
  '<div class="kpis">'+kpi("Active applications",stats.active,"Tracked records with active states")+
  kpi("Requirements unconfirmed",stats.unconfirmed_requirements,"No document list recorded")+
  kpi("Unknown readiness",stats.unknown,"Recorded requirements without a status")+
  kpi("Not started",stats.not_started,"Explicitly marked incomplete")+
  kpi("Reported ready",stats.ready,"Applicant record; not portal proof")+'</div>'+
  '<div class="info">Document titles and readiness reflect recorded evidence, not uploaded files. No document contents or private credentials are stored on GitHub Pages.</div>'+
  (rows||'<div class="empty">No recorded document requirements. Add a reviewed opportunity or inspect the official portal before assuming documents are unnecessary.</div>');
}
function discoveryView(){
 const report=candidateQueue(records(),TODAY(),{stage:discoveryFilter,query:discoveryQuery});
 const stages=[["all","All candidates"],["reviewed","Source reviewed"],["review","Verification needed"],["staged","Staged updates"],["closed","Recorded date passed"]];
 const filters=stages.map(([id,label])=>button(label+" ("+(id==="all"?report.counts.total:report.counts[id])+")","discovery-filter",id,discoveryFilter===id?"primary":"secondary")).join("");
 const cards=report.items.map(({record:r,stage,action,reasons})=>
  '<div class="mini-row discovery-row"><div><div>'+rowButton(r)+' '+pill(({reviewed:"Source reviewed",review:"Review needed",closed:"Recorded date passed",staged:"Staged"})[stage]||"Unverified")+'</div>'+
  '<small>'+escapeHTML(r.institution||"Institution unknown")+' · '+escapeHTML(r.country||"Country unknown")+' · '+escapeHTML(r.topic||"Research focus not recorded")+'</small>'+
  '<small>'+escapeHTML(action)+(reasons.length?" · "+escapeHTML(reasons.slice(0,2).join("; ")):"")+'</small>'+
  '<div class="linkset">'+link(r.source_url,"Primary source")+link(r.apply_url,"Official application route")+'</div></div>'+
  '<div class="discovery-actions"><div>'+escapeHTML(r.deadline||"Date unknown")+'</div>'+
  button("Inspect","record",r.id)+(stage==="reviewed"?button("Stage promotion","promote",r.id):"")+'</div></div>'
 ).join("");
 return heading("Discovery","Evidence-first research candidate triage. Recorded verification is not a guarantee of open admissions.",
   button("Add opportunity","new-local","","primary")+button("Tracked applications","nav","applications"))+
  '<div class="kpis">'+kpi("Candidates",report.counts.total,"Research leads; not applications")+kpi("Source reviewed",report.counts.reviewed,"Explicitly recorded review")+kpi("Needs verification",report.counts.review,"Primary proof still needed")+kpi("Staged changes",report.counts.staged,"Require confirmation")+kpi("Recorded date passed",report.counts.closed,"Check current call")+'</div>'+
  '<div class="discovery-controls"><div class="buttons" role="group" aria-label="Discovery status filters">'+filters+'</div>'+
  '<label class="field"><span>Search candidate evidence</span><input id="discoveryQuery" class="input" type="search" maxlength="200" value="'+escapeHTML(discoveryQuery)+'" placeholder="Institution, programme, topic, country"></label></div>'+
  statCard("Candidate review queue",cards||'<div class="empty">No matching research candidates. Review your source records or adjust filters.</div>')+
  '<div class="info">Candidate promotion is staged as a local draft. Official source review, deadline validation and a separate GitHub confirmation are required before treating it as tracked.</div>';
}
function readiness(){
 const report=portfolioReadiness(records(),TODAY());
 return renderReadinessView({report,filter:readinessFilter,heading,kpi,rowButton,button,pill,dateRisk,stamp,escape:escapeHTML});
}
function contacts(){const all=records().filter(r=>r.faculty!=="Not recorded"||r.contact_status!=="unrecorded"||r.followup);const list=sortList(filters(all));return heading("Faculty contacts","Contacts and follow-up dates, recorded explicitly.",button("Export contacts CSV","export","contacts"))+
statCard("Faculty and supervisor pipeline",toolbar(list)+'<div class="tablewrap"><table class="table"><thead><tr><th>Opportunity</th><th>Faculty / contact</th><th>Outreach status</th><th>Next follow-up</th><th>Action</th></tr></thead><tbody>'+list.map(r=>'<tr><td>'+rowButton(r)+'</td><td>'+escapeHTML(r.faculty)+'</td><td>'+pill(r.contact_status==="unrecorded"?"Not recorded":r.contact_status)+'</td><td>'+escapeHTML(stamp(r.followup))+(r.followup?" "+dateRisk(days(r.followup)):"")+'</td><td>'+button("Update","record",r.id)+'</td></tr>').join("")+'</tbody></table></div>')}
function ledgerView(){
 const all=Array.isArray(state.data.task_ledger)?state.data.task_ledger:[];
 const q=ledgerQuery.trim().toLocaleLowerCase();
 const types=[...new Set(all.map(t=>t.type).filter(Boolean))].sort();
 const selected=all.filter(t=>(ledgerType==="all"||t.type===ledgerType)&&(!q||[t.id,t.application_id,t.name,t.action,t.sheet,t.state,t.type].join(" ").toLocaleLowerCase().includes(q)));
 const pageSize=60,pageCount=Math.max(1,Math.ceil(selected.length/pageSize)),page=Math.min(ledgerPage,pageCount);
 const current=selected.slice((page-1)*pageSize,page*pageSize);
 const opt=(v,label)=>'<option value="'+escapeHTML(v)+'"'+(ledgerType===v?' selected':'')+'>'+escapeHTML(label)+'</option>';
 return heading("Full task ledger","All normalized task records from the original source workbook, including dated historical events. Task states are source claims, not proof of outstanding or completed work.",button("Export full ledger","export-ledger","","primary")+button("Priority actions","nav","actions"))+
 '<div class="kpis">'+kpi("All task records",all.length,"Source execution-plan records")+kpi("Matching tasks",selected.length,"Current search and type")+kpi("Source categories",types.length,"Different task types")+kpi("Historical dates",selected.filter(t=>t.due&&days(t.due)<0).length,"Not automatically incomplete")+'</div>'+
 '<section class="panel"><div class="panel-header"><h2>Workbook task register</h2><span class="subtle">Page '+page+' of '+pageCount+'</span></div>'+
 '<div class="toolbar"><input id="ledgerQuery" class="input" type="search" aria-label="Search all workbook tasks" placeholder="Search task, application, worksheet or action…" value="'+escapeHTML(ledgerQuery)+'">'+
 '<select id="ledgerType" class="select" aria-label="Filter workbook task type">'+opt("all","All task categories")+types.map(t=>opt(t,t.replaceAll("_"," "))).join("")+'</select>'+
 '<span class="count" aria-live="polite">'+selected.length+' of '+all.length+' entries</span></div>'+
 (current.length?'<div class="tablewrap"><table class="table"><thead><tr><th>Task</th><th>Date</th><th>Source type</th><th>Source row</th><th>State / Evidence</th></tr></thead><tbody>'+
 current.map(t=>'<tr><td><strong>'+escapeHTML(t.name||"Untitled task")+'</strong><small>'+escapeHTML(t.action||"No task instruction recorded")+'</small><small>'+escapeHTML(t.id)+'</small></td>'+
 '<td>'+escapeHTML(stamp(t.due))+(t.due?' '+dateRisk(days(t.due)):'')+'</td>'+
 '<td>'+escapeHTML(t.type.replaceAll("_"," "))+'</td><td>'+escapeHTML(t.sheet||"Unknown sheet")+(t.row?' · '+escapeHTML(t.row):"")+'</td>'+
 '<td>'+pill(t.state||"unconfirmed")+'<small>'+escapeHTML(t.application_id||"Cross-route task")+'</small>'+
 (getRecord(t.application_id)?button("Application","record",t.application_id):"")+link(t.source_url,"Official source")+'</td></tr>').join("")+
 '</tbody></table></div>':'<p class="empty">No tasks match this search and category. Clear the filter or review the original workbook.</p>')+
 '<div class="buttons" style="justify-content:flex-end;padding:14px 16px">'+button("Previous 60","ledger-page",String(Math.max(1,page-1)))+button("Next 60","ledger-page",String(Math.min(pageCount,page+1)))+'</div></section>'+
 '<p class="footnote">The original action list, timeline, proposed application dates and cross-route tasks are different records. Dates in the past are not necessarily unfinished. This view does not write completion state to the workbook.</p>';
}
function actions(){const rs=records().filter(r=>r.record_type==="tracked").filter(open).sort((a,b)=>priority(b)-priority(a));const tasks=(state.data.tasks||[]).filter(t=>!t.application_id||!getRecord(t.application_id)||open(getRecord(t.application_id)));return heading("Next actions","Your deadline-first application tasks and the original workbook steps.",button("Download calendar (.ics)","export","ics","primary")+button("Readiness plan","nav","readiness")+button("Full task ledger","nav","ledger"))+
'<div class="kpis">'+kpi("Due today",rs.filter(r=>days(r.deadline)===0).length,"Final or priority dates")+kpi("Within 72h",rs.filter(r=>days(r.deadline)!==null&&days(r.deadline)>=0&&days(r.deadline)<=3).length,"Check portal cutoff")+kpi("Follow-ups overdue",rs.filter(r=>r.followup&&days(r.followup)<0).length,"Manual date entries")+kpi("Plan steps surfaced",tasks.length,"Original tracker snapshot")+kpi("Explicit document gaps",rs.filter(r=>Object.values(r.document_states||{}).includes("not_started")).length,"Never infer from unknown")+'</div>'+
statCard("Prioritized opportunities",'<div class="mini-list">'+rs.map((r,i)=>'<div class="mini-row"><div><span class="subtle">#'+(i+1)+' &nbsp;</span>'+rowButton(r)+'<small>'+escapeHTML(r.status==="submitted"?"Follow-up after submission: "+(r.next_step||"Check receipt and referee states"):(r.next_step||"Confirm next action"))+'</small></div><div>'+dateRisk(days(r.status==="submitted"?r.followup:r.deadline))+'</div></div>').join("")+'</div>')+
statCard("Existing workbook execution steps",'<p class="subtle">Task completion should be confirmed through the existing authenticated GitHub issue workflow; a listed task is not automatically unfinished.</p>'+(tasks.length?'<div class="tablewrap"><table class="table"><thead><tr><th>Action</th><th>Due</th><th>Source status</th><th>Related application</th><th>Control</th></tr></thead><tbody>'+tasks.map(t=>'<tr><td>'+escapeHTML(t.action||t.name)+'</td><td>'+escapeHTML(stamp(t.due))+'</td><td>'+pill(t.state)+'</td><td>'+escapeHTML(t.application_id||"Shared")+'</td><td>'+button("Copy /done","task",t.id)+'</td></tr>').join("")+'</tbody></table></div>':'<div class="empty">No planned steps in the displayed horizon.</div>'))}
function updates(){
 const committed=records().filter(r=>r.updated_at&&!r.local_only);
 const edited=Object.keys(state.drafts).filter(id=>state.data.records.some(r=>r.id===id));
 const statuses=Object.fromEntries(edited.map(id=>[id,draftState(state.drafts[id],state.data.records.find(r=>r.id===id))]));
 const conflicting=edited.filter(id=>["conflict","needs-review"].includes(statuses[id]));
 const pending=edited.filter(id=>statuses[id]==="pending");
 return heading("Changes","Local changes, synchronization status and research leads.",button("Export drafts","export","drafts","primary")+button("Git history","url",ownerRepo()+"/commits/main"))+
 '<div class="kpis">'+kpi("Device-only opportunities",state.localRecords.length,"Private to this browser")+kpi("Local drafts",edited.length,"Only in this browser")+kpi("Awaiting confirmation",pending.length,"GitHub issue required")+kpi("Needs reconciliation",conflicting.length,"Source version changed or unknown")+kpi("Owner updates",committed.length,"Committed overrides")+kpi("Evidence snapshot",stamp(state.data.as_of),"Source projection")+'</div>'+
 statCard("Local change register",edited.length?'<div class="mini-list">'+edited.map(id=>{
  const r=getRecord(id),status=statuses[id],message={"draft":"Local draft","pending":"Awaiting GitHub confirmation","conflict":"Conflict — source changed","needs-review":"Review source version","committed":"Matches committed source","missing-source":"Source unavailable"}[status]||"Draft";
  return '<div class="mini-row"><div>'+rowButton(r)+'<small>'+escapeHTML(message)+' · '+escapeHTML(id)+'</small></div><div class="buttons">'+
  (status==="conflict"||status==="needs-review"?button("Reconcile","reconcile",id,"primary"):status==="committed"?button("Review source","record",id):button("Copy update","command",id,"primary"))+
  button("Discard","discard",id,"danger")+'</div></div>';
 }).join("")+'</div>':'<div class="empty">No local changes. Application edits are saved on this device until confirmed through GitHub.</div>')+
 statCard("Discovery leads",'<p class="subtle">These leads have not been promoted to applications. Verify the primary listing before taking action.</p><div class="tablewrap"><table class="table"><thead><tr><th>Lead</th><th>Provider</th><th>Deadline</th><th>Evidence</th></tr></thead><tbody>'+state.data.leads.map(r=>'<tr><td><strong>'+escapeHTML(r.name)+'</strong><small>'+escapeHTML(r.id)+'</small></td><td>'+escapeHTML(r.provider)+'<small>'+link(r.source_url,"Listing")+'</small></td><td>'+escapeHTML(stamp(r.deadline))+'</td><td>'+pill(r.evidence_status,"warning")+'</td></tr>').join("")+'</tbody></table></div>');
}
function calendarView(){
  const today=TODAY(),month=state.calendarMonth||today.slice(0,7);
  const parts=month.split("-").map(Number);
  const year=parts[0],monthNumber=parts[1],first=new Date(Date.UTC(year,monthNumber-1,1));
  const last=new Date(Date.UTC(year,monthNumber,0)).getUTCDate();
  const offset=(first.getUTCDay()+6)%7;
  const from=month+"-01";
  const deadlineRows=records().filter(r=>r.record_type==="tracked"&&r.deadline&&r.deadline.slice(0,7)===month);
  const byDate=new Map();
  deadlineRows.forEach(r=>{const items=byDate.get(r.deadline)||[];items.push(r);byDate.set(r.deadline,items)});
  const selected=state.selectedDate&&state.selectedDate.slice(0,7)===month?state.selectedDate:(byDate.has(today)?today:Array.from(byDate.keys()).sort()[0]||from);
  const selectedItems=(byDate.get(selected)||[]).slice().sort((a,b)=>priority(b)-priority(a));
  const header=new Intl.DateTimeFormat("en-US",{month:"long",year:"numeric",timeZone:"UTC"}).format(first);
  let cells="";
  for(let i=0;i<offset;i++)cells+='<div class="cal-empty" aria-hidden="true"></div>';
  for(let d=1;d<=last;d++){
    const day=month+"-"+String(d).padStart(2,"0"),items=byDate.get(day)||[],urgent=items.some(r=>!isClosed(r)&&days(day)>=0&&days(day)<=3);
    const mark=day===today?" today":"",chosen=day===selected?" selected":"";
    cells+='<button class="cal-day'+mark+chosen+'" type="button" data-action="cal-day" data-value="'+day+'"><span class="cal-number">'+d+'</span><span class="sr-only">Full date: '+escapeHTML(stamp(day))+'</span>'+(items.length?'<span class="cal-count '+(urgent?"cal-urgent":"")+'">'+items.length+' due</span>':'')+items.slice(0,2).map(r=>'<span class="cal-entry">'+escapeHTML(r.name.slice(0,32))+'</span>').join("")+(items.length>2?'<span class="cal-more">+'+(items.length-2)+' more</span>':"")+'</button>';
  }
  const total=Array.from(byDate.values()).reduce((n,arr)=>n+arr.length,0);
  const ordered=Array.from(byDate.keys()).sort();
  return heading("Application calendar","Month-by-month deadline density, collision detection and dated action planning. Dates come from the committed tracker, not live portal checks.",button("Export iCalendar","export","ics","primary"))+
    '<div class="kpis">'+kpi("Dates this month",total,"Recorded application events")+kpi("Distinct due dates",byDate.size,"Separate calendar dates")+kpi("Peak-day load",Math.max(0,...Array.from(byDate.values()).map(x=>x.length)),"Application collisions")+kpi("Unverified deadlines",deadlineRows.filter(r=>r.recheck_required).length,"Evidence review needed")+kpi("Past dates",deadlineRows.filter(r=>days(r.deadline)<0).length,"Not automatically submitted")+'</div>'+
    '<section class="panel"><div class="panel-header"><h2>'+escapeHTML(header)+'</h2><div class="buttons">'+button("← Previous","cal-prev")+button("Today","cal-today")+button("Next →","cal-next")+'</div></div>'+
    '<div class="calendar-scroller"><div class="cal-grid"><div class="cal-weekday">Mon</div><div class="cal-weekday">Tue</div><div class="cal-weekday">Wed</div><div class="cal-weekday">Thu</div><div class="cal-weekday">Fri</div><div class="cal-weekday">Sat</div><div class="cal-weekday">Sun</div>'+cells+'</div></div></section>'+
    '<div class="two-col">'+statCard("Selected day · "+stamp(selected),selectedItems.length?'<div class="mini-list">'+selectedItems.map(r=>'<div class="mini-row"><div>'+rowButton(r)+'<small>'+escapeHTML(r.next_step||"Next action unrecorded")+'</small><small>'+escapeHTML(cutoffDescription(r))+'</small></div>'+verificationPill(r)+'</div>').join("")+'</div>':'<div class="empty">No application date recorded for this day.</div>')+
    statCard("Date collisions & upcoming distribution",ordered.length?'<div class="mini-list">'+ordered.map(day=>'<div class="mini-row"><button data-action="cal-day" data-value="'+escapeHTML(day)+'">'+escapeHTML(stamp(day))+'</button><strong>'+byDate.get(day).length+' recorded</strong></div>').join("")+'</div>':'<div class="empty">No dated application records for this month.</div>')+'</div>'+
    '<p class="footnote">The site shows whole calendar dates. Exact submission cutoffs and local time zones remain available in the application detail where recorded; unverified cutoffs must be confirmed on the official portal.</p>';
}
function pipeline(){
  const lanes=[["unconfirmed","Unconfirmed"],["shortlisted","Shortlisted"],["preparing","Preparing"],["submitted","Submitted"],["interview","Interview"],["offer","Offer"],["blocked","Blocked"]];
  const rows=records().filter(r=>r.record_type==="tracked"),counts=Object.fromEntries(lanes.map(([id])=>[id,rows.filter(r=>r.status===id).length]));
  const laneMarkup=lanes.map(([id,label])=>{
    const items=rows.filter(r=>r.status===id).sort((a,b)=>priority(b)-priority(a));
    return '<div class="kanban-lane" data-lane="'+id+'"><div class="kanban-head"><strong>'+escapeHTML(label)+'</strong>'+pill(items.length,'neutral')+'</div><div class="kanban-body">'+items.slice(0,11).map(r=>
      '<div class="kanban-card" data-drag-id="'+escapeHTML(r.id)+'" draggable="true"><div class="eyebrow">'+escapeHTML(r.id)+'</div>'+rowButton(r)+'<div class="kanban-meta">'+dateRisk(days(r.deadline))+' '+verificationPill(r)+'</div><small>'+escapeHTML(r.next_step||"Next action unrecorded").slice(0,105)+'</small><label class="kanban-stage">Move to <select data-stage-id="'+escapeHTML(r.id)+'" aria-label="Move '+escapeHTML(r.name)+' to stage">'+lanes.map(([value,name])=>'<option value="'+value+'"'+(r.status===value?' selected':'')+'>'+name+'</option>').join("")+'</select></label></div>'
    ).join("")+(items.length>11?button("View all "+items.length,"pipeline-filter",id):"")+
    (items.length===0?'<p class="subtle">No records in this state</p>':"")+'</div></div>';
  }).join("");
  return heading("Application pipeline","A status-driven board for owner-confirmed application progress. Use the stage selector or drag a card. Changes remain local until confirmed through GitHub.",button("Export application statuses","export","csv","primary")+button("Review local changes","nav","updates"))+
    '<div class="kpis">'+kpi("Shortlisted",counts.shortlisted,"Explicit owner selection")+kpi("In preparation",counts.preparing,"Active document work")+kpi("Submitted",counts.submitted,"Confirmation required")+kpi("In interview",counts.interview,"Recorded stage")+kpi("Offers",counts.offer,"Recorded stage")+'</div>'+
    '<div class="info">Cards can be moved with the labelled stage selector (keyboard accessible) or drag-and-drop. This creates a local draft; it never submits an application or updates GitHub by itself.</div>'+
    '<div class="kanban-board" aria-label="Application status board">'+laneMarkup+'</div>'+
    '<p class="footnote">Other statuses (withdrawn, rejected, archived) remain available in the application registry and Expired / blocked view. A submission is not counted as owner-confirmed until committed.</p>';
}
function compare(){const selected=state.compare.map(getRecord).filter(Boolean);return heading("Compare opportunities","Compare deadline, funding, evidence and requirements side by side.",button("Choose applications","nav","applications","primary")+button("Clear selection","clear-compare"))+
'<div class="info">'+selected.length+' of 4 applications selected. Use checkboxes in Applications. Funding and eligibility are recorded claims, not verified personal eligibility decisions.</div>'+
(selected.length?'<div class="compare-grid">'+selected.map(r=>'<div class="compare-card"><h3>'+escapeHTML(r.name)+'</h3><label>Deadline</label><p>'+escapeHTML(stamp(r.deadline))+' '+dateRisk(days(r.deadline))+'</p><label>Evidence</label><p>'+verificationPill(r)+'</p><label>Status</label><p>'+escapeHTML(statusLabel(r.status))+'</p><label>Funding</label><p>'+escapeHTML(r.funding||"Unverified")+'</p><label>Eligibility</label><p>'+escapeHTML(r.eligibility||"Unverified")+'</p><label>Fit rationale</label><p>'+escapeHTML(r.fit||"Not recorded")+'</p><label>Document proof</label><p>'+Object.values(r.document_states||{}).filter(x=>x==="unknown").length+' unknown, '+Object.values(r.document_states||{}).filter(x=>x==="not_started").length+' explicitly not started</p><label>Next step</label><p>'+escapeHTML(r.next_step||"Unknown")+'</p><p>'+link(r.source_url,"Source")+'</p>'+button("Open details","record",r.id)+'</div>').join("")+'</div>':'<div class="empty">Select two to four applications from the Applications table to compare them.</div>')}
function hostedAIPanel(){
 const advisory = state.data?.hosted_ai;
 const utcToday = new Date().toISOString().slice(0,10);
 const selected = hostedAdvisories(state.data,utcToday).slice(0,24);
 const status = hostedStatus(advisory,utcToday);
 const path = ownerRepo()+"/actions/workflows/hosted-ai-advisories.yml";
 const entries = selected.length?'<div class="mini-list">'+selected.map(item=>{
  const r=getRecord(item.id);
  if(!r)return"";
  return '<div class="mini-row"><div>'+button(escapeHTML(r.name),"record",r.id)+
   '<small>'+escapeHTML(item.category.replace(/_/g," "))+' · '+escapeHTML(item.priority)+' priority · unverified AI proposal</small></div></div>';
 }).join("")+'</div>':'<p class="subtle">'+escapeHTML(status)+'</p>';
 return statCard("Hosted AI verification triage",'<p class="muted">An opt-in GitHub Actions job can call a model using repository or environment secrets. These are provisional proof-gap priorities, not source verification, submission confirmation, or admission probabilities.</p>'+entries+
 '<p>'+link(path,"Configure or run workflow")+'</p>');
}
function assurancePanel(){return renderAssurance({snapshot:state.data,records:records(),today:TODAY(),filter:selectedAuditCategory,limit:assuranceLimit,escape:escapeHTML,button,link})}
function coveragePanel(){return renderCoverage({snapshot:state.data,escape:escapeHTML,link,repository:ownerRepo()})}
function review(){const rs=records().filter(r=>r.verification!=="source_verified"&&r.verification!=="owner_verified"||r.duplicate_submission_advisory||r.blockers||r.document_states&&Object.values(r.document_states).includes("not_started"));const suspect=state.data.duplicates||[];return heading("Verification","Unconfirmed sources, duplicate pathways and document risk.",button("Open source monitoring","url",state.data.source_links.source_monitor,"primary"))+
assurancePanel()+
hostedAIPanel()+
'<div class="info">Duplicate detection is an advisory similarity screen, not a determination that two calls are the same. Some programmes require two distinct submissions; others forbid two independent applications.</div>'+
'<div class="kpis">'+kpi("Needs evidence review",records().filter(r=>r.recheck_required).length,"No automatic promotion")+kpi("Potential title matches",suspect.length,"Requires human assessment")+kpi("Multi-route cautions",records().filter(r=>r.duplicate_submission_advisory).length,"Manual interpretation")+kpi("Document gaps",records().filter(r=>Object.values(r.document_states||{}).includes("not_started")).length,"Explicitly confirmed")+kpi("Unverified dates",records().filter(r=>!r.deadline).length,"Date is unknown")+'</div>'+
statCard("Programme and source duplicate advisories",suspect.length?'<div class="mini-list">'+suspect.map(d=>'<div class="mini-row"><div>'+d.ids.map(id=>'<button data-action="record" data-value="'+escapeHTML(id)+'">'+escapeHTML(id)+'</button>').join(' / ')+'<small>'+escapeHTML(d.reason)+' · Similarity '+escapeHTML(d.similarity)+' · NOT confirmed</small></div></div>').join("")+'</div>':'<div class="empty">No high-similarity programme titles detected. This does not rule out duplicate routes.</div>')+
statCard("Verification and submission risks",table(rs.slice().sort((a,b)=>priority(b)-priority(a))))}
function archive(){const all=records().filter(r=>r.status==="blocked"||days(r.deadline)!==null&&days(r.deadline)<0||["archived","withdrawn","rejected"].includes(r.status));return heading("Expired & blocked","Deadlines in the past, blocked routes and historical exclusions.",button("View exclusions in GitHub","url",ownerRepo()+"/blob/main/data/exclusion_memory.json"))+
'<div class="kpis">'+kpi("Expired",all.filter(r=>days(r.deadline)!==null&&days(r.deadline)<0).length,"Deadline in the past")+kpi("Owner blocked",all.filter(r=>r.status==="blocked").length,"Explicit status")+kpi("Archived / withdrawn",all.filter(r=>["archived","withdrawn"].includes(r.status)).length,"Explicit status")+kpi("Historical exclusions",state.data.archive.length,"Workbook-derived snapshot")+kpi("Undated opportunities",records().filter(r=>!r.deadline).length,"Not automatically expired")+'</div>'+
statCard("Closed or blocked opportunities",all.length?table(sortList(filters(all))):'<div class="empty">No records in this category.</div>')+
statCard("Historical exclusion memory",'<p class="subtle">This is a concise projection only; inspect source workbook for original reasons and dates. Prior-cycle exclusions cannot automatically disqualify a new call.</p><div class="tablewrap"><table class="table"><thead><tr><th>Source ID</th><th>Recorded route</th><th>Historical classification</th></tr></thead><tbody>'+state.data.archive.map(x=>'<tr><td>'+escapeHTML(x.id)+'</td><td>'+escapeHTML(x.name)+'</td><td>'+pill(x.status,"neutral")+'</td></tr>').join("")+'</tbody></table></div>')}
function sources(){return heading("Source records","Source coverage, verification and data lineage.",button("Run discovery workflow","url",state.data.source_links.source_monitor,"primary")+button("Original workbook","url",state.data.source_links.workbook))+
coveragePanel()+
'<div class="info">Discovery pipeline status: '+escapeHTML(state.data.meta.discovery_snapshot||"Unknown")+'. This view is a committed snapshot, not a fresh external web search. Providers with 403, missing credentials or parsing failures cannot establish search completeness.</div>'+
'<div class="source-grid">'+state.data.providers.map(p=>'<article><strong>'+escapeHTML(p.name)+'</strong>'+pill(p.health,p.health==="ok"?"green":"warning")+'<small>'+escapeHTML(p.observed)+' observed · '+escapeHTML(p.new_unique)+' new unique leads</small></article>').join("")+'</div><div style="height:18px"></div>'+
statCard("Evidence and workflow entry points",'<div class="mini-list">'+[
["Application source records",state.data.source_links.opportunities],
["Original Excel tracker",state.data.source_links.workbook],
["Run multi-source discovery",state.data.source_links.source_monitor],
["Owner action center",state.data.source_links.control_issue],
["Recent repository changes",ownerRepo()+"/commits/main"],
["Original interactive evidence graph",new URL("./evidencegraph/",location.href).href],
["Structured new opportunity",ownerRepo()+"/issues/new?template=02-opportunity-lead.yml"],
["Correct disputed evidence",ownerRepo()+"/issues/new?template=01-source-correction.yml"]
].map(([name,url])=>'<div class="mini-row"><span>'+escapeHTML(name)+'</span>'+link(url,"Open")+'</div>').join("")+'</div>')+
statCard("Contact & application control model",'<p class="muted">New owner decisions are submitted as authenticated GitHub issue commands. Local draft values are provisional until the issue-control workflow commits an updated versioned record. The original workbook, data pipeline, reminders and source-monitor workflow remain intact.</p><p class="muted">The public-site projection deliberately excludes mailbox permalinks, email addresses, correspondence bodies and full exclusion rationales. GitHub Pages is not an access-controlled datastore.</p>')}
const DOC_LABELS={unknown:"Unknown",ready:"Ready",in_progress:"In progress",not_started:"Not started",not_applicable:"Not required"};
function sourceRecord(id){return state.data?.records.find(r=>r.id===id)||state.localRecords.find(r=>r.id===id)}
function withDraftBase(id){const saved=state.drafts[id]||{};return {...saved,base_updated_at:typeof saved.base_updated_at==="string"?saved.base_updated_at:sourceRecord(id)?.updated_at||""}}
function stageStatus(id,status){
 const r=getRecord(id);
 if(!r || !["unconfirmed","shortlisted","preparing","submitted","interview","offer","blocked"].includes(status))return;
 if(r.record_type==="candidate"){notify("Verify and promote this candidate before changing its application stage.");return}
 if(status==="submitted"&& !confirm("Confirm this application was submitted through the official portal? This change is only a local draft."))return;
 if(r.local_only){saveLocalRecord({...r,status,updated_at:new Date().toISOString()});render();notify("Application stage updated on this device.");return}
 state.drafts[id]={...withDraftBase(id),status,_sync_status:"draft"};
 saveStore(STORE,state.drafts);render();notify("Status saved locally. Confirm it on GitHub from Changes.");
}
function reconcileDraft(id){
 const source=sourceRecord(id),draft=state.drafts[id];
 if(!source||!draft)return;
 const changed=[["Status",source.status,draft.status],["Verification",source.verification,draft.verification],["Next step",source.next_step,draft.next_step],["Priority",source.priority||"normal",draft.priority||"normal"]]
 .filter(([name,oldValue,newValue])=>newValue!==undefined&&oldValue!==newValue);
 const compare=changed.length?changed.map(([name,oldValue,newValue])=>'<div class="reconcile-line"><strong>'+escapeHTML(name)+'</strong><div><span>Committed: '+escapeHTML(oldValue||"Not recorded")+'</span><span>Draft: '+escapeHTML(newValue||"Not recorded")+'</span></div></div>').join(""):'<p class="muted">No differences in the main status fields. Review documents separately before keeping a draft.</p>';
 state.selected=id;
 openModal("<h2>Resolve source conflict</h2>",'<p class="muted">The source changed after this draft was created or the original version is unknown. Review these differences before rebasing. This does not commit any change.</p>'+compare+
 '<p class="subtle">Last committed version: '+escapeHTML(source.updated_at||"No owner update")+'</p>'+
 '<div class="buttons">'+button("Keep draft against current source","confirm-rebase",id,"primary")+button("Discard draft","discard",id)+button("Cancel","close")+'</div>');
}
function commitRebase(id){
 const source=sourceRecord(id),draft=state.drafts[id];
 if(!source||!draft)return;
 state.drafts[id]={...draft,base_updated_at:source.updated_at||"",_sync_status:"draft"};
 saveStore(STORE,state.drafts);closeModal();render();notify("Draft rebased locally. Review and confirm the GitHub update.");
}
function detail(r){if(!r)return;state.selected=r.id;const docs=Object.entries(r.document_states||{});const opts=(values,current)=>values.map(v=>'<option value="'+escapeHTML(v)+'"'+(current===v?' selected':'')+'>'+escapeHTML(DOC_LABELS[v]||statusLabel(v))+'</option>').join('');
const sync=r.local_only?"device-only":draftState(state.drafts[r.id],sourceRecord(r.id)),readiness=documentReadiness(r),execution=assessApplication(r,TODAY());
const fields='<div class="field"><label for="editPriority">My priority</label><select id="editPriority" class="select">'+opts(["normal","high","low"],r.priority||"normal")+'</select><small class="subtle">Adjusts priority in the action queue.</small></div><div class="field"><label for="editStatus">Application status (confirm any real portal submission)</label><select id="editStatus" class="select">'+opts(["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"],r.status)+'</select><small class="subtle">Never mark submitted without actual portal confirmation.</small></div>'+
'<div class="field"><label for="editVerification">Verification status</label><select id="editVerification" class="select">'+opts(["unverified","needs_review","source_verified","owner_verified"],r.verification)+'</select><small class="subtle">Choose verified only after inspecting supporting primary evidence.</small></div>'+
'<div class="field"><label for="editFollowup">Next faculty follow-up</label><input id="editFollowup" type="date" class="input" value="'+escapeHTML(r.followup||"")+'"></div>'+
'<div class="field"><label for="editContact">Contact / outreach stage</label><select id="editContact" class="select">'+opts(["unrecorded","to_contact","contacted","awaiting_reply","followup_due","replied","declined","completed"],r.contact_status)+'</select></div>'+
'<div class="field"><label for="editStep">Next action</label><textarea id="editStep" class="input" maxlength="650">'+escapeHTML(r.next_step||"")+'</textarea></div>'+
(r.local_only?'<div class="field"><label for="editCutoffTime">Recorded closing time (unverified)</label><input id="editCutoffTime" class="input" type="time" value="'+escapeHTML(r.deadline_time||"")+'"></div><div class="field"><label for="editCutoffZone">Institution IANA timezone</label><input id="editCutoffZone" class="input" maxlength="80" value="'+escapeHTML(r.deadline_timezone||"")+'" placeholder="Europe/London"><small class="subtle">Both fields are required together. Local edits never attest to cutoff verification.</small></div>':'')+
 '<div class="field"><label for="editNotes">Local notes (this device)</label><textarea id="editNotes" class="input" maxlength="750">'+escapeHTML(r.notes||"")+'</textarea></div>'+
'<div class="field"><label for="editReceipt">Receipt link (local only, HTTPS)</label><input id="editReceipt" type="url" class="input" value="'+escapeHTML(r.receipt||r.submission_receipt||"")+'" placeholder="https://..."><p class="form-error" id="receiptError" role="alert"></p><small class="subtle">Private browser-local URL; never sent to public GitHub.</small></div>'+
'<h3>Document readiness</h3><p class="subtle">'+escapeHTML(readiness.label)+'. Unknown is not missing. Verify the complete official document list.</p><div class="documents">'+docs.map(([id,st])=>'<div class="docrow"><span>'+escapeHTML(state.data.documents[id]||id)+'</span><select class="select" aria-label="Readiness for '+escapeHTML(state.data.documents[id]||id)+'" data-document="'+escapeHTML(id)+'">'+opts(["unknown","ready","in_progress","not_started","not_applicable"],st)+'</select></div>').join("")+'</div>';
openModal('<div class="eyebrow">'+escapeHTML(r.id)+' · '+escapeHTML(r.record_type)+(sync!=="none"?' · '+escapeHTML(sync):"")+'</div><h2>'+escapeHTML(r.name)+'</h2>',
'<div class="detail-layout"><div><div class="field"><label>Deadline & evidence classification</label><p>'+escapeHTML(stamp(r.deadline))+' · '+dateRisk(days(r.deadline))+' · '+verificationPill(r)+'</p><p class="subtle">'+escapeHTML(r.deadline_kind||"Deadline classification not recorded")+'</p><p class="subtle">'+escapeHTML(cutoffDescription(r))+'</p></div>'+
'<div class="field"><label>Execution decision</label><p>'+escapeHTML(execution?.top?.label||"No active execution action; review the source")+'</p><p class="subtle">'+escapeHTML(execution?.top?.detail||"The presence or absence of an action does not establish submission readiness.")+'</p><small class="subtle">'+(execution?.openProof||0)+' evidence checks · '+(execution?.knownPreparation||0)+' known preparation tasks</small></div><div class="field"><label>Evidence links</label><div class="linkset">'+link(r.source_url,"Primary evidence")+link(r.secondary_url,"Secondary evidence")+link(r.apply_url,"Application route")+'</div></div>'+
'<div class="field"><label>Institution / geography / decision</label><p>'+escapeHTML(r.institution||"Institution not recorded")+" · "+escapeHTML(r.country||"Country not recorded")+'</p><p>Recorded decision: '+escapeHTML(r.decision||"Not recorded")+" · Source observation: "+escapeHTML(r.source_date||"Not recorded")+'</p></div>'+
'<div class="field"><label>Funding / eligibility</label><p>'+escapeHTML(r.funding||"Not verified")+'</p><p>'+escapeHTML(r.eligibility||"Eligibility not verified")+'</p></div>'+
'<div class="field"><label>Academic fit & faculty</label><p>'+escapeHTML(r.fit||r.topic||"Not recorded")+'</p><p>'+escapeHTML(r.faculty)+'</p></div>'+
'<div class="field"><label>Required document evidence</label><p>'+escapeHTML(r.document_requirements_note||"Verify document list on official portal")+'</p></div>'+
'<div class="field"><label>Blockers, source reservations & submission precautions</label><p>'+escapeHTML(r.blockers||r.verification_note||"No specific blocker documented")+'</p>'+riskPill(r)+'</div>'+
'<div class="field"><label>Evidence excerpt</label><p>'+escapeHTML(r.evidence||"No detailed excerpt recorded")+'</p></div></div><div>'+fields+'</div></div>',
'<div class="buttons">'+(r.local_only?button("Save on this device","save-record",r.id,"primary")+button("Delete local opportunity","delete-local",r.id,"danger"):(r.record_type==="tracked"?button("Analyze with Copilot","ai-record",r.id,"primary")+button("Manage privately","ops-record",r.id):"")+button("Save local draft","save-record",r.id)+button("Review GitHub update","save-command",r.id)+(r.record_type==="candidate"?button("Promote candidate","promote",r.id):"")+button("Action Center","url",state.data.source_links.control_issue))+'</div><p class="footnote">'+(r.local_only?"Device-local only. Export a backup or a sanitized GitHub source file; no commit occurs automatically.":"Drafts stay in your browser until confirmed through GitHub. Notes and receipt URLs remain local; public issues must not contain private applicant data.")+'</p>');
}
function openModal(title,body,footer=""){
 if(!state.modal)state.returnFocus=document.activeElement;
 state.modal="generic";
 document.body.classList.add("modal-open");
 if($("app"))$("app").inert=true;
 $("dialogRoot").innerHTML='<div class="overlay" data-close="true"><div class="modal" tabindex="-1" role="dialog" aria-modal="true" aria-label="Workspace dialog"><div class="head"><div>'+title+'</div><button class="x" type="button" data-action="close" aria-label="Close dialog">✕</button></div>'+body+footer+'</div></div>';
 $("dialogRoot").querySelector(".modal")?.focus();
}
function closeModal(){
 state.modal="";
 $("dialogRoot").innerHTML="";
 document.body.classList.remove("modal-open");
 if($("app"))$("app").inert=false;
 if(state.returnFocus?.isConnected&&typeof state.returnFocus.focus==="function")state.returnFocus.focus();
 state.returnFocus=null;
}
function saveRecord(copy){
 const id=state.selected,r=getRecord(id);
 if(!r)return;
 const status=$("editStatus").value,verification=$("editVerification").value,followup=$("editFollowup").value,contact_status=$("editContact").value;
 const priority=$("editPriority").value,next_step=$("editStep").value.trim(),notes=$("editNotes").value.trim(),receipt=$("editReceipt").value.trim();
 if(receipt&&!safeURL(receipt)){const el=$("receiptError");if(el)el.textContent="Enter an HTTPS address or leave this blank."; $("editReceipt").setAttribute("aria-invalid","true");$("editReceipt").focus();return}
 if(status==="submitted"&&r.status!=="submitted"&&!confirm("Confirm that this application was actually submitted through the official portal?"))return;
 if(verification==="owner_verified"&&r.verification!=="owner_verified"&&!confirm("Confirm that you inspected the official source, including the exact deadline?"))return;
 const documents={};$("dialogRoot").querySelectorAll("[data-document]").forEach(el=>documents[el.dataset.document]=el.value);
 if(r.local_only){try{
  saveLocalRecord({...r,status,verification,priority,followup:followup||null,contact_status,next_step,notes,receipt,
   deadline_time:$("editCutoffTime")?.value||null,deadline_timezone:$("editCutoffZone")?.value.trim()||null,
   document_states:documents,updated_at:new Date().toISOString()});
  closeModal();render();notify("Local opportunity updated. Export a backup to preserve it.");
 }catch(error){notify("Local record rejected: "+String(error.message||error))}return}
 state.drafts[id]={...withDraftBase(id),status,verification,priority,followup:followup||null,contact_status,next_step,notes,receipt,documents,_sync_status:"draft"};
 saveStore(STORE,state.drafts);closeModal();render();
 if(copy)issueCommand(id);else notify("Saved on this device. GitHub confirmation is still required.");
}
function promoteCandidate(id){
 const r=getRecord(id);
 if(!r||r.record_type!=="candidate")return;
 if(!["source_verified","owner_verified"].includes(r.verification)){
  notify("Verify the official opportunity before promoting the research candidate.");return
 }
 if(!confirm("Promote this evidence-verified candidate into tracked applications? This stages a local draft and requires GitHub confirmation."))return;
 state.drafts[id]={...withDraftBase(id),promoted:true,verification:r.verification,_sync_status:"draft"};
 saveStore(STORE,state.drafts);closeModal();go("updates");notify("Promotion staged. Commit from Changes to make it authoritative.");
}
function issueCommand(id){
 const v=state.drafts[id],source=sourceRecord(id);
 if(source?.local_only){notify("Device-local records cannot be synchronized through the GitHub Action Center. Export GitHub source JSON.");return}
 if(!v||!source){notify("Source or local draft unavailable.");return}
 const sync=draftState(v,source);
 if(["conflict","needs-review"].includes(sync)){reconcileDraft(id);return}
 if(sync==="committed"){notify("The operational fields already match the committed source.");return}
 const {status,verification,followup,contact_status,next_step,documents,priority,promoted}=v;
 const payload={id,expected_updated_at:v.base_updated_at||""};
 for(const [key,value] of Object.entries({status,verification,followup,contact_status,next_step,documents,priority,promoted})){
  if(value!==undefined)payload[key]=value;
 }
 const command="/workspace "+JSON.stringify(payload);
 state.drafts[id]={...v,_sync_status:"pending"};saveStore(STORE,state.drafts);
 copyText(command);
 openModal("<h2>Confirm update in GitHub</h2>",'<p class="muted">Copied a version-checked command. Open the owner Action Center and post this command to request a commit. Private notes and receipt links are excluded.</p>'+
 '<div class="command">'+escapeHTML(command)+'</div><p>'+link(state.data.source_links.control_issue,"Open Action Center")+'</p>'+
 '<p class="footnote">Awaiting confirmation is not the same as committed. If the source changes, the backend rejects stale commands rather than overwriting them.</p>');
}
function commandPalette(){const q=state.focus||"";const matches=records().filter(r=>!q||[r.id,r.name,r.faculty,r.topic,r.next_step].join(" ").toLowerCase().includes(q.toLowerCase())).slice(0,15);openModal("<h2>Search across workspace</h2>",'<input class="input" id="paletteQuery" type="search" placeholder="Find an application, faculty member, source ID…" value="'+escapeHTML(q)+'" style="width:100%" aria-label="Universal search"><div id="paletteResults" class="searchresults">'+matches.map(r=>'<div class="mini-row"><div>'+rowButton(r)+'<small>'+escapeHTML(r.id)+' · '+escapeHTML(r.topic||r.country||"Unknown")+'</small></div>'+dateRisk(days(r.deadline))+'</div>').join("")+'</div><p class="footnote">Press Ctrl/Cmd+K anywhere to open, Escape to close.</p>');$("paletteQuery")?.focus()}
function updatePalette(){state.focus=$("paletteQuery").value;const matches=records().filter(r=>[r.id,r.name,r.faculty,r.topic,r.next_step].join(" ").toLowerCase().includes(state.focus.toLowerCase())).slice(0,15);$("paletteResults").innerHTML=matches.map(r=>'<div class="mini-row"><div>'+rowButton(r)+'<small>'+escapeHTML(r.id)+' · '+escapeHTML(r.country||"Unknown")+'</small></div>'+dateRisk(days(r.deadline))+'</div>').join("")||'<div class="empty">No results found.</div>'}
function exportFile(filename,content,type="text/plain;charset=utf-8"){const blob=new Blob([content],{type});const u=URL.createObjectURL(blob);const a=document.createElement("a");a.href=u;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
const csvVal=v=>{const raw=String(v??"");const safe=/^[\s\u0000-\u001f]*[=+\-@\t\r]/.test(raw)?"'"+raw:raw;return '"'+safe.replace(/"/g,'""')+'"'};
function asCSV(rows,columns){return[columns.map(csvVal).join(","),...rows.map(row=>columns.map(c=>csvVal(row[c])).join(","))].join("\r\n")}
function calendar(){return calendarEvents(records(),state.data?.instance?.repository||"phd-atlas")}
function saveLocalRecord(value){
 const record=createLocalRecord(value,value.id);
 if(!state.localRecords.some(r=>r.id===record.id))throw new TypeError("Local opportunity not found");
 state.localRecords=state.localRecords.map(r=>r.id===record.id?record:r);
 saveStore(LOCAL_STORE,state.localRecords);
}
function openLocalCreator(){
 openModal("<h2>Add an opportunity on this device</h2>",'<p class="muted">This record is local-only; it has not been verified, published or submitted. Export a backup before clearing browser data.</p>'+
 '<div class="field"><label for="localName">Programme or position</label><input id="localName" class="input" maxlength="350" required placeholder="PhD in robotics"></div>'+
 '<div class="field"><label for="localDeadline">Recorded deadline (optional)</label><input id="localDeadline" class="input" type="date"></div>'+
 '<div class="field"><label for="localCutoffTime">Recorded closing time (optional, unverified)</label><input id="localCutoffTime" class="input" type="time"><small class="subtle">Record the institution-local time, not your own local time.</small></div>'+
 '<div class="field"><label for="localCutoffZone">Institution timezone (IANA; paired with time)</label><input id="localCutoffZone" class="input" maxlength="80" placeholder="Europe/London"><small class="subtle">A recorded clock is provisional until an official source establishes the cutoff.</small></div>'+
 '<div class="field"><label for="localCountry">Country</label><input id="localCountry" class="input" maxlength="70"></div>'+
 '<div class="field"><label for="localSource">Public official-source URL (optional, HTTPS)</label><input id="localSource" class="input" type="url" placeholder="https://university.example/"></div>'+
 '<div class="field"><label for="localNext">Next action</label><textarea id="localNext" class="input" maxlength="650" placeholder="Verify the primary source, eligibility and funding"></textarea></div>'+
 '<p class="form-error" id="localError" role="alert"></p><div class="buttons">'+button("Add to this device","create-local","","primary")+button("Cancel","close")+'</div>');
 $("localName")?.focus();
}
function createLocal(){
 try{
  if(!globalThis.crypto?.randomUUID)throw new Error("Secure browser UUID generation is unavailable.");
  const input={name:$("localName").value,country:$("localCountry").value,deadline:$("localDeadline").value,deadline_time:$("localCutoffTime").value,deadline_timezone:$("localCutoffZone").value,source_url:$("localSource").value,next_step:$("localNext").value};
  const id="LOCAL-"+globalThis.crypto.randomUUID(),record=createLocalRecord(input,id);
  if(sourceRecord(id))throw new Error("Generated identifier collides with an existing opportunity");
  if(state.localRecords.length>=1000)throw new Error("Maximum 1000 device-local opportunities");
  state.localRecords.push(record);saveStore(LOCAL_STORE,state.localRecords);
  closeModal();state.scope="tracked";state.query="";state.status="all";state.horizon="all";persistViews();go("applications");detail(record);notify("Opportunity saved locally; GitHub was not changed.");
 }catch(error){const target=$("localError");if(target)target.textContent=String(error.message||error)}
}
async function importLocalBackup(file){
 try{
  if(!file||file.size>2_000_000)throw new TypeError("Choose a local backup JSON file no larger than 2 MB");
  const source=JSON.parse(await file.text());
  if(source?.schema_version!==1||!Array.isArray(source.local_records))throw new TypeError("Expected a PhD Atlas local-records v1 backup");
  const result=mergeLocalRecords(state.localRecords,source.local_records,state.data.records.map(r=>r.id));
  state.localRecords=result.records;saveStore(LOCAL_STORE,state.localRecords);render();
  notify(result.imported+" opportunity records imported; "+result.skipped+" existing IDs preserved.");
 }catch(error){notify("Import rejected: "+String(error.message||error))}
}
function exportData(kind){const filename="phd-atlas-"+TODAY();if(kind==="csv"){const cols=["id","name","country","deadline","deadline_kind","deadline_time","deadline_timezone","deadline_cutoff_verified","deadline_cutoff_utc","verification","status","next_step","source_url","funding","eligibility"];exportFile(filename+"-applications.csv",asCSV(sortList(filters(records())),cols),"text/csv;charset=utf-8")}else if(kind==="contacts"){exportFile(filename+"-contacts.csv",asCSV(records().filter(r=>r.faculty!=="Not recorded"),["id","name","faculty","contact_status","followup","source_url"]),"text/csv;charset=utf-8")}else if(kind==="ics"){exportFile(filename+"-deadlines.ics",calendar(),"text/calendar;charset=utf-8")}else if(kind==="drafts"){exportFile(filename+"-local-drafts.json",JSON.stringify({as_of:TODAY(),drafts:state.drafts,local_records:state.localRecords},null,2),"application/json")}else if(kind==="local"){exportFile(filename+"-local-records.json",JSON.stringify({schema_version:1,exported_at:new Date().toISOString(),local_records:state.localRecords},null,2),"application/json")}else if(kind==="github-source"){exportFile("user_opportunities.json",JSON.stringify(exportIndependentSource(state.localRecords,TODAY(),state.data.timezone||"UTC",state.data.instance?.type==="independent"&&state.data.instance?.data_mode==="source"?state.data.records:[]),null,2),"application/json")}else{exportFile(filename+"-workspace.json",JSON.stringify({source_snapshot:state.data,local_drafts:state.drafts,local_records:state.localRecords},null,2),"application/json")}}
const ICONS={
 home:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 10h16M10 10v10"/>',
 file:'<path d="M7 3.5h8l3 3V20H7zM15 3.5v4h3M10 12h5M10 16h5"/>',
 calendar:'<rect x="3.5" y="5.5" width="17" height="15" rx="2"/><path d="M7.5 3.5v4M16.5 3.5v4M3.5 10h17"/>',
 columns:'<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9 4.5v15M15 4.5v15"/>',
 check:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 3 3 5-6"/>',
 users:'<circle cx="9.2" cy="8.5" r="3"/><path d="M3.6 19v-1.5a5.6 5.6 0 0 1 11.2 0V19M17 5.8a3 3 0 0 1 0 5.6M17.7 13.7a5.3 5.3 0 0 1 2.7 4.6"/>',
 clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5l3.5 2"/>',
 compare:'<rect x="3.5" y="5" width="6.5" height="14" rx="1.5"/><rect x="14" y="5" width="6.5" height="14" rx="1.5"/>',
 shield:'<path d="M12 2.5 19 5v6.8c0 4.5-2.8 7.5-7 9.7-4.2-2.2-7-5.2-7-9.7V5zM9 11.8l2 2 4-4"/>',
 archive:'<rect x="4" y="4.5" width="16" height="4.5" rx="1"/><path d="M6 9v10.5h12V9M10 13.3h4"/>',
 layers:'<path d="m12 2 9 5-9 5-9-5zM3 12l9 5 9-5M3 17l9 5 9-5"/>',
 sparkles:'<path d="m12 2 1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6zM19 17l.7 1.8L22 19.5l-2.3.7L19 22l-.7-1.8-2.3-.7 2.3-.7z"/>',
 bot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4m-2 0h4M8 13h.1M16 13h.1M9 17h6"/>',
 flow:'<rect x="3" y="3" width="7" height="6" rx="1"/><rect x="14" y="15" width="7" height="6" rx="1"/><path d="M10 6h5v5m0 0v4M15 11H8v4"/>',
 activity:'<path d="M3 12h4l3-7 4 14 3-7h4"/>',
 settings:'<circle cx="12" cy="12" r="3.5"/><path d="M12 2v3m0 14v3M4.9 4.9l2.1 2.1m10 10 2.1 2.1M2 12h3m14 0h3M4.9 19.1 7 17m10-10 2.1-2.1"/>',
 database:'<ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6M4.5 12v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6"/>'
};
function navigation(){
 const tracked=records().filter(r=>r.record_type==="tracked");
 const counts={applications:tracked.length,discovery:records().filter(r=>r.record_type==="candidate").length,actions:tracked.filter(open).filter(thisWeek).length,review:tracked.filter(r=>r.recheck_required).length};
 const chapters={dashboard:"Workspace",applications:"Tracking",ai:"Assistant",settings:"Configuration"};
 $("navigation").innerHTML=VIEWS.map(([id,icon,label])=>
  (chapters[id]?'<div class="nav-chapter" aria-hidden="true">'+chapters[id]+'</div>':"")+
  '<button class="nav-btn '+(state.view===id?"active":"")+'" type="button" data-action="nav" data-value="'+id+'"'+(state.view===id?' aria-current="page"':'')+'>'+
  '<span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24">'+(ICONS[icon]||"")+'</svg></span>'+
  '<span class="nav-label">'+escapeHTML(label)+'</span>'+(counts[id]?'<em>'+counts[id]+'</em>':"")+'</button>'
 ).join("");
 $("crumbName").textContent=VIEWS.find(x=>x[0]===state.view)?.[2]||"Overview";
 const mobile=$("workspaceSection");
 if(mobile)mobile.innerHTML=VIEWS.map(([id,,label])=>'<option value="'+id+'"'+(id===state.view?' selected':'')+'>'+escapeHTML(label)+'</option>').join("");
 const next=tracked.filter(r=>open(r)&&r.status!=="submitted"&&remainingDeadlineDays(r)!==null&&remainingDeadlineDays(r)>=0).sort((a,b)=>remainingDeadlineDays(a)-remainingDeadlineDays(b)||priority(b)-priority(a))[0];
 const sidebarDue=$("sidebarDue");
 if(sidebarDue)sidebarDue.innerHTML=next?
  '<span class="sidebar-deadline-label">NEXT RECORDED CLOSING</span><strong>'+(remainingDeadlineDays(next)===0?(verifiedCutoff(next)!==null?'UNDER 24H':'TODAY'):remainingDeadlineDays(next)+' DAYS')+'</strong><button type="button" class="sidebar-deadline-link" data-action="record" data-value="'+escapeHTML(next.id)+'">'+escapeHTML(next.name)+'</button><small>'+escapeHTML(stamp(next.deadline))+'</small>':
  '<span class="sidebar-deadline-label">NEXT RECORDED CLOSING</span><small>No upcoming dated applications</small>';
}
function render(){
 if(!state.data)return;
 navigation();
 const views={dashboard,calendar:calendarView,applications,discovery:discoveryView,deployment:deploymentView,documents:documentsView,readiness,pipeline,contacts,actions,ledger:ledgerView,updates,compare,review,archive,sources};
 const intelligence=["ai","agents","automations","activity","source-observations","settings","operations"].includes(state.view);
 const freshness=freshnessState(state.data.as_of,TODAY());
 const note=["aging","stale","unknown","future"].includes(freshness.state)
   ?'<div class="freshness-note" role="status"><span>'+escapeHTML(freshness.label)+'. Verify critical deadlines using official sources.</span>'+button("Review sources","nav","sources")+'</div>':"";
 $("body").innerHTML=note+(intelligence?aiConsole.view(state.view,{records:records()}):views[state.view]());
 const activeBadge=$("currentModel");
 const browserStatus=aiConsole.browserModel.status();
 const modelReady=aiConsole.isLive()?aiConsole.isVerified():browserStatus.verified;
 if(activeBadge){
   activeBadge.textContent=aiConsole.isLive()?aiConsole.activeLabel()+" / "+aiConsole.activeModel():browserStatus.verified?"Local / "+browserStatus.model:"Connect model";
   activeBadge.classList.toggle("is-online",modelReady);
 }
 const runtimeNote=$("aiRuntimeState");
 if(runtimeNote)runtimeNote.textContent=aiConsole.isLive()?"Private runtime · agents and persistence ready":browserStatus.verified?"Browser-local model verified · direct inference only":"No verified inference · configure in Settings";
 const unhealthy=state.data.providers.filter(p=>p.health!=="ok").length;
 $("providerStatus").innerHTML='<strong>'+escapeHTML(stamp(state.data.as_of))+'</strong><span class="signal"><span class="signal-dot '+(unhealthy?"":"ok")+'" aria-hidden="true"></span>'+unhealthy+' source feeds need attention</span>';
 const topAsOf=$("topEvidenceAsOf");if(topAsOf)topAsOf.textContent="Evidence observed "+stamp(state.data.as_of)+(state.data.instance?.type==="independent"?" · Independent deployment: verify evidence provenance":"");
}
function go(view){
 if(!VIEWS.some(([id])=>id===view))return;
 if(view==="ai"&&state.view!=="ai")aiConsole.setContext(state.view);
 state.view=view;
 if(location.hash!=="#"+view)location.hash=view;
 window.scrollTo({top:0,behavior:"instant"});render();
}
const aiConsole=createConsole({notify,onChange:()=>{if(state.data)render()},navigate:go,getRecords:records,getSourceRecords:()=>state.data?.records||[],onReload:loadSnapshot,getView:()=>state.view});
let atlasLens=null;
function explainNotifications(){const supported=("Notification" in window);const permission=supported?Notification.permission:"unsupported";openModal("<h2>Reminder settings</h2>",'<p class="muted">Reminders are computed locally from source dates while this page is open. Closing the tab disables on-page notifications. GitHub Actions provides separate scheduled reminders.</p><div class="notifications"><div class="notification"><strong>Browser permission</strong>'+escapeHTML(permission)+'</div><div class="notification"><strong>Current horizon</strong>Date-only: 0, 1, 3 and 7 days. Verified cutoffs: 7d, 3d, 24h, 6h and 1h</div></div><div class="buttons">'+button("Request browser permission","permission","","primary")+button("View GitHub notifications","url",ownerRepo()+"/actions/workflows/phd-intelligence.yml")+'</div>')}
function checkNotifications(){
 if(!state.data||!state.prefs.reminders||!("Notification" in window)||Notification.permission!=="granted")return;
 const alerted=state.prefs.notified||{};let changed=false;
 for(const r of records().filter(r=>r.record_type==="tracked")){
  if(!open(r))continue;
  const exact=exactCutoffReminder(r),known=verifiedCutoff(r)!==null;
  let key,title,body;
  if(exact){key=exact.key;title=exact.title;body=exact.body}
  else if(known)continue;
  else{
   const d=days(r.deadline);
   if(![0,1,3,7].includes(d))continue;
   key=r.id+"|"+r.deadline+"|"+d;
   title="PhD deadline: "+stamp(r.deadline);
   body=r.name.slice(0,140)+" — recorded date only; verify exact closing hour and official portal.";
  }
  if(alerted[key])continue;
  try{
   const n=new Notification(title,{body,tag:key});
   n.onclick=()=>{window.focus();go("applications");detail(getRecord(r.id));n.close()};
   alerted[key]=TODAY();changed=true;
  }catch{}
 }
 if(changed){state.prefs.notified=Object.fromEntries(Object.entries(alerted).slice(-500));saveStore(PREFS,state.prefs)}
}
function events(){
 document.addEventListener("click",e=>{
  if(e.target?.dataset?.close==="true"){closeModal();return}
  const el=e.target.closest("[data-action]");if(!el)return;
  const {action:type,value}=el.dataset;
  if(type==="nav")go(value);
  else if(type==="lens-open")atlasLens?.open();
  else if(type==="record"){closeModal();detail(getRecord(value))}
  else if(type==="ai-record"){closeModal();aiConsole.selectApplication(value);atlasLens?.setApplication(value);atlasLens?.open()}
  else if(type==="ops-record"){closeModal();aiConsole.openApplication(value);go("operations")}
   else if(type==="close")closeModal();
  else if(type==="save-record")saveRecord(false);
  else if(type==="save-command")saveRecord(true);
  else if(type==="command")issueCommand(value);
  else if(type==="reconcile")reconcileDraft(value);
  else if(type==="confirm-rebase")commitRebase(value);
  else if(type==="promote")promoteCandidate(value);
  else if(type==="new-local")openLocalCreator();
  else if(type==="create-local")createLocal();
  else if(type==="import-local")$("localImportFile")?.click();
  else if(type==="delete-local"){
   const row=state.localRecords.find(r=>r.id===value);
   if(row&&confirm("Delete this device-only opportunity? Export a backup first. This action cannot be undone.")){
    state.localRecords=state.localRecords.filter(r=>r.id!==value);delete state.drafts[value];state.compare=state.compare.filter(id=>id!==value);
    saveStore(LOCAL_STORE,state.localRecords);saveStore(STORE,state.drafts);saveStore(COMPARE_STORE,state.compare);closeModal();render();notify("Local opportunity deleted.");
   }
  }
  else if(type==="save-view")saveCurrentView();
  else if(type==="confirm-view")commitSavedView();
  else if(type==="delete-view")deleteSavedView();
  else if(type==="clear-filters")resetFilters();
  else if(type==="retry-load")loadSnapshot();
  else if(type==="readiness-filter"){readinessFilter=value;render()}
   else if(type==="discovery-filter"){discoveryFilter=value;render()}
  else if(type==="audit-filter"){selectedAuditCategory=value;assuranceLimit=75;render()}
  else if(type==="audit-more"){assuranceLimit+=75;render()}
  else if(type==="ledger-page"){ledgerPage=Math.max(1,Number(value)||1);render()}
  else if(type==="export-ledger"){
   const full=state.data.task_ledger||[];
   exportFile("phd-atlas-full-task-ledger-"+TODAY()+".csv",asCSV(full,["id","application_id","name","action","due","type","state","sheet","row","source_url"]),"text/csv;charset=utf-8");
  }
  else if(type==="export-readiness"){
   const report=portfolioReadiness(records(),TODAY());
   const rows=[...report.active,...report.submitted,...report.halted].map(x=>({id:x.id,application:x.record.name,phase:x.phase,deadline:x.record.deadline||"",followup:x.record.followup||"",next_action:x.top?.label||"",action_type:x.top?.kind||"",open_proof_checks:x.openProof,recorded_preparation:x.knownPreparation,source_url:x.record.source_url||""}));
   exportFile("phd-atlas-readiness-"+TODAY()+".csv",asCSV(rows,["id","application","phase","deadline","followup","next_action","action_type","open_proof_checks","recorded_preparation","source_url"]),"text/csv;charset=utf-8");
  }
  else if(type==="export-audit"){
   const report=auditWorkspace({...state.data,records:records()},TODAY());
   const rows=report.queue.map(x=>({id:x.record_id,application:x.record_name,category:x.category,urgency:x.urgency,issue:x.title,details:x.detail,source_url:x.source_url}));
   exportFile("phd-atlas-assurance-"+TODAY()+".csv",asCSV(rows,["id","application","category","urgency","issue","details","source_url"]),"text/csv;charset=utf-8");
  }
  else if(type==="discard"){
   if(confirm("Discard the unsynchronized draft for "+value+"? The change cannot be undone.")){
    delete state.drafts[value];saveStore(STORE,state.drafts);closeModal();render();notify("Local draft discarded.")
   }
  }
  else if(type==="cal-day"){state.selectedDate=value;render()}
  else if(type==="cal-today"){state.calendarMonth=TODAY().slice(0,7);state.selectedDate=TODAY();render()}
  else if(type==="cal-prev"||type==="cal-next"){
   const base=state.calendarMonth||TODAY().slice(0,7),[y,m]=base.split("-").map(Number);
   const next=new Date(Date.UTC(y,m-1+(type==="cal-next"?1:-1),1));
   state.calendarMonth=next.toISOString().slice(0,7);state.selectedDate=null;render();
  }
  else if(type==="pipeline-filter"){state.status=value;state.scope="tracked";state.horizon="all";state.activePreset="";persistViews();go("applications")}
  else if(type==="clear-compare"){state.compare=[];saveStore(COMPARE_STORE,[]);render();notify("Comparison cleared.")}
  else if(type==="url"){const u=safeURL(value);if(u)window.open(u,"_blank","noopener,noreferrer")}
  else if(type==="export")exportData(value);
  else if(type==="task"){copyText("/done "+value);notify("Task command copied. Post to GitHub Action Center.")}
  else if(type==="permission"){
   if("Notification" in window)Notification.requestPermission().then(()=>{closeModal();checkNotifications();notify("Browser notification preference updated.")});
   else notify("Notifications are not supported by this browser.");
  }
 });
 document.addEventListener("change",e=>{
  const t=e.target;
  if(t.id==="workspaceSection"){go(t.value);return}
  if(t.id==="localImportFile"){const file=t.files?.[0];if(file)importLocalBackup(file);return}
  if(t.id==="ledgerType"){ledgerType=t.value;ledgerPage=1;render();return}
  if(t.matches("[data-stage-id]")){stageStatus(t.dataset.stageId,t.value);return}
  if(t.matches("[data-compare]")){
   const id=t.dataset.compare;
   if(t.checked){
    if(state.compare.length>=4&&!state.compare.includes(id)){t.checked=false;notify("Compare up to four opportunities.");return}
    if(!state.compare.includes(id))state.compare.push(id);
   }else state.compare=state.compare.filter(x=>x!==id);
   saveStore(COMPARE_STORE,state.compare);
   $("body").querySelectorAll("[data-compare]").forEach(c=>c.checked=state.compare.includes(c.dataset.compare));
   const chosen=$("body").querySelector('[data-action="nav"][data-value="compare"]');
   if(chosen)chosen.textContent="Compare selected ("+state.compare.length+")";
   navigation();return;
  }
  if(t.id==="viewPreset"){
   if(t.value)applySavedView(t.value);
   else{state.activePreset="";persistViews();render()}
   return;
  }
  const key={filterScope:"scope",filterStatus:"status",filterVerify:"verification",filterHorizon:"horizon",filterCountry:"country",filterSort:"sort"}[t.id];
  if(key){
   const focusId=t.id;state[key]=t.value;state.activePreset="";persistViews();render();$(focusId)?.focus();
  }
 });
 document.addEventListener("input",e=>{
  if(e.target.id==="discoveryQuery"){
    const pos=e.target.selectionStart;
    discoveryQuery=e.target.value.slice(0,200);
    render();
    const field=$("discoveryQuery");
    if(field){field.focus();field.setSelectionRange(pos,pos)}
   }else if(e.target.id==="ledgerQuery"){
   const pos=e.target.selectionStart;ledgerQuery=e.target.value;ledgerPage=1;render();$("ledgerQuery")?.focus();$("ledgerQuery")?.setSelectionRange(pos,pos);
  }else if(e.target.id==="filterQuery"){
   const pos=e.target.selectionStart;
   state.query=e.target.value;state.activePreset="";persistViews();render();
   $("filterQuery")?.focus();$("filterQuery")?.setSelectionRange(pos,pos);
  }else if(e.target.id==="paletteQuery")updatePalette();
 });
 document.addEventListener("keydown",e=>{
  if(e.key==="Tab"&&state.modal){
   const nodes=[...$("dialogRoot").querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled])')].filter(el=>el.getClientRects().length);
   if(nodes.length){
    const first=nodes[0],last=nodes[nodes.length-1],active=document.activeElement;
    if(e.shiftKey&&(active===first||active?.classList.contains("modal"))){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&(active===last||active?.classList.contains("modal"))){e.preventDefault();first.focus()}
   }
  }
  if(e.key==="Escape"&&state.modal){closeModal();return}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();state.focus="";commandPalette();return}
  if(e.key==="/"&&!state.modal&&!["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName)){e.preventDefault();$("filterQuery")?.focus()}
 });
 document.addEventListener("dragstart",e=>{
  const card=e.target.closest(".kanban-card");if(!card)return;
  state.draggedId=card.dataset.dragId;
  if(e.dataTransfer){e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("text/plain",state.draggedId)}
 });
 document.addEventListener("dragover",e=>{if(e.target.closest(".kanban-lane"))e.preventDefault()});
 document.addEventListener("drop",e=>{
  const lane=e.target.closest(".kanban-lane");if(!lane||!state.draggedId)return;
  e.preventDefault();const id=state.draggedId,target=lane.dataset.lane;state.draggedId=null;stageStatus(id,target);
 });
 document.addEventListener("dragend",()=>{state.draggedId=null});
 window.addEventListener("hashchange",()=>{
  const requested=resolveWorkspaceRoute(location.hash);
  if(location.hash&&location.hash!=="#"+requested)history.replaceState(null,"",location.pathname+location.search+"#"+requested);
  if(state.view===requested)return;
  state.view=requested;closeModal();render();
 });
 $("openSearch").addEventListener("click",()=>{state.focus="";commandPalette()});
 $("exportMenu").addEventListener("click",()=>openModal("<h2>Export workspace</h2>",'<p class="muted">Exports clearly separate committed evidence from local browser drafts.</p><div class="buttons">'+button("Applications CSV","export","csv")+button("Contacts CSV","export","contacts")+button("Calendar ICS","export","ics")+button("Local draft JSON","export","drafts")+button("Local opportunity backup","export","local")+button("GitHub source JSON (public fields)","export","github-source")+button("Full workspace JSON","export","json")+'</div>'));
 $("themeToggle").addEventListener("click",()=>{state.prefs.theme=state.prefs.theme==="light"?"dark":"light";saveStore(PREFS,state.prefs);document.body.classList.toggle("dark",state.prefs.theme==="dark")});
 $("notificationToggle").addEventListener("click",explainNotifications);
}
function updateInstanceLinks(data){
 const repo=safeURL(data?.source_links?.repository);
 if(!repo)return;
 const sidebar=document.querySelector(".side-link");if(sidebar)sidebar.href=repo;
 const release=document.querySelector(".main-footer a");if(release)release.href=repo+"/releases";
}
async function loadSnapshot(){
 try{
  const response=await fetch("./data/workspace.json",{cache:"no-store"});
  if(!response.ok)throw new Error("The source could not be retrieved.");
  const data=await response.json(),validation=validateSnapshot(data);
  if(!validation.ok)throw new Error(validation.error);
  const prior=state.data?.generated_at;
  state.data=data;
  updateInstanceLinks(data);
  atlasLens?.refreshData();
  if(!Array.isArray(state.compare))state.compare=[];
  state.compare=state.compare.filter(id=>validation.ids.has(id)||state.localRecords.some(r=>r.id===id)).slice(0,4);
  saveStore(COMPARE_STORE,state.compare);
  render();
  if(prior&&prior!==data.generated_at)notify("Source snapshot updated. Local drafts have been checked for conflicts.");
  checkNotifications();
 }catch(error){
  if(state.data){notify("Source refresh failed. The last verified snapshot remains available.");return}
  $("body").innerHTML=heading("Source unavailable","The workspace cannot validate its source snapshot.")+
  '<div class="alert">'+escapeHTML(error.message||"The data could not be loaded.")+'</div>'+
  '<div class="buttons">'+button("Retry loading","retry-load","","primary")+button("Open repository","url",ownerRepo())+'</div>';
 }
}
function init(){
 events();
 atlasLens=mountAtlasLens({getRecords:()=>state.data?records():[],getPublicRecords:()=>state.data?.records||[],browserModel:aiConsole.browserModel,getView:()=>state.view,getSelectedApplication:()=>state.selected,openSettings:()=>go("settings"),onFocusApplication:id=>detail(getRecord(id)),onRunComplete:()=>aiConsole.isLive()?aiConsole.connect():undefined});
 document.body.classList.toggle("dark",state.prefs.theme==="dark");
 const route=resolveWorkspaceRoute(location.hash);
 if(location.hash&&location.hash!=="#"+route)history.replaceState(null,"",location.pathname+location.search+"#"+route);
 state.view=route;
 loadSnapshot();
 aiConsole.connect();
 setInterval(checkNotifications,60_000);
 setInterval(loadSnapshot,15*60_000);
}
init();
})();
