import {daysUntil, freshnessState} from "./domain.mjs";

const closed=new Set(["rejected","withdrawn","archived","offer"]);
const weights={submission:110,deadline:95,documents:80,route:75,source:68,status:60};
export const auditCategories=["all","deadline","source","documents","submission","route","status"];

export function auditWorkspace(snapshot,today){
 const records=Array.isArray(snapshot?.records)?snapshot.records.filter(r=>r.record_type==="tracked"):[];
 const providers=Array.isArray(snapshot?.providers)?snapshot.providers:[];
 const queue=[];
 const add=(r,category,title,detail)=>{
  const days=daysUntil(r.deadline,today),score=weights[category]+(days===null||days<0?0:Math.max(0,21-days));
  queue.push({id:r.id+":"+category+":"+queue.length,record_id:r.id,record_name:r.name,category,title,detail,source_url:r.source_url||"",days,score,urgency:days!==null&&days>=0&&days<=3?"urgent":days!==null&&days>=0&&days<=14?"attention":"review"});
 };
 for(const r of records){
  if(closed.has(r.status))continue;
  const days=daysUntil(r.deadline,today),docs=Object.values(r.document_states||{});
  if(r.status==="submitted"){
   if(!String(r.submission_receipt||r.receipt||"").trim())add(r,"submission","Submission confirmation not recorded","Owner status says Submitted, but this view has no receipt identifier. Verify the portal in the private record.");
   if(r.followup&&daysUntil(r.followup,today)!==null&&daysUntil(r.followup,today)<=7)add(r,"status","Submission follow-up due","Verify the recorded follow-up action.");
   continue;
  }
  if(r.status==="blocked")add(r,"status","Owner-marked blocker","Review the documented blocker before resuming.");
  if(days===null)add(r,"deadline","Deadline date missing","No valid application closing date is recorded.");
  else if(days<0)add(r,"status","Recorded date elapsed","The date passed. Do not infer submission, rejection or withdrawal.");
  else if(days<=45&&r.deadline_cutoff_verified!==true)add(r,"deadline","Cutoff hour not structurally verified","A calendar date is not proof of the portal closing time and timezone.");
  if(!String(r.source_url||"").trim())add(r,"source","Official source link missing","Add a retrievable primary programme or vacancy source.");
  if(!["source_verified","owner_verified"].includes(r.verification))add(r,"source","Evidence verification outstanding","Check the official source before marking evidence reviewed.");
  if(r.duplicate_submission_advisory)add(r,"route","Possible duplicate route","Verify whether the programme requires one joint application or allows separate submissions.");
  if(docs.includes("not_started"))add(r,"documents","Explicit preparation gap","At least one recorded document is Not started. Confirm its requirement.");
  if(docs.includes("unknown")&&(days===null||(days>=0&&days<=30)))add(r,"documents","Document state unknown","Unknown does not mean the applicant lacks this document.");
 }
 queue.sort((a,b)=>b.score-a.score||(a.days??Infinity)-(b.days??Infinity)||a.record_id.localeCompare(b.record_id));
 return {
  queue,
  counts:Object.fromEntries(auditCategories.slice(1).map(c=>[c,queue.filter(q=>q.category===c).length])),
  providers:{total:providers.length,degraded:providers.filter(p=>!["ok","healthy"].includes(p.health)).map(p=>({name:p.name,health:p.health||"unknown"}))},
  freshness:freshnessState(snapshot?.as_of,today),
  totals:{
   tracked:records.length,obligations:queue.length,affected:new Set(queue.map(q=>q.record_id)).size,
   unverified:records.filter(r=>!["source_verified","owner_verified"].includes(r.verification)).length,
   cutoffUnstructured:records.filter(r=>r.deadline&&r.deadline_cutoff_verified!==true).length,
   documentsUnknown:records.filter(r=>Object.values(r.document_states||{}).includes("unknown")).length,
   documentsNotStarted:records.filter(r=>Object.values(r.document_states||{}).includes("not_started")).length,
   receiptsAbsent:records.filter(r=>r.status==="submitted"&&!String(r.submission_receipt||r.receipt||"").trim()).length
  }
 };
}
export function sourceCoverage(snapshot){
 const c=snapshot?.coverage||{};
 return {sheets:Array.isArray(c.worksheets)?c.worksheets:[],sources:Array.isArray(c.files)?c.files:[],asOf:c.workbook_audit_as_of||null,totals:c.totals||{},discoveryErrors:c.discovery_errors||{}};
}
