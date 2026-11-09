import test from "node:test";
import assert from "node:assert/strict";
import {assessApplication,portfolioReadiness} from "../site/modules/readiness.mjs";

const today="2026-11-10";
const base={id:"A",record_type:"tracked",name:"Robotics PhD",status:"preparing",verification:"unverified",deadline:"2026-11-12",documents:["academic_cv","transcripts"],document_states:{academic_cv:"ready",transcripts:"unknown"},source_url:"https://example.edu/phd"};

test("unknown is not missing or ready; source and cutoff proof remain open",()=>{
 const r=assessApplication(base,today);
 assert.equal(r.phase,"active");
 assert.ok(r.tasks.some(x=>x.key==="document:transcripts"&&x.kind==="evidence"));
 assert.equal(r.knownPreparation,0);
 assert.ok(r.tasks.some(x=>x.key==="deadline_cutoff"));
 assert.ok(r.tasks.some(x=>x.key==="source_review"));
 assert.ok(!r.tasks.some(x=>/ready to submit/i.test(x.label)));
});
test("explicit document gaps remain preparation tasks",()=>{
 const r=assessApplication({...base,document_states:{academic_cv:"not_started",transcripts:"in_progress"}},today);
 assert.equal(r.knownPreparation,2);
 assert.equal(r.tasks.find(x=>x.key==="document:academic_cv").kind,"preparation");
});
test("candidates and closed outcomes are excluded from active work",()=>{
 const p=portfolioReadiness([base,{...base,id:"C",record_type:"candidate"},{...base,id:"D",status:"offer"}],today);
 assert.deepEqual(p.active.map(x=>x.id),["A"]);
 assert.equal(p.closed.length,1);
 assert.equal(p.totals.tracked,2);
});
test("blocked and expired remain halted; submitted only receives receipt and follow-up checks",()=>{
 const p=portfolioReadiness([{...base,id:"B",status:"blocked"},{...base,id:"X",deadline:"2026-11-09"},{...base,id:"S",status:"submitted",followup:"2026-11-08"}],today);
 assert.equal(p.active.length,0);
 assert.equal(p.halted.length,2);
 assert.deepEqual(p.submitted[0].tasks.map(x=>x.key),["submitted_followup","receipt"]);
 assert.equal(p.totals.submittedWithoutReceipt,1);
});
test("same-day pressure and shared document demand count only active applications",()=>{
 const p=portfolioReadiness([base,{...base,id:"B",documents:["transcripts"],document_states:{transcripts:"not_started"}}],today);
 assert.deepEqual(p.collisions.map(x=>x.count),[2]);
 assert.equal(p.reusable.find(x=>x.key==="transcripts").required,2);
 assert.equal(p.totals.knownDocumentGaps,1);
});
test("deadline ordering is deterministic; invalid dates fail closed",()=>{
 const p=portfolioReadiness([{...base,id:"late",deadline:"2027-01-01"},{...base,id:"near",deadline:"2026-11-10"}],today);
 assert.deepEqual(p.active.map(x=>x.id),["near","late"]);
 assert.equal(assessApplication({...base,deadline:null},today).tasks.some(x=>x.key==="deadline_date"),true);
 assert.equal(assessApplication(base,"2026-02-30"),null);
 assert.throws(()=>portfolioReadiness({},today),TypeError);
});
