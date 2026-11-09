import test from "node:test";
import assert from "node:assert/strict";
import {hostedAdvisories,hostedStatus} from "../site/modules/hosted-ai.mjs";
const today="2026-11-10";
const sample={records:[{id:"A1",record_type:"tracked",status:"unconfirmed"},{id:"C1",record_type:"candidate",status:"unconfirmed"}],hosted_ai:{state:"current",status:"unverified_model_proposal",observation_date:today,source_digest:"a".repeat(64),items:[{id:"A1",category:"source_review",priority:"high"}]}};
test("current bounded evidence priorities display without inventing proof",()=>{
 assert.deepEqual(hostedAdvisories(sample,today),[{id:"A1",category:"source_review",priority:"high"}]);
 assert.equal(hostedAdvisories(sample,"2026-11-11").length,0);
 assert.equal(hostedAdvisories({...sample,hosted_ai:{...sample.hosted_ai,state:"stale_or_invalid"}},today).length,0);
});
test("unsupported records, categories, priority and duplicates fail closed",()=>{
 for(const bad of [[{id:"UNKNOWN",category:"source_review",priority:"high"}],[{id:"C1",category:"source_review",priority:"high"}],[{id:"A1",category:"admitted",priority:"high"}],[{id:"A1",category:"source_review",priority:"extreme"}],sample.hosted_ai.items.concat(sample.hosted_ai.items)]){
  assert.deepEqual(hostedAdvisories({...sample,hosted_ai:{...sample.hosted_ai,items:bad}},today),[]);
 }
});
test("state and observation dates are disclosed",()=>{
 assert.match(hostedStatus(null,today),/No hosted/);
 assert.match(hostedStatus({state:"stale_or_invalid"},today),/stale/);
 assert.match(hostedStatus({...sample.hosted_ai,observation_date:"2026-11-09"},today),/no longer current/);
});
