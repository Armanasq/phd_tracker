import test from "node:test";
import assert from "node:assert/strict";
import {createLocalRecord,normalizeLocalRecords,mergeLocalRecords,exportIndependentSource,validateEvidenceUrl} from "../site/modules/local-records.mjs";

const id="LOCAL-11111111-1111-4111-8111-111111111111";
const id2="LOCAL-22222222-2222-4222-8222-222222222222";
const input={name:"Robotics doctoral position",country:"DE",deadline:"2027-01-31",source_url:"https://example.edu/phd",next_step:"Verify official call"};

test("new opportunities begin as unverified local-only records with no inferred documents",()=>{
 const row=createLocalRecord(input,id);
 assert.equal(row.id,id);
 assert.equal(row.record_type,"tracked");
 assert.equal(row.local_only,true);
 assert.equal(row.status,"unconfirmed");
 assert.equal(row.verification,"unverified");
 assert.equal(row.document_states.academic_cv,undefined);
 assert.equal(row.deadline_type,"unverified");
 assert.equal(row.submission_receipt,"");
 assert.equal(normalizeLocalRecords([row])[0].source_url,"https://example.edu/phd");
});

test("invalid deadlines, mailbox URLs, private text, unsupported states and unsafe IDs fail closed",()=>{
 for(const value of ["2027-02-30","tomorrow","2026-13-01"])
  assert.throws(()=>createLocalRecord({...input,deadline:value},id),/deadline/);
 for(const source_url of ["javascript:alert(1)","http://example.edu","https://mail.google.com/mail/u/0/#x","https://user:pass@example.edu/"])
  assert.throws(()=>validateEvidenceUrl(source_url),TypeError);
 assert.throws(()=>createLocalRecord({...input,name:"Prof test@example.edu"},id),/name/);
 assert.throws(()=>createLocalRecord({...input,status:"submitted_without_receipt"},id),/workflow/);
 assert.throws(()=>createLocalRecord(input,"../bad"),/ID/);
 assert.throws(()=>createLocalRecord({...input,documents:["unrecognised"]},id),/document/);
 assert.throws(()=>normalizeLocalRecords([createLocalRecord(input,id),createLocalRecord(input,id)]),/Duplicate/);
 assert.throws(()=>normalizeLocalRecords([createLocalRecord(input,id)],[id]),/Duplicate/);
});

test("import merges only new local IDs and never overwrites existing records",()=>{
 const first=createLocalRecord(input,id);
 const changed=createLocalRecord({...input,name:"Conflicting title"},id);
 const second=createLocalRecord({...input,name:"New Lab"},id2);
 const merged=mergeLocalRecords([first],[changed,second]);
 assert.equal(merged.imported,1);
 assert.equal(merged.skipped,1);
 assert.equal(merged.records.find(x=>x.id===id).name,input.name);
 assert.equal(merged.records.length,2);
 assert.throws(()=>mergeLocalRecords([], [first], [id]),/Duplicate/);
});

test("GitHub source export excludes local notes, receipts and private workflow state",()=>{
 const row=createLocalRecord({...input,notes:"Confidential planning",status:"preparing",receipt:"https://example.edu/private/receipt",documents:["academic_cv"]},id);
 const result=exportIndependentSource([row],"2026-11-09","Europe/Berlin");
 assert.equal(result.records.length,1);
 assert.deepEqual(result.records[0].documents,["academic_cv"]);
 assert.equal(result.schema_version,1);
 const encoded=JSON.stringify(result);
 assert.ok(!encoded.includes("Confidential planning"));
 assert.ok(!encoded.includes("receipt"));
 assert.ok(!encoded.includes('"status":"preparing"'));
 assert.ok(encoded.includes('"source_url":"https://example.edu/phd"'));
});

test("public exports drop URL tokens, fragments and personal next steps",()=>{
 const row=createLocalRecord({...input,source_url:"https://example.edu/phd?id=123&token=private#account",next_step:"Do not disclose my planning"},id);
 const exported=JSON.stringify(exportIndependentSource([row],"2026-11-09"));
 assert.ok(exported.includes('"source_url":"https://example.edu/phd"'));
 assert.ok(!exported.includes("token=private"));
 assert.ok(!exported.includes("Do not disclose"));
 assert.ok(!exported.includes('"next_step"'));
});
