import test from "node:test";
import assert from "node:assert/strict";
import {auditWorkspace,sourceCoverage} from "../site/modules/assurance.mjs";

const today="2026-11-09";
const record={id:"R-1",name:"Robotics doctorate",record_type:"tracked",status:"preparing",verification:"needs_review",deadline:"2026-11-11",document_states:{cv:"unknown",transcripts:"not_started"},source_url:"",duplicate_submission_advisory:true};
const sample=records=>({schema_version:1,as_of:today,records,providers:[{name:"limited-feed",health:"degraded"}]});

test("audit makes missing, unknown, source, cutoff and route uncertainty distinct",()=>{
 const report=auditWorkspace(sample([record]),today);
 assert.equal(report.totals.tracked,1);
 assert.equal(report.totals.documentsUnknown,1);
 assert.equal(report.totals.documentsNotStarted,1);
 assert.ok(report.queue.some(x=>x.title==="Cutoff hour not structurally verified"));
 assert.ok(report.queue.some(x=>x.title==="Possible duplicate route"));
 assert.ok(report.queue.some(x=>x.title==="Official source link missing"));
 assert.equal(report.providers.degraded.length,1);
});
test("submitted state without receipt is not treated as confirmed",()=>{
 const report=auditWorkspace(sample([{...record,status:"submitted"}]),today);
 assert.equal(report.totals.receiptsAbsent,1);
 assert.equal(report.counts.submission,1);
 assert.equal(report.counts.documents,0);
});
test("elapsed deadlines are not submissions and archived candidates are excluded",()=>{
 const report=auditWorkspace(sample([{...record,deadline:"2026-11-01"},{...record,id:"R-2",status:"archived"},{...record,id:"R-3",record_type:"candidate"}]),today);
 assert.equal(report.totals.tracked,2);
 assert.ok(report.queue.some(x=>x.title==="Recorded date elapsed"));
 assert.equal(report.queue.some(x=>x.record_id==="R-2"||x.record_id==="R-3"),false);
});
test("worksheet row counts are separate from application counts",()=>{
 const report=sourceCoverage({coverage:{workbook_audit_as_of:"2026-11-06",totals:{tracked:109},worksheets:[{name:"Action list",populated_rows:185}]}});
 assert.equal(report.totals.tracked,109);
 assert.equal(report.sheets[0].populated_rows,185);
 assert.equal(report.asOf,"2026-11-06");
});
