import test from "node:test";
import assert from "node:assert/strict";
import {candidateAssessment,candidateQueue} from "../site/modules/discovery.mjs";

const today="2026-11-10";
const candidate=(id,extra={})=>({id,record_type:"candidate",name:id,institution:"Example University",verification:"unverified",...extra});

test("candidate classification never infers admission or funding readiness",()=>{
  const reviewed=candidateAssessment(candidate("a",{verification:"source_verified",source_url:"https://example.edu"}),today);
  assert.equal(reviewed.stage,"reviewed");
  assert.ok(reviewed.reasons.includes("Funding not established"));
  assert.ok(reviewed.reasons.includes("Closing date unrecorded"));
  assert.match(reviewed.action,/promotion/);
});

test("expired, rolling, staged and unverified candidates are distinguished",()=>{
  assert.equal(candidateAssessment(candidate("closed",{deadline:"2026-11-09",verification:"source_verified",source_url:"https://example.edu"}),today).stage,"closed");
  assert.equal(candidateAssessment(candidate("rolling",{deadline:"2020-01-01",deadline_type:"rolling",verification:"source_verified",source_url:"https://example.edu"}),today).stage,"reviewed");
  assert.equal(candidateAssessment(candidate("staged",{promoted:true,deadline:"2020-01-01"}),today).stage,"staged");
  assert.equal(candidateAssessment(candidate("needs",{verification:"source_verified"}),today).stage,"review");
});

test("filter and ordering are deterministic, search ignores missing optional data",()=>{
  const records=[candidate("review"),candidate("closed",{deadline:"2025-01-01"}),candidate("ready",{verification:"owner_verified",source_url:"https://example.edu",deadline:"2027-01-01"}),{record_type:"tracked",id:"application"}];
  const result=candidateQueue(records,today);
  assert.equal(result.counts.total,3);
  assert.deepEqual(result.items.map(x=>x.record.id),["ready","review","closed"]);
  assert.deepEqual(candidateQueue(records,today,{stage:"review",query:"rev"}).items.map(x=>x.record.id),["review"]);
  assert.deepEqual(candidateQueue(records,today,{query:"missing"}).items,[]);
});

test("invalid records and unknown filters fail explicitly",()=>{
  assert.throws(()=>candidateAssessment({id:"bad",record_type:"tracked"},today));
  assert.throws(()=>candidateQueue({},today));
  assert.throws(()=>candidateQueue([],today,{stage:"invalid"}));
});
