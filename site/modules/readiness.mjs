import {verifiedCutoff} from "./deadline-cutoff.mjs";
import {daysUntil,deadlineCollisions,isDay} from "./domain.mjs";

const CLOSED=new Set(["offer","rejected","withdrawn","archived"]);
const VERIFIED=new Set(["source_verified","owner_verified"]);
const DOCS={academic_cv:"Academic CV",research_statement:"Research statement",transcripts:"Academic transcripts",recommendations:"Reference letters",english_proof:"English proficiency",research_portfolio:"Research portfolio"};
const VALID_DOC_STATES=new Set(["ready","unknown","in_progress","not_started","not_applicable"]);
const hasText=x=>typeof x==="string"&&x.trim().length>0;
const requirements=r=>Array.isArray(r?.documents)?[...new Set(r.documents.filter(d=>typeof d==="string"&&d in DOCS))]:[];

export function assessApplication(record,today,now=Date.now()){
 if(!record||record.record_type!=="tracked"||!isDay(today))return null;
 const exact=verifiedCutoff(record);
 const due=exact===null?daysUntil(record.deadline,today):Math.floor((exact-now)/86400000);
 const followup=daysUntil(record.followup,today);
 const phase=CLOSED.has(record.status)?"closed":record.status==="submitted"?"submitted":record.status==="blocked"?"blocked":due!==null&&due<0?"expired":"active";
 const tasks=[];
 const add=(key,label,detail,kind,score)=>tasks.push({key,label,detail,kind,score});
 if(phase==="submitted"){
  if(!hasText(record.receipt)&&!hasText(record.submission_receipt))add("receipt","Confirm portal submission receipt","Submitted is owner-recorded. Confirm the receipt privately; never publish identifiers.","evidence",110);
  if(followup!==null&&followup<=14)add("submitted_followup","Review post-submission follow-up",followup<0?"Recorded follow-up date has passed.":"Recorded follow-up date is approaching.","followup",followup<=0?118:90);
 }else if(phase==="blocked")add("owner_blocker","Resolve owner-marked blocker","Do not treat the route as actionable until the owner clears the blocker.","blocker",140);
 else if(phase==="expired")add("past_deadline","Verify whether the application route is still available","The recorded deadline passed. Late submission is not presumed permitted.","blocker",110);
 else if(phase==="active"){
  if(record.duplicate_submission_advisory===true)add("duplicate_route","Resolve possible duplicate submission route","Confirm whether joint or separate submissions are required.","blocker",125);
  if(hasText(record.blockers))add("recorded_reservations","Review recorded constraints","Source notes contain a blocker or reservation.","blocker",112);
  if(!hasText(record.source_url))add("primary_source","Find an official programme source","No official primary-source URL is recorded.","evidence",108);
  else if(!VERIFIED.has(record.verification))add("source_review","Review current official source evidence","A linked source is not explicitly verified.","evidence",105);
  if(due===null)add("deadline_date","Establish the application deadline","No valid closing date is recorded.","evidence",107);
  else if(record.deadline_cutoff_verified!==true&&record.deadline_time_verified!==true)add("deadline_cutoff","Verify closing time and timezone","A calendar date does not verify a portal cutoff.","evidence",99);
  const documents=requirements(record),states=record.document_states&&typeof record.document_states==="object"?record.document_states:{};
  if(!documents.length)add("document_list","Confirm complete document requirements","No documented requirements inventory is available.","evidence",96);
  else{
   if(!hasText(record.document_requirements_note))add("document_scope","Verify complete document requirements","The official requirements scope is not recorded.","evidence",85);
   for(const key of documents){
    const value=VALID_DOC_STATES.has(states[key])?states[key]:"unknown",name=DOCS[key];
    if(value==="not_started")add("document:"+key,"Start "+name,"Explicitly marked not started; reconfirm it is required.","preparation",92);
    if(value==="in_progress")add("document:"+key,"Finish "+name,"In progress; verify institutional format.","preparation",82);
    if(value==="unknown")add("document:"+key,"Confirm "+name+" readiness","Unknown does not mean missing.","evidence",74);
   }
  }
  if(!hasText(record.eligibility))add("eligibility","Confirm personal eligibility","An individual eligibility determination is not recorded.","evidence",68);
  if(!hasText(record.funding))add("funding","Confirm funding conditions","Funding and applicant-specific terms are not recorded.","evidence",56);
  if(followup!==null&&followup<=14&&!["completed","declined"].includes(record.contact_status))add("faculty_followup","Review faculty follow-up",followup<0?"Follow-up date passed.":"Follow-up date is approaching.","followup",followup<=0?121:88);
  if(hasText(record.next_step))add("owner_step","Review owner-recorded next action","Owner-entered, not proof of completion.","owner",63);
 }
 tasks.sort((a,b)=>b.score-a.score||a.key.localeCompare(b.key));
 const urgency=phase==="active"?(due!==null&&due<=3?40:due!==null&&due<=14?20:0):phase==="submitted"?10:0;
 const preference=record.priority==="high"?12:record.priority==="low"?-8:0;
 return {id:record.id,record,phase,due,followup,tasks,top:tasks[0]||null,priority:(tasks[0]?.score??0)+urgency+preference,
  openProof:tasks.filter(t=>t.kind==="evidence").length,knownPreparation:tasks.filter(t=>t.kind==="preparation").length};
}

