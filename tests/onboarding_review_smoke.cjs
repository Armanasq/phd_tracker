'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const net = require('node:net');
const {spawn,spawnSync} = require('node:child_process');
const {chromium} = require('playwright');

const root=process.cwd();

async function port() {
  const socket=net.createServer();
  await new Promise(resolve=>socket.listen(0,'127.0.0.1',resolve));
  const value=socket.address().port;
  await new Promise(resolve=>socket.close(resolve));
  return value;
}

async function serveStatic() {
  const base=path.resolve(root,'site');
  const server=http.createServer(async(req,res)=>{
    try {
      const target=new URL(req.url,'http://localhost');
      const pathname=decodeURIComponent(target.pathname);
      const filename=path.resolve(base,'.'+(pathname==='/'?'/index.html':pathname));
      if(!filename.startsWith(base+path.sep)) {res.writeHead(403);res.end();return;}
      const data=await fs.readFile(filename);
      const ext=path.extname(filename);
      const contentType={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json'}[ext]||'application/octet-stream';
      res.writeHead(200,{'Content-Type':contentType});res.end(data);
    } catch {res.writeHead(404);res.end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,address:'http://127.0.0.1:'+server.address().port};
}

async function waitForHealth(base) {
  for(let attempt=0;attempt<70;attempt++){
    try{
      const response=await fetch(base+'/api/health');
      if(response.ok)return;
    }catch{}
    await new Promise(resolve=>setTimeout(resolve,180));
  }
  throw new Error('Private runtime did not start');
}

async function main() {
  const folder=await fs.mkdtemp(path.join(os.tmpdir(),'phd-atlas-review-'));
  const seed=String.raw`
import hashlib
import sys
from pathlib import Path
from phd_agents.store import Store
store = Store(Path(sys.argv[1]) / "state.sqlite3")
digest = hashlib.sha256(b"official source bytes").hexdigest()
text = "Doctoral applications close on 15 December 2026."
visible = hashlib.sha256(text.encode("utf-8")).hexdigest()
with store.db:
    previous = "Doctoral applications close on 11 December 2026."
    store.db.execute(
        "INSERT INTO source_observations(application_id,source_url,status,content_sha256,"
        "observed_at,http_status,content_length,drift,visible_text_sha256,"
        "visible_text_excerpt,visible_text_truncated,text_drift) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("EXAMPLE-1","https://university.example/program","fetched",
         hashlib.sha256(previous.encode()).hexdigest(),
         "2026-11-09T08:00:00+00:00",200,len(previous),"baseline_only",
         hashlib.sha256(previous.encode()).hexdigest(),previous,0,"not_comparable"),
    )
    store.db.execute(
        "INSERT INTO source_observations(application_id,source_url,status,content_sha256,"
        "observed_at,http_status,content_length,drift,visible_text_sha256,"
        "visible_text_excerpt,visible_text_truncated,text_drift) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("EXAMPLE-1","https://university.example/program","fetched",digest,
         "2026-11-10T08:00:00+00:00",200,21,"source_bytes_changed_needs_review",
         visible,text,0,"visible_text_changed"),
    )
store.put_run("agent", "deadline_auditor", "EXAMPLE-1", "proposed", "ollama", {
    "model": "synthetic-no-network", "latency_ms": 125,
    "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    "prompt_contract_id": "phd_evidence_analysis_v1",
    "text": "SYNTHETIC PRIVATE RESPONSE MUST NOT LEAK",
    "claim_audit": {"schema_version": 1, "unknown_reference_links": 1,
                    "linked_to_unverified_records": 1, "linked_to_reviewed_records": 0,
                    "unlinked_text_blocks": 1},
})
store.close()
`;
  const seeded=spawnSync('python',['-c',seed,folder],{cwd:root,encoding:'utf8'});
  if(seeded.status!==0)throw new Error('Source fixture failed: '+seeded.stderr);
  const runtimePort=await port();
  const privateUrl='http://127.0.0.1:'+runtimePort;
  const child=spawn('python',['-m','phd_agents','serve','--port',String(runtimePort)],{
    cwd:root,env:{...process.env,PHDAI_PRIVATE_DIR:folder},stdio:'ignore'
  });
  let staticSite,browser;
  try {
    staticSite=await serveStatic();
    await waitForHealth(privateUrl);
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const privatePage=await browser.newPage({viewport:{width:390,height:844}});
    const errors=[];
    privatePage.on('pageerror',e=>errors.push(e.message));
    await privatePage.goto(privateUrl+'/index.html#evaluations',{waitUntil:'networkidle'});
    await privatePage.locator('#body h1').getByText('Agent evaluations').waitFor({timeout:12000});
    await privatePage.locator('[data-os-eval-provider]').selectOption('ollama');
    assert.match(await privatePage.locator('#body').innerText(),/deadline_auditor/);
    assert.match(await privatePage.locator('#body').innerText(),/Unknown citation links/);
    const evaluation=await (await fetch(privateUrl+'/api/evaluations')).json();
    assert.equal(evaluation.summary.calls,1);
    assert.equal(evaluation.summary.unknown_reference_links,1);
    assert.equal(evaluation.summary.semantic_entailment_verified,false);
    assert.equal(evaluation.workflow_summaries.length,0);
    assert.ok(!JSON.stringify(evaluation).includes('SYNTHETIC PRIVATE RESPONSE MUST NOT LEAK'));
    await privatePage.goto(privateUrl+'/index.html#source-observations',{waitUntil:'networkidle'});
    await privatePage.locator('form[data-os-form="source-review"]').waitFor({timeout:15000});
    const form=privatePage.locator('form[data-os-form="source-review"]');
    await form.locator('[name="decision"]').selectOption('reviewed_no_fact_change');
    await form.locator('[name="note"]').fill('Reviewed the official source against the recorded deadline. Only page layout markup changed.');
    await form.locator('button[type="submit"]').click();
    await privatePage.getByText('Owner review recorded privately.',{exact:false}).waitFor({timeout:10000});
    const saved=await (await fetch(privateUrl+'/api/source-observations')).json();
    assert.equal(saved.observations[0].review_decision,'reviewed_no_fact_change');
    await privatePage.reload({waitUntil:'networkidle'});
    await privatePage.locator('#body h1').first().waitFor();
    assert.equal(await privatePage.locator('form[data-os-form="source-review"]').count(),0);
    await privatePage.goto(privateUrl+'/index.html#source-claims',{waitUntil:'networkidle'});
    await privatePage.locator('[data-os-action="load-claim-source"]').waitFor({timeout:15000});
    await privatePage.locator('[data-os-action="load-claim-source"]').click();
    await privatePage.locator('#sourceCapturedText').getByText('Doctoral applications close on 15 December 2026.').waitFor({timeout:10000});
    await privatePage.locator('[data-os-action="suggest-source-dates"]').click();
    await privatePage.getByText('Date mentions for manual review',{exact:true}).waitFor({timeout:10000});
    const candidates=await (await fetch(privateUrl+'/api/source-observations/'+saved.observations[0].id+'/candidates')).json();
    assert.equal(candidates.result.semantic_claim_verified,false);
    assert.equal(candidates.result.candidate_count,1);
    assert.equal(candidates.result.candidates[0].normalized_date,'2026-12-15');
    await privatePage.locator('[data-os-action="fill-source-candidate"]').first().click();
    const capture=privatePage.locator('form[data-os-form="source-claim"]');
    assert.equal(await capture.locator('[name="candidate_value"]').inputValue(),'2026-12-15');
    assert.match(await capture.locator('[name="quote"]').inputValue(),/Doctoral applications close on/);
    await capture.locator('[name="claim_type"]').selectOption('deadline');
    await capture.locator('[name="candidate_value"]').fill('2026-12-15');
    await capture.locator('[name="quote"]').fill('Doctoral applications close on 15 December 2026.');
    await capture.locator('button[type="submit"]').click();
    await privatePage.getByText('Exact source quotation captured privately.',{exact:false}).waitFor({timeout:10000});
    const captured=await (await fetch(privateUrl+'/api/source-claims')).json();
    assert.equal(captured.claims.length,1);
    assert.equal(captured.claims[0].verification,'source_quote_observed_not_fact_verified');
    const reviewForm=privatePage.locator('form[data-os-form="source-claim-review"]').first();
    await reviewForm.locator('[name="decision"]').selectOption('owner_interpretation_supported');
    await reviewForm.locator('[name="rationale"]').fill('The captured primary text explicitly states the date. Submission cutoff time remains unknown.');
    await reviewForm.locator('button[type="submit"]').click();
    await privatePage.getByText('Owner assessment recorded privately.',{exact:false}).waitFor({timeout:10000});
    const afterReview=await (await fetch(privateUrl+'/api/source-claims')).json();
    assert.equal(afterReview.claims[0].owner_review_decision,'owner_interpretation_supported');
    assert.equal(afterReview.claims[0].verification,'source_quote_observed_not_fact_verified');
    await privatePage.locator('[data-os-action="claim-history"]').first().click();
    await privatePage.locator('.os-review-history').getByText('The captured primary text explicitly states the date.',{exact:false}).waitFor({timeout:10000});
    await privatePage.locator('[data-os-action="load-claim-source"]').click();
    await privatePage.locator('[data-os-action="compare-claim-source"]').click();
    await privatePage.getByText('Visible text comparison',{exact:true}).waitFor({timeout:10000});
    const difference=await (await fetch(privateUrl+'/api/source-observations/'+saved.observations[0].id+'/diff')).json();
    assert.equal(difference.diff.status,'visible_text_changed');
    assert.ok(difference.diff.possible_topics.includes('deadline'));
    assert.equal(difference.diff.semantic_claim_verified,false);
    await privatePage.reload({waitUntil:'networkidle'});
    await privatePage.locator('.os-evidence-quote').getByText('Doctoral applications close on 15 December 2026.').waitFor({timeout:10000});
    assert.deepEqual(errors,[],'Private source review and claim capture JavaScript errors');
    await privatePage.close();

    const publicPage=await browser.newPage({acceptDownloads:true,viewport:{width:375,height:812}});
    const publicErrors=[];
    publicPage.on('pageerror',e=>publicErrors.push(e.message));
    await publicPage.goto(staticSite.address+'/index.html#onboarding',{waitUntil:'networkidle'});
    await publicPage.locator('#body h1').first().waitFor({timeout:12000});
    assert.match(await publicPage.locator('#body h1').innerText(),/First-run setup/i);
    await publicPage.locator('#onboardingMode').selectOption('browser-local');
    await publicPage.reload({waitUntil:'networkidle'});
    assert.equal(await publicPage.locator('#onboardingMode').inputValue(),'browser-local');
    const pending=publicPage.waitForEvent('download');
    await publicPage.locator('[data-action="export"][data-value="setup"]').click();
    const download=await pending;
    const exported=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.equal(exported.schema_version,1);
    assert.equal(exported.target,'browser-local');
    assert.equal(exported.contains_secrets,false);
    assert.deepEqual(publicErrors,[],'Public first-run setup JavaScript errors');
    await publicPage.close();
    console.log('Private evaluation metrics, candidate-date review, quote capture, and fork setup smoke passed');
  } finally {
    if(browser)await browser.close();
    child.kill('SIGTERM');
    if(staticSite)await new Promise(resolve=>staticSite.server.close(resolve));
    await fs.rm(folder,{recursive:true,force:true});
  }
}

main().catch(error=>{console.error(error);process.exitCode=1;});
