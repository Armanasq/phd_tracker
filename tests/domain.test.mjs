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
 assert.equal(riskSignal({...base,status:"submitted"},today),"Closed");
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
 assert.equal(draftState({...draft,status:"submitted"},{...base,updated_at:"2026-11-09T10:00:00Z",status:"submitted"}),"committed");
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
