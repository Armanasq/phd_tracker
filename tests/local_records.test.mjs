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

test("publishing additional opportunities preserves existing fork records and strips private fields",()=>{
 const existing={
  id:"FORK-1",name:"Existing official programme",record_type:"tracked",
  verification:"source_verified",status:"preparing",source_url:"https://university.example.edu/phd?tracking=1",
  source_date:"2026-11-09",evidence:"Reviewed official academic page",
  documents:["academic_cv"],document_states:{academic_cv:"ready"},
  notes:"PRIVATE owner note",receipt:"https://university.example.edu/private?token=1",
  next_step:"Confirm official portal deadline",
 };
 const row=createLocalRecord({...input,notes:"Do not publish",status:"preparing"},id);
 const source=exportIndependentSource([row],"2026-11-09","Europe/Berlin",[existing]);
 assert.deepEqual(source.records.map(r=>r.id),["FORK-1",id]);
 assert.equal(source.records[0].verification,"source_verified");
 assert.equal(source.records[0].source_url,"https://university.example.edu/phd");
 assert.equal(source.records[0].document_states.academic_cv,"ready");
 assert.equal(source.records[0].status,"preparing");
 assert.equal(source.records[1].verification,"unverified");
 assert.ok(!JSON.stringify(source).includes("PRIVATE"));
 assert.ok(!JSON.stringify(source).includes("token=1"));
 assert.ok(!JSON.stringify(source).includes("Do not publish"));
 assert.throws(()=>exportIndependentSource([row],"2026-11-09","Europe/Berlin",[{...existing,id}]),/Duplicate opportunity/);
 assert.throws(()=>exportIndependentSource([],"2026-11-09","UTC",[{...existing,source_date:null}]),/source date/);
});

test("independent source re-export preserves verified final cutoff fields but not derived UTC state",()=>{
 const existing={
  id:"FORK-CUTOFF",name:"Illustrative official call",record_type:"tracked",
  deadline:"2027-06-01",deadline_type:"final",deadline_time:"23:59",
  deadline_timezone:"Europe/London",deadline_cutoff_verified:true,
  deadline_cutoff_utc:"2027-06-01T22:59:00Z",
  deadline_cutoff_evidence:"Official page states closing at 23:59 London",
  source_url:"https://example.edu/call",source_date:"2026-11-09",
  evidence:"Original official page reviewed",verification:"source_verified",
 };
 const reexported=exportIndependentSource([],"2026-11-09","UTC",[existing]);
 const record=reexported.records[0];
 assert.equal(record.deadline_cutoff_verified,true);
 assert.equal(record.deadline_time,"23:59");
 assert.equal(record.deadline_timezone,"Europe/London");
 assert.equal(record.deadline_cutoff_evidence,existing.deadline_cutoff_evidence);
 assert.equal("deadline_cutoff_utc" in record,false);
 assert.throws(()=>exportIndependentSource([],"2026-11-09","UTC",[{...existing,deadline_timezone:null}]),/paired/);
 assert.throws(()=>exportIndependentSource([],"2026-11-09","UTC",[{...existing,deadline_cutoff_evidence:""}]),/proof/);
});

test("device-only recorded clocks stay unverified when exported to a fork",()=>{
 const row=createLocalRecord({...input,deadline_time:"23:59",deadline_timezone:"Europe/London"},id);
 assert.equal(row.deadline_time,"23:59");
 assert.equal(row.deadline_timezone,"Europe/London");
 assert.equal(row.deadline_cutoff_verified,false);
 const exported=exportIndependentSource([row],"2026-11-09","Europe/London").records[0];
 assert.equal(exported.deadline_time,"23:59");
 assert.equal(exported.deadline_timezone,"Europe/London");
 assert.equal(exported.verification,"unverified");
 assert.notEqual(exported.deadline_cutoff_verified,true);
 assert.equal(Object.hasOwn(exported,"deadline_cutoff_utc"),false);
 for(const change of ([{deadline_timezone:""},{deadline_time:""},{deadline_time:"24:03"},{deadline_timezone:"Nowhere/Invalid"},{deadline:null}])){
  assert.throws(()=>createLocalRecord({...input,deadline_time:"23:59",deadline_timezone:"Europe/London",...change},id),TypeError);
 }
});
