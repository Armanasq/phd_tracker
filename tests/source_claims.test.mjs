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

test("visible-text diff is explicitly provisional and safely escaped",()=>{
  const sample={id:9,content_sha256:"a".repeat(64),visible_text:"Application deadline changed from 15 to 20 December 2026."};
  const comparison={observation_id:9,status:"visible_text_changed",comparison_complete:true,
    possible_topics:["deadline"],changes:[{type:"replace",before:"15",after:"20"}],
    notice:"Text changes do not constitute official fact verification"};
  const screen=renderSourceClaims({observations:observed,selectedId:9,sourceText:sample,diff:comparison});
  assert.match(screen,/Compare previous fetch/);
  assert.match(screen,/Visible text comparison/);
  assert.match(screen,/Possible review topics: deadline/);
  assert.match(screen,/Text changes do not constitute official fact verification/);
  const untrusted=renderSourceClaims({observations:observed,selectedId:9,sourceText:sample,
    diff:{...comparison,changes:[{type:"replace",before:"<script>bad</script>",after:"<img onerror=alert(1)>"}]}});
  assert.ok(!untrusted.includes("<script>"));
  assert.ok(!untrusted.includes("<img"));
});

test("every source-claim owner verdict remains explicitly provisional",()=>{
  for(const decision of [null,"needs_recheck","owner_interpretation_supported","owner_interpretation_rejected"]){
    const rendered=renderSourceClaims({claims:[{
      id:17,observation_id:9,application_id:"APP1",source_url:"https://uni.example",
      source_digest:"a".repeat(64),quote_digest:"b".repeat(64),claim_type:"deadline",
      exact_quote:"Institutional deadline shown on public website.",
      candidate_value:"2026-12-15",captured_at:"2026-11-10",
      owner_review_decision:decision
    }]});
    assert.match(rendered,/data-os-form="source-claim-review"/);
    assert.match(rendered,/name="claim_id" value="17"/);
    assert.match(rendered,/name="expected_quote_digest"/);
    assert.match(rendered,/factual interpretation unverified/);
    assert.match(rendered,/no automatic official-fact verification/);
  }
});

test("owner audit history displays dated decisions without leaking HTML",()=>{
  const claim={id:17,observation_id:9,application_id:"APP1",source_url:"https://university.example",
    source_digest:"a".repeat(64),quote_digest:"b".repeat(64),claim_type:"deadline",
    exact_quote:"Institutional deadline from captured source.",
    candidate_value:"2026-12-15",captured_at:"2026-11-10"};
  const result=renderSourceClaims({claims:[claim],reviewHistory:{
    claim_id:17,reviews:[{id:22,decision:"owner_interpretation_supported",
      rationale:"<script>untrusted rationale</script>",reviewed_at:"2026-11-10"}]
  }});
  assert.match(result,/Owner review history/);
  assert.match(result,/&lt;script&gt;untrusted rationale&lt;\/script&gt;/);
  assert.ok(!result.includes("<script>"));
  assert.match(result,/factual interpretation unverified/);
});
