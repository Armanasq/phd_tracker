import test from "node:test";
import assert from "node:assert/strict";
import {assessOnboarding,renderOnboarding,SETUP_MODES} from "../site/modules/onboarding.mjs";

const snapshot={
  instance:{repository:"independent/phd_tracker",type:"independent",data_mode:"starter"},
  records:[],hosted_ai:{state:"not_configured"}
};

test("all supported setup modes have explicit distinct decision contracts",()=>{
  assert.equal(SETUP_MODES.length,5);
  assert.equal(new Set(SETUP_MODES.map(([id])=>id)).size,5);
  assert.equal(assessOnboarding(snapshot,{mode:"unknown"}).mode,"pages");
  for(const [mode] of SETUP_MODES){
    const report=assessOnboarding(snapshot,{mode});
    assert.equal(report.mode,mode);
    assert.ok(report.steps.length>=4);
  }
});

test("fork source mode does not infer institutional evidence accuracy",()=>{
  const initial=assessOnboarding(snapshot);
  assert.equal(initial.steps.find(s=>s.id==="data").status,"action");
  const configured=assessOnboarding({...snapshot,instance:{...snapshot.instance,data_mode:"source"},records:[{id:"candidate"}]});
  const evidence=configured.steps.find(s=>s.id==="data");
  assert.equal(evidence.status,"observed");
  assert.match(evidence.detail,/still require verification/);
  assert.doesNotMatch(renderOnboarding(configured),/Verified facts/);
});

test("browser inference and private runtime remain separate capabilities",()=>{
  const local=assessOnboarding(snapshot,{mode:"browser-local",browserModelVerified:true});
  assert.equal(local.steps.find(s=>s.id==="model").status,"verified");
  const unavailable=assessOnboarding(snapshot,{mode:"private",browserModelVerified:true,privateConnected:false});
  assert.equal(unavailable.steps.find(s=>s.id==="runtime").status,"action");
  const available=assessOnboarding(snapshot,{mode:"private",privateConnected:true});
  assert.equal(available.steps.find(s=>s.id==="runtime").status,"verified");
});

test("hosted Actions reports are not proof of credentials or cloud readiness",()=>{
  const hosted=assessOnboarding({...snapshot,hosted_ai:{state:"current"}},{mode:"actions"});
  assert.equal(hosted.steps.find(s=>s.id==="actions").status,"observed");
  const cloud=assessOnboarding(snapshot,{mode:"cloud",privateConnected:true,browserModelVerified:true});
  assert.equal(cloud.steps.find(s=>s.id==="cloud").status,"blocked");
  assert.match(renderOnboarding(cloud),/Not implemented/);
});

test("public renderer escapes hostile repository identifiers and never includes secrets",()=>{
  const report=assessOnboarding({...snapshot,instance:{repository:'<script>alert(1)</script>',data_mode:"starter"}});
  assert.equal(report.repository,"");
  const html=renderOnboarding(report);
  assert.ok(!html.includes("<script"));
  assert.ok(!html.includes("Actions secrets</a>"));
  assert.ok(html.includes("Repository links are unavailable"));
  assert.match(renderOnboarding(assessOnboarding(snapshot)),/independent\/phd_tracker/);
});
