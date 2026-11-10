import test from "node:test";
import assert from "node:assert/strict";
import {renderEvaluations} from "../site/modules/evaluations.mjs";

const report={
 schema_version:1,status:"descriptive_only",sample_truncated:false,sample_limit:500,
 generated_at:"2026-11-10T10:00:00Z",
 summary:{calls:2,failed:1,citation_audits:1,unknown_reference_links:1,unverified_reference_links:2},
 providers:[{provider_id:"ollama",calls:2,failed:1,latency_p95_ms:1800,unknown_reference_links:1}],
 agents:[{agent_id:"deadline_auditor",calls:2,failed:1,latency_p95_ms:1800,unknown_reference_links:1}],
 recent_traces:[{run_id:"a".repeat(32),agent_id:"deadline_auditor",provider_id:"ollama",
  model:"local",created_at:"2026-11-10T10:00:00Z",status:"proposed",latency_ms:1800,
  prompt_contract_id:"phd_evidence_analysis_v1"}],
 workflow_summaries:[{run_id:"b".repeat(32),workflow_id:"deadline_watch",
  completed_stages:1,stage_count:2,status:"failed"}],
 limitations:"No semantic entailment or provider pricing is inferred"
};

test("distinguishes unavailable and empty sample without inventing metrics",()=>{
 assert.match(renderEvaluations({error:"unavailable"}),/role="alert"/);
 const empty=renderEvaluations({report:{...report,status:"no_observations",
  providers:[],agents:[],recent_traces:[],workflow_summaries:[],summary:{calls:0,failed:0}}});
 assert.match(empty,/No agent executions recorded/);
 assert.match(empty,/Not measured/);
});

test("renders measured agent, provider and workflow traces with filters",()=>{
 const html=renderEvaluations({report});
 assert.match(html,/Agent evaluations/);
 assert.match(html,/Unknown citation links/);
 assert.match(html,/1,800 ms/);
 assert.match(html,/deadline_watch/);
 assert.match(html,/phd_evidence_analysis_v1/);
 assert.match(html,/data-os-eval-provider/);
 assert.match(html,/No semantic entailment or provider pricing is inferred/);
 assert.match(renderEvaluations({report,provider:"unregistered"}),/option value="all" selected/);
});

test("untrusted model and agent strings are escaped",()=>{
 const html=renderEvaluations({report:{...report,
  agents:[{...report.agents[0],agent_id:"<script>alert(1)</script>"}],
  recent_traces:[{...report.recent_traces[0],model:'<img src=x onerror=alert(1)>'}]}});
 assert.ok(!html.includes("<script>"));
 assert.ok(!html.includes("<img"));
 assert.match(html,/&lt;script&gt;/);
 assert.match(html,/&lt;img/);
});
