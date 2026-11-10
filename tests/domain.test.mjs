import test from "node:test";
import assert from "node:assert/strict";
import {isDay,daysUntil,isActionable,documentReadiness,riskSignal,priorityScore,validateSnapshot,draftState,applyRecordFilters,deadlineCollisions,freshnessState} from "../site/modules/domain.mjs";

const today="2026-11-09";
const base={id:"alpha",name:"Verified PhD opportunity",record_type:"tracked",status:"preparing",verification:"source_verified",deadline:"2026-11-10",documents:["academic_cv","transcripts"],document_states:{academic_cv:"ready",transcripts:"unknown"},document_requirements_note:"CV and transcript",country:"NL",next_step:"Check admission portal",faculty:"Not recorded"};
test("UTC day arithmetic is DST independent, invalid dates remain unknown",()=>{
 assert.equal(daysUntil("2026-11-10",today),1);
 assert.equal(daysUntil("2026-11-08",today),-1);
 assert.equal(daysUntil(null,today),null);
 assert.equal(daysUntil("2026-02-30",today),null);
 assert.equal(isDay("2028-02-29"),true);
 assert.equal(isDay("2027-02-29"),false);
});
test("unknown readiness never means missing or ready",()=>{
 assert.equal(documentReadiness(base).state,"unknown");
 assert.equal(documentReadiness({...base,document_states:{academic_cv:"not_started",transcripts:"unknown"}}).state,"incomplete");
 assert.equal(documentReadiness({...base,document_states:{academic_cv:"ready",transcripts:"ready"}}).state,"ready");
 assert.equal(documentReadiness({...base,document_requirements_note:"",document_states:{academic_cv:"ready",transcripts:"ready"}}).state,"provisional");
});
test("critical risks preserve explicit blockers and do not invent submission",()=>{
 assert.equal(riskSignal(base,today),"Urgent");
 assert.equal(riskSignal({...base,document_states:{academic_cv:"not_started",transcripts:"unknown"}},today),"Confirmed gap");
 assert.equal(riskSignal({...base,status:"blocked"},today),"Blocked");
 assert.equal(riskSignal({...base,status:"submitted"},today),"Submitted");
 assert.equal(riskSignal({...base,status:"submitted",followup:"2026-11-08"},today),"Follow-up overdue");
 assert.equal(isActionable({...base,status:"submitted",followup:"2026-11-08"},today),true);
 assert.equal(isActionable({...base,status:"submitted"},today),false);
 assert.ok(priorityScore({...base,status:"submitted",followup:"2026-11-08"},today)>0);
 assert.equal(isActionable({...base,record_type:"candidate"},today),false);
 assert.ok(priorityScore({...base,priority:"high"},today)>priorityScore({...base,priority:"low"},today));
});
test("snapshot validation checks record shape, IDs and date truthfulness",()=>{
 const valid={schema_version:1,providers:[],records:[base]};
 assert.equal(validateSnapshot(valid).ok,true);
 assert.equal(validateSnapshot({...valid,records:[base,base]}).ok,false);
 assert.equal(validateSnapshot({...valid,records:[{...base,deadline:"invalid"}]}).ok,false);
 assert.equal(validateSnapshot({schema_version:1,records:[]}).ok,false);
});
test("filtering distinguishes tracked and candidate, and composes dimensions",()=>{
 const items=[base,{...base,id:"beta",record_type:"candidate",status:"unconfirmed",name:"Other faculty",deadline:null}];
 const scoped=applyRecordFilters(items,{scope:"tracked",verification:"source_verified",horizon:"7",query:"portal"},today);
 assert.deepEqual(scoped.map(r=>r.id),["alpha"]);
 assert.deepEqual(applyRecordFilters(items,{scope:"candidate"},today).map(r=>r.id),["beta"]);
 assert.deepEqual(applyRecordFilters(items,{scope:"all",horizon:"unknown"},today).map(r=>r.id),["beta"]);
});
test("optimistic draft conflict detection does not overwrite newer source state",()=>{
 const draft={base_updated_at:"2026-11-08T10:00:00Z",status:"preparing",documents:{academic_cv:"ready"}};
 assert.equal(draftState(draft,{...base,updated_at:"2026-11-08T10:00:00Z"}),"draft");
 assert.equal(draftState({...draft,_sync_status:"pending"},{...base,updated_at:"2026-11-08T10:00:00Z"}),"pending");
 assert.equal(draftState(draft,{...base,updated_at:"2026-11-09T10:00:00Z"}),"conflict");
 assert.equal(draftState({...draft,status:"submitted",_sync_status:"pending"},{...base,updated_at:"2026-11-09T10:00:00Z",status:"submitted"}),"committed");
 assert.equal(draftState({status:"preparing"},base),"needs-review");
});
test("deadline collision classification requires two actionable tracked opportunities",()=>{
 const a={...base,id:"x"};
 const b={...base,id:"y"};
 const c={...base,id:"z",record_type:"candidate"};
 assert.deepEqual(deadlineCollisions([a,b,c],today)[0],{date:"2026-11-10",ids:["x","y"],count:2});
});
test("stale data is labeled without guessing source correctness",()=>{
 assert.equal(freshnessState("2026-10-12",today).state,"stale");
 assert.equal(freshnessState("2026-11-08",today).state,"current");
 assert.equal(freshnessState(null,today).state,"unknown");
});

test("verified exact cutoff overrides same-day calendar urgency after the instant",()=>{
 const item={...base,deadline:"2027-06-01",deadline_time:"23:59",deadline_timezone:"Europe/London",
  deadline_cutoff_verified:true,deadline_cutoff_utc:"2027-06-01T22:59:00Z"};
 const before=Date.parse("2027-06-01T22:58:00Z"),after=Date.parse("2027-06-01T22:59:00Z");
 assert.equal(isActionable(item,"2027-06-01",before),true);
 assert.equal(isActionable(item,"2027-06-01",after),false);
 assert.equal(riskSignal(item,"2027-06-01",after),"Cutoff elapsed");
 assert.equal(priorityScore(item,"2027-06-01",after),-100);
 assert.equal(validateSnapshot({schema_version:1,providers:[],records:[item]}).ok,true);
 assert.equal(validateSnapshot({schema_version:1,providers:[],records:[{...item,deadline_cutoff_utc:"wrong"}]}).ok,false);
});

test("verified cutoff remains actionable after applicant local midnight when institution is behind",()=>{
 const record={...base,deadline:"2027-06-01",deadline_time:"23:59",deadline_timezone:"America/Los_Angeles",
  deadline_cutoff_verified:true,deadline_cutoff_utc:"2027-06-02T06:59:00Z"};
 const now=Date.parse("2027-06-02T01:00:00Z"),today="2027-06-02";
 assert.equal(daysUntil(record.deadline,today),-1);
 assert.equal(isActionable(record,today,now),true);
 assert.notEqual(riskSignal(record,today,now),"Expired");
 assert.ok(priorityScore(record,today,now)>=100);
 assert.equal(applyRecordFilters([record],{horizon:"expired"},today,now).length,0);
 assert.equal(applyRecordFilters([record],{horizon:"7"},today,now).length,1);
 assert.equal(isActionable(record,today,Date.parse("2027-06-02T07:00:00Z")),false);
});
