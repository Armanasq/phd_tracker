import test from "node:test";
import assert from "node:assert/strict";
import {observationSummary,observationLink,renderSourceObservations} from "../site/modules/source-observations.mjs";

test("unreviewed byte drift remains visible after later unchanged fetch",()=>{
  const records=[
    {application_id:"A",source_url:"https://uni.example/app",observed_at:"2026-11-08T10:00:00Z",drift:"source_bytes_changed_needs_review"},
    {application_id:"A",source_url:"https://uni.example/app",observed_at:"2026-11-09T10:00:00Z",drift:"unchanged_bytes"},
    {application_id:"B",source_url:"https://uni.example/other",observed_at:"2026-11-09T12:00:00Z",drift:"source_bytes_changed_needs_review"},
    {application_id:"C",source_url:"https://uni.example/unavailable",observed_at:"2026-11-09T13:00:00Z",drift:"unavailable_no_source_conclusion"},
    {application_id:"D",source_url:"https://uni.example/legacy",observed_at:"2026-11-09T14:00:00Z",drift:null},
    {application_id:"E",source_url:"https://uni.example/baseline",observed_at:"2026-11-09T15:00:00Z",drift:"baseline_only"}
  ];
  const result=observationSummary(records);
  assert.equal(result.sources,5);
  assert.deepEqual(result.counts,{changed:2,pending:2,unavailable:1,unchanged:1,baseline:1,legacy:1});
  const changed=renderSourceObservations({records,filter:"changed"});
  assert.match(changed,/>B<\/strong>/);
  assert.match(changed,/>A<\/strong>/);
  assert.match(changed,/Byte drift requires owner review/);
  assert.match(changed,/manual review/);
  assert.doesNotMatch(changed,/automatically verified/i);
});

test("source observation links reject secrets and non-HTTPS links",()=>{
  assert.equal(observationLink("https://university.example/program"),"https://university.example/program");
  for(const unsafe of ["javascript:alert(1)","http://university.example","https://university.example/?key=secret",
    "https://user:secret@university.example","https://localhost/private"]){
    assert.equal(observationLink(unsafe),"");
  }
});

test("rendering escapes untrusted source data, preserves unknown states",()=>{
  const view=renderSourceObservations({records:[{
    application_id:'<img src=x onerror=alert(1)>',source_url:"javascript:alert(1)",
    observed_at:"2026-11-10",drift:null,http_status:null
  }],error:'<script>bad</script>'});
  assert.ok(view.includes("&lt;img"));
  assert.ok(view.includes("Legacy observation"));
  assert.ok(view.includes("Recorded URL unavailable"));
  assert.ok(!view.includes("<img"));
  assert.ok(!view.includes("<script"));
  assert.throws(()=>observationSummary({}),TypeError);
});

test("reviewing a particular changed observation resolves only that observation",()=>{
  const records=[
    {id:11,application_id:"A",source_url:"https://uni.example/app",
     observed_at:"2026-11-08T10:00:00Z",drift:"source_bytes_changed_needs_review",
     content_sha256:"a".repeat(64),review_decision:"reviewed_no_fact_change"},
    {id:12,application_id:"A",source_url:"https://uni.example/app",
     observed_at:"2026-11-09T10:00:00Z",drift:"unchanged_bytes"},
  ];
  assert.equal(observationSummary(records).counts.pending,0);
  const queue=renderSourceObservations({records,filter:"changed"});
  assert.doesNotMatch(queue,/>A<\/strong>/);
  records.push({id:13,application_id:"A",source_url:"https://uni.example/app",
    observed_at:"2026-11-10T10:00:00Z",drift:"source_bytes_changed_needs_review",
    content_sha256:"b".repeat(64),review_decision:"needs_follow_up"});
  const next=observationSummary(records);
  assert.equal(next.counts.pending,1);
  const review=renderSourceObservations({records,filter:"changed"});
  assert.match(review,/name="observation_id" value="13"/);
  assert.match(review,/name="expected_digest"/);
  assert.match(review,/owner review/i);
});
