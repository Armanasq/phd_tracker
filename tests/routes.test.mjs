import test from "node:test";
import assert from "node:assert/strict";
import {VIEWS,resolveWorkspaceRoute} from "../site/modules/routes.mjs";

test("each public route has unique stable identity and title",()=>{
  const ids=VIEWS.map(x=>x[0]);
  assert.equal(new Set(ids).size,ids.length);
  assert.equal(ids.length,24);
  assert.ok(VIEWS.every(x=>x.length===3&&x.every(y=>typeof y==="string"&&y)));
});

test("legacy deep links resolve without exposing undefined views",()=>{
  const entries={
    "#first-run":"onboarding","#get-started":"onboarding","#setup":"deployment","#runtime":"deployment","#research":"discovery","#dossier":"documents",
    "#providers":"settings","#models":"settings","#copilot":"ai",
    "#workflows":"automations","#source-drift":"source-observations","#observations":"source-observations","#home":"dashboard","#verification":"review"
  };
  for(const [source,target] of Object.entries(entries))assert.equal(resolveWorkspaceRoute(source),target);
});

test("malformed and unsupported hashes safely resolve to dashboard",()=>{
  for(const hash of ["","#","#[object Object]","#/../../api/secrets","#does-not-exist","#ai?test=1","#%3Cscript%3E"]) {
    assert.equal(resolveWorkspaceRoute(hash),"dashboard");
  }
  assert.equal(resolveWorkspaceRoute("#discovery"),"discovery");
});