export function portfolioReadiness(records,today,now=Date.now()){
 if(!Array.isArray(records)||!isDay(today))throw new TypeError("Valid records and an ISO observation date are required");
 const assessed=records.map(r=>assessApplication(r,today,now)).filter(Boolean);
 const active=assessed.filter(x=>x.phase==="active").sort((a,b)=>b.priority-a.priority||(a.due??Infinity)-(b.due??Infinity)||String(a.id).localeCompare(String(b.id)));
 const submitted=assessed.filter(x=>x.phase==="submitted").sort((a,b)=>b.priority-a.priority||String(a.id).localeCompare(String(b.id)));
 const halted=assessed.filter(x=>["blocked","expired"].includes(x.phase));
 const closed=assessed.filter(x=>x.phase==="closed");
 const groups=new Map();
 for(const x of active){
  const states=x.record.document_states&&typeof x.record.document_states==="object"?x.record.document_states:{};
  for(const key of requirements(x.record)){
   const row=groups.get(key)||{key,name:DOCS[key],required:0,unknown:0,not_started:0,in_progress:0,ready:0,not_applicable:0};
   const state=VALID_DOC_STATES.has(states[key])?states[key]:"unknown";
   row.required++;row[state]++;groups.set(key,row);
  }
 }
 const reusable=[...groups.values()].filter(x=>x.required>1||x.not_started>0||x.in_progress>0)
  .sort((a,b)=>(b.not_started*2+b.in_progress+b.unknown)-(a.not_started*2+a.in_progress+a.unknown)||b.required-a.required||a.key.localeCompare(b.key));
 return {active,submitted,halted,closed,reusable,collisions:deadlineCollisions(active.map(x=>x.record),today),totals:{
  tracked:assessed.length,active:active.length,close14:active.filter(x=>x.due!==null&&x.due>=0&&x.due<=14).length,
  deadlineProof:active.filter(x=>x.tasks.some(t=>["deadline_date","deadline_cutoff"].includes(t.key))).length,
  sourceProof:active.filter(x=>x.tasks.some(t=>["primary_source","source_review"].includes(t.key))).length,
  knownDocumentGaps:active.filter(x=>x.knownPreparation>0).length,
  unknownDocuments:active.filter(x=>x.tasks.some(t=>t.key==="document_list"||t.key.startsWith("document:")&&t.kind==="evidence")).length,
  submittedWithoutReceipt:submitted.filter(x=>x.tasks.some(t=>t.key==="receipt")).length,
  halted:halted.length}};
}
