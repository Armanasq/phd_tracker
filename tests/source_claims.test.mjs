import test from "node:test";
import assert from "node:assert/strict";
import {claimCandidates,renderSourceClaims} from "../site/modules/source-claims.mjs";

const observed=[
  {id:9,application_id:"APP1",source_url:"https://university.example/phd",observed_at:"2026-11-10",
   content_sha256:"a".repeat(64),excerpt_available:1,text_drift:"visible_text_changed"},
  {id:8,application_id:"APP1",source_url:"https://university.example/phd",observed_at:"2026-11-09",
   content_sha256:"b".repeat(64),excerpt_available:0},
];

test("only captured observations can be chosen for claim evidence",()=>{
  assert.deepEqual(claimCandidates(observed).map(x=>x.id),[9]);
  assert.throws(()=>claimCandidates({}),TypeError);
});

test("rendering observed text and quote capture is gated on an exact digest and ID",()=>{
  const without=renderSourceClaims({observations:observed});
  assert.ok(!without.includes('data-os-form="source-claim"'));
  const yes=renderSourceClaims({observations:observed,selectedId:9,sourceText:{
    id:9,content_sha256:"a".repeat(64),visible_text:"Doctoral applications close on 15 December 2026.",
    visible_text_sha256:"c".repeat(64),visible_text_truncated:false
  }});
  assert.match(yes,/data-os-form="source-claim"/);
  assert.match(yes,/Doctoral applications close/);
  assert.match(yes,/name="expected_digest"/);
  assert.match(yes,/sourceCapturedText/);
  const stale=renderSourceClaims({observations:observed,selectedId:9,sourceText:{
    id:9,content_sha256:"b".repeat(64),visible_text:"stale visible text"
  }});
  assert.doesNotMatch(stale,/stale visible text/);
  assert.ok(!stale.includes('data-os-form="source-claim"'));
});

test("claims remain explicitly unverified, and untrusted content is escaped",()=>{
  const html=renderSourceClaims({claims:[{
    application_id:'<script>script</script>',claim_type:"deadline",
    exact_quote:'<img src=x onerror=alert(1)>',candidate_value:"2026-12-15",
    source_url:"javascript:alert(1)",observation_id:1,captured_at:"2026-11-10"
  }],error:'<img src=x>',filter:"all"});
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes("<script"));
  assert.match(html,/&lt;script&gt;/);
  assert.match(html,/factual interpretation unverified/);
  assert.match(html,/Unknown|No retained source text/);
});
