import test from "node:test";
import assert from "node:assert/strict";
import {runtimeCapabilities} from "../site/modules/runtime-capabilities.mjs";

test("static Pages never claims a private API or hosted authentication",()=>{
  const result=runtimeCapabilities();
  assert.equal(result.mode,"static");
  assert.deepEqual(result.available,["public_evidence"]);
  assert.ok(result.blocked.includes("cloud_hosted"));
  assert.ok(result.blocked.includes("agents"));
});

test("verified browser model enables direct chat but no privileged tools",()=>{
  const result=runtimeCapabilities({browserModelVerified:true});
  assert.equal(result.mode,"browser-local");
  assert.ok(result.available.includes("direct_chat"));
  for(const id of ["private_state","agents","automations","cloud_hosted"])assert.ok(result.blocked.includes(id));
});

test("private service exposes agents and persistence, not OIDC cloud mode",()=>{
  const result=runtimeCapabilities({privateConnected:true,privateModelVerified:true,browserModelVerified:true});
  assert.equal(result.mode,"private");
  for(const id of ["direct_chat","private_state","agents","automations"])assert.ok(result.available.includes(id));
  assert.ok(result.blocked.includes("cloud_hosted"));
});

test("private provider readiness is separate from server reachability",()=>{
  const result=runtimeCapabilities({privateConnected:true,privateModelVerified:false});
  assert.ok(result.blocked.includes("direct_chat"));
  assert.ok(result.available.includes("private_state"));
});
