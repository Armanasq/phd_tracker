'use strict';
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const net=require('node:net');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');

async function freePort(){
 const server=net.createServer();
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 await new Promise(resolve=>server.close(resolve));
 return port;
}
async function stubModelServer(){
 const seen=[];
 const server=http.createServer(async(req,res)=>{
  const chunks=[];
  for await(const c of req)chunks.push(c);
  const raw=Buffer.concat(chunks).toString('utf8');
  seen.push({method:req.method,path:req.url,body:raw});
  res.setHeader('Content-Type','application/json');
  if(req.url==='/v1/models'&&req.method==='GET'){
   res.end(JSON.stringify({data:[{id:'smoke-chat',object:'model',name:'Smoke Chat'}]}));return;
  }
  if(req.url==='/v1/chat/completions'&&req.method==='POST'){
   let payload={};try{payload=JSON.parse(raw)}catch{}
   if(payload.model!=='smoke-chat'){res.writeHead(422);res.end(JSON.stringify({error:{message:'unknown stub model'}}));return}
   res.end(JSON.stringify({id:'chatcmpl-test',model:'smoke-chat',
    choices:[{message:{role:'assistant',content:'Synthetic verified local inference response. No application was submitted.'}}],
    usage:{prompt_tokens:42,completion_tokens:13}}));return;
  }
  res.writeHead(404);res.end(JSON.stringify({error:'Not found'}));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 return {server,port:server.address().port,seen};
}
async function main(){
 const {server:model,port:modelPort,seen}=await stubModelServer();
 const root=path.resolve('.'),folder=await fs.mkdtemp(path.join(os.tmpdir(),'atlas-unified-'));
 const port=await freePort();
 const child=spawn('python',['-m','phd_agents','serve','--port',String(port)],{
  cwd:root,env:{...process.env,PHDAI_PRIVATE_DIR:folder},stdio:['ignore','pipe','pipe']
 });
 let errors='';child.stderr.on('data',b=>errors+=b.toString());
 const base='http://127.0.0.1:'+port;
 let browser;
 try{
  let ready=false;
  for(let i=0;i<75;i++){
   try{const response=await fetch(base+'/api/health');if(response.ok){ready=true;break}}catch{}
   await new Promise(resolve=>setTimeout(resolve,180));
  }
  assert.ok(ready,'Local backend did not start: '+errors.slice(-800));
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const pageErrors=[];
  page.on('pageerror',error=>pageErrors.push(error.message));
  await page.goto(base+'/index.html#settings',{waitUntil:'networkidle'});
  await page.locator('.os-registry').waitFor({timeout:13000});
  assert.equal(await page.locator('iframe').count(),0,'Separate AI Studio iframe must not exist');
  await page.locator('[data-os-action="new-provider"]').click();
  const form=page.locator('form[data-os-form="provider"]');
  await form.locator('input[name="id"]').fill('smoke_vllm');
  await form.locator('input[name="label"]').fill('Local smoke model');
  await form.locator('select[name="kind"]').selectOption('openai_compatible');
  await form.locator('input[name="base_url"]').fill('http://127.0.0.1:'+modelPort+'/v1');
  await form.locator('input[name="model"]').fill('smoke-chat');
  await form.locator('input[name="api_key_env"]').fill('');
  await form.locator('button[name="mode"][value="verify"]').click();
  await page.waitForFunction(()=>document.querySelector('#currentModel')?.textContent?.includes('Local smoke model'),{timeout:30000});
  const current=await fetch(base+'/api/routing').then(x=>x.json());
  assert.equal(current.default_provider,'smoke_vllm','Persisted default route should be active');
  assert.equal(current.default_model,'smoke-chat');
  assert.ok(seen.some(x=>x.path==='/v1/chat/completions'),'A real local HTTP model request must have occurred');
  await page.locator('[data-os-action="tab"][data-id="agents"]').click();
  await page.locator('[data-os-action="new-agent"]').click();
  const agent=page.locator('form[data-os-form="agent"]');
  await agent.locator('input[name="id"]').fill('smoke_agent');
  await agent.locator('input[name="label"]').fill('My Research Agent');
  await agent.locator('input[name="description"]').fill('Audit evidence');
  await agent.locator('textarea[name="instructions"]').fill('Only analyze supported evidence. Do not invent opportunities.');
  await agent.locator('select[name="provider_id"]').selectOption('smoke_vllm');
  await agent.locator('button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('.os-agent-row.active')?.textContent?.includes('My Research Agent'),{timeout:15000});
  const updated=await fetch(base+'/api/routing').then(x=>x.json());
  assert.equal(updated.agent_assignments.smoke_agent.provider_id,'smoke_vllm');
  assert.equal(updated.agent_assignments.smoke_agent.source,'agent_assignment');
  await page.locator('#navigation [data-action="nav"][data-value="applications"]').click();
  await page.locator('#body tbody .rowbutton').first().click();
  const recordButton=page.locator('.modal [data-action="ai-record"]');
  await recordButton.waitFor();
  const selectedId=await recordButton.getAttribute('data-value');
  await recordButton.click();
  await page.locator('.os-context-banner').getByText(selectedId,{exact:false}).waitFor();
  assert.equal(await page.locator('form[data-os-form="run"] select[name="application_id"]').inputValue(),selectedId);
  await page.locator('form[data-os-form="run"] select[name="agent_id"]').selectOption('smoke_agent');
  await page.locator('#osPrompt').fill('Evaluate the applicant evidence; do not submit anything.');
  assert.equal(await page.locator('form[data-os-form="run"] select[name="provider_id"]').count(),0,
    'Copilot must not require a model selector on each run');
  await page.locator('form[data-os-form="run"] button[type="submit"]').click();
  await page.locator('.os-answer-text').getByText('Synthetic verified local inference response.',{exact:false}).waitFor({timeout:30000});
  assert.ok(seen.filter(x=>x.path==='/v1/chat/completions').length>=2);
  await page.locator('[data-action="nav"][data-value="activity"]').click();
  await page.locator('.os-ledger').first().getByText('My Research Agent').waitFor();
  await page.locator('#navigation [data-action="nav"][data-value="operations"]').click();
  await page.locator('.ops-metrics').waitFor({timeout:15000});
  await page.locator('[data-ops-action="tab"][data-id="referees"]').click();
  await page.locator('[data-ops-action="new"][data-id="referee"]').click();
  const referee=page.locator('form[data-ops-form="private"][data-kind="referee"]');
  await referee.locator('input[name="id"]').fill('test_referee');
  await referee.locator('input[name="name"]').fill('Synthetic Referee');
  await referee.locator('button[type="submit"]').click();
  await page.locator('.ops-rows').getByText('Synthetic Referee',{exact:true}).first().waitFor({timeout:15000});
  const storedReferees=await fetch(base+'/api/operations').then(r=>r.json());
  assert.ok(storedReferees.referees.some(x=>x.id==='test_referee'));
  await page.locator('[data-ops-action="tab"][data-id="application"]').click();
  const appForm=page.locator('form[data-ops-form="application"]');
  await appForm.locator('select[name="application_id"]').selectOption(selectedId);
  await appForm.locator('textarea[name="notes"]').fill('Synthetic private preparation note.');
  await appForm.locator('input[name="estimated_hours"]').fill('3');
  await appForm.locator('button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('form[data-ops-form="application"] input[name="private_version"]')?.value==='1',{timeout:15000});
  const ownerSnapshot=await fetch(base+'/api/snapshot').then(r=>r.json());
  assert.equal(ownerSnapshot.records.find(r=>r.id===selectedId).notes,'Synthetic private preparation note.');

  await page.locator('#navigation [data-action="nav"][data-value="settings"]').click();
  await page.locator('[data-os-action="tab"][data-id="workflows"]').click();
  await page.locator('form[data-os-form="workflow"]').waitFor();
  const out=path.resolve('artifacts/ui-qa');
  await fs.mkdir(out,{recursive:true});
  await page.screenshot({path:path.join(out,'atlas-settings-unified-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspaceSection').selectOption('settings');
  await page.locator('[data-os-action="tab"][data-id="connections"]').click();
  await page.screenshot({path:path.join(out,'atlas-settings-unified-mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
  assert.ok(overflow<=2,'Mobile settings horizontal overflow: '+overflow);
  await page.goto(base+'/ai-studio.html#providers',{waitUntil:'domcontentloaded'});
  await page.waitForURL('**/index.html#settings');
  await page.locator('#body h1').first().waitFor({timeout:12000});
  assert.deepEqual(pageErrors,[],'Browser JS errors');
  await page.close();
  console.log('Unified workspace passed: custom OpenAI-compatible vLLM endpoint, model probe, activation, agent assignment, automatic inference, workflow editor, legacy route, mobile layout');
 }finally{
  if(browser)await browser.close();
  child.kill('SIGTERM');
  await new Promise(resolve=>setTimeout(resolve,220));
  await fs.rm(folder,{recursive:true,force:true});
  await new Promise(resolve=>model.close(resolve));
 }
}
main().catch(error=>{console.error(error);process.exitCode=1});
