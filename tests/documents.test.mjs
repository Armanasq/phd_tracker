import test from "node:test";
import assert from "node:assert/strict";
import {portfolioDocumentInventory} from "../site/modules/documents.mjs";

const row=(id,other={})=>({id,name:id,record_type:"tracked",status:"preparing",documents:["academic_cv"],document_states:{academic_cv:"unknown"},verification:"unverified",...other});

test("aggregates shared requirements without assuming readiness",()=>{
 const result=portfolioDocumentInventory([
  row("one",{documents:["academic_cv","transcripts","academic_cv"],document_states:{academic_cv:"ready",transcripts:"not_started"}}),
  row("two",{documents:["academic_cv"],document_states:{academic_cv:"in_progress"}}),
  row("three",{documents:["academic_cv"],status:"withdrawn",document_states:{academic_cv:"ready"}}),
  {id:"lead",record_type:"candidate",documents:["transcripts"]}
 ]);
 assert.equal(result.summary.tracked,3);
 assert.equal(result.summary.active,2);
 assert.equal(result.summary.listed_requirements,3);
 assert.equal(result.summary.ready,1);
 assert.equal(result.summary.in_progress,1);
 assert.equal(result.summary.not_started,1);
 assert.equal(result.items.find(x=>x.id==="academic_cv").active,2);
 assert.equal(result.items.find(x=>x.id==="academic_cv").reported_ready,1);
});

test("missing document requirements remain unconfirmed, not missing files",()=>{
 const report=portfolioDocumentInventory([row("unknown",{documents:[]}),row("partially-recorded",{documents:["academic_cv"],document_states:{}})]);
 assert.equal(report.summary.unconfirmed_requirements,1);
 assert.equal(report.summary.unknown,1);
 assert.equal(report.summary.not_started,0);
});

test("source-reviewed application does not imply document list verified",()=>{
 const report=portfolioDocumentInventory([row("source",{verification:"source_verified",document_requirements_note:"",document_states:{academic_cv:"ready"}})]);
 assert.equal(report.items[0].verified_requirements,0);
 assert.equal(report.items[0].reported_ready,1);
});

test("invalid input fails and unknown statuses remain unknown",()=>{
 assert.throws(()=>portfolioDocumentInventory(null),TypeError);
 const report=portfolioDocumentInventory([row("bad",{document_states:{academic_cv:"fabricated_state"}})]);
 assert.equal(report.summary.unknown,1);
});
