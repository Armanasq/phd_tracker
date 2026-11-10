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
   if(payload.stream===true){
    res.setHeader('Content-Type','text/event-stream');
    res.end('data: {"choices":[{"delta":{"content":"Synthetic verified local "}}]}\n\n'+
      'data: {"choices":[{"delta":{"content":"inference response. No application was submitted."}}]}\n\n'+
      'data: [DONE]\n\n');return;
   }
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
  const lensRequests=[];
  page.on('request',req=>{
   if(req.method()==='POST'&&req.url().includes('/api/agents/run')){
    const body=req.postDataJSON();
    lensRequests.push({body,key:req.headers()['idempotency-key']||null});
   }
  });
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
  const routeChange=await fetch(base+'/api/settings',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({default_provider:'ollama'})});
  assert.ok(routeChange.ok,'Unverified workspace default should not block an assigned verified agent');
  await page.locator('#navigation [data-action="nav"][data-value="applications"]').click();
  await page.locator('#body tbody .rowbutton').first().click();
  const recordButton=page.locator('.modal [data-action="ai-record"]');
  await recordButton.waitFor();
  const selectedId=await recordButton.getAttribute('data-value');
  await recordButton.click();
  await page.locator('#atlasLensPanel').waitFor({timeout:12000});
  assert.equal(await page.locator('#lensScope').inputValue(),selectedId,
    'Application action must open the Lens with the correct opportunity in context');
  await page.locator('#lensAgent').selectOption('smoke_agent',{timeout:12000});
  await page.locator('.lens-identity-copy small').getByText('Verified · smoke-chat',{exact:false}).waitFor({timeout:12000});
  assert.match(await page.locator('.lens-provider').innerText(),/Local smoke model/);
  await page.locator('#lensInput').fill('Evaluate the applicant evidence; do not submit anything.');
  assert.equal(await page.locator('#lensForm select[name="provider_id"]').count(),0,
    'Lens must use the configured model route rather than exposing a per-turn provider field');
  await page.locator('#lensForm button[type="submit"]').click();
  await page.locator('.lens-turn.assistant .lens-body').getByText('Synthetic verified local inference response.',{exact:false}).waitFor({timeout:30000});
  await page.locator('.lens-turn.assistant [data-lens="trace"]').click();
  assert.match(await page.locator('.lens-trace').innerText(),/smoke-chat/);
  await page.locator('.lens-evidence summary').click();
  assert.ok((await page.locator('.lens-evidence-item').count())>=1);
  const conversations=await fetch(base+'/api/conversations').then(r=>r.json());
  assert.equal(conversations.conversations.length,1);
  const threadId=conversations.conversations[0].id;
  const firstThread=await fetch(base+'/api/conversations/'+threadId).then(r=>r.json());
  assert.equal(firstThread.application_id,selectedId);
  assert.equal(firstThread.agent_id,'smoke_agent');
  assert.equal(firstThread.messages.length,2);
  assert.equal(firstThread.messages[1].evidence_refs[0].application_id,selectedId);
  await page.locator('#lensInput').fill('Which document should I check next?');
  await page.locator('#lensForm button[type="submit"]').click();
  await page.locator('.lens-turn.assistant').nth(1).waitFor({timeout:30000});
  const secondThread=await fetch(base+'/api/conversations/'+threadId).then(r=>r.json());
  assert.equal(secondThread.messages.length,4);
  const lastModelCall=seen.filter(x=>x.path==='/v1/chat/completions').at(-1);
  assert.match(lastModelCall.body,/conversation_history/);
  assert.match(lastModelCall.body,/Evaluate the applicant evidence/);
  await page.locator('#lensStreaming').check();
  await page.locator('#lensInput').fill('Stream the next evidence check.');
  await page.locator('#lensForm button[type="submit"]').click();
  await page.locator('.lens-turn.assistant').nth(2).waitFor({timeout:30000});
  assert.match(await page.locator('.lens-turn.assistant').nth(2).innerText(),/Synthetic verified local inference response/);
  const streamedCall=seen.filter(x=>x.path==='/v1/chat/completions').at(-1);
  assert.equal(JSON.parse(streamedCall.body).stream,true,'Private assistant must request native model SSE');
  const streamedThread=await fetch(base+'/api/conversations/'+threadId).then(r=>r.json());
  assert.equal(streamedThread.messages.length,6,'Streamed output must persist exactly once');
  await page.locator('#atlasLensPanel [data-lens="close"]').click();
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.topbar [data-action="lens-open"]').click();
  await page.locator('.lens-turn.assistant').nth(1).waitFor({timeout:13000});
  assert.equal(await page.locator('#lensAgent').inputValue(),'smoke_agent');
  assert.equal(await page.locator('#lensScope').inputValue(),selectedId);
  await page.locator('#atlasLensPanel [data-lens="history"]').click();
  await page.locator('.lens-thread-open').first().waitFor();
  await page.locator('#atlasLensPanel [data-lens="close"]').click();
  assert.ok(seen.filter(x=>x.path==='/v1/chat/completions').length>=2);
  await page.locator('[data-action="nav"][data-value="activity"]').click();
  await page.locator('.os-ledger').first().getByText('My Research Agent').first().waitFor();
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
  const cloudRequests=[];
  await page.route('**/api/assistant/bootstrap',async route=>{
   const upstream=await route.fetch();
   const bootstrap=await upstream.json();
   bootstrap.catalog.providers.push({id:'cloud_consent_test',label:'Cloud test gateway',local:false,kind:'openai_compatible',base_url:'https://safe.example.invalid/v1',model:'test-cloud'});
   bootstrap.provider_states.cloud_consent_test={state:'responded',credential_configured:true};
   bootstrap.routing.agent_assignments.smoke_agent={provider_id:'cloud_consent_test',provider_label:'Cloud test gateway',model:'test-cloud',source:'agent_assignment',state:'responded',allowed:true};
   await route.fulfill({response:upstream,json:bootstrap});
  });
  await page.route('**/api/agents/run',async route=>{
   cloudRequests.push({body:route.request().postDataJSON(),key:route.request().headers()['idempotency-key']});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
    id:'synthetic-cloud-run',agent_id:'smoke_agent',provider_id:'cloud_consent_test',
    model:'test-cloud',status:'proposed',text:'Cloud consent verified for this single request.',
    conversation_id:null,evidence_refs:[],tools:[],retrieval_method:'test'
   })});
  });
  let consentDialogs=0;
  page.on('dialog',async dialog=>{
   if(dialog.type()!=='confirm')throw Error('Unexpected dialog: '+dialog.message());
   consentDialogs+=1;
   if(consentDialogs===1)await dialog.dismiss();
   else await dialog.accept();
  });
  await page.evaluate(()=>{
   const launcher=document.querySelector('.lens-launcher');
   if(launcher?.getAttribute('aria-expanded')!=='true')launcher?.click();
  });
  await page.locator('#atlasLensPanel').waitFor({state:'visible'});
  await page.locator('#lensAgent').selectOption('smoke_agent');
  await page.waitForFunction(()=>document.querySelector('.lens-provider')?.textContent?.includes('Cloud test gateway'),{timeout:15000});
  await page.locator('#lensInput').fill('Audit a verified research statement.');
  await page.locator('#lensForm button[type="submit"]').click();
  assert.equal(consentDialogs,1,'A manual cloud request must obtain explicit disclosure consent');
  assert.equal(cloudRequests.length,0,'Declined cloud consent must not send a model request');
  await page.locator('#lensForm button[type="submit"]').click();
  await page.locator('.lens-turn.assistant .lens-body').getByText('Cloud consent verified for this single request.',{exact:false}).waitFor({timeout:12000});
  assert.equal(consentDialogs,2);
  assert.equal(cloudRequests.length,1);
  assert.equal(cloudRequests[0].body.cloud_consent,true);
  assert.ok(cloudRequests[0].key?.length>=16,'Cloud request must provide an idempotency key');
  await page.locator('#atlasLensPanel [data-lens="close"]').click();
  await page.unroute('**/api/agents/run');
  await page.unroute('**/api/assistant/bootstrap');
  await page.goto(base+'/ai-studio.html#providers',{waitUntil:'domcontentloaded'});
  await page.waitForURL('**/index.html#settings');
  await page.locator('#body h1').first().waitFor({timeout:12000});
  const lensCalls=lensRequests.filter(x=>x.body.conversation===true);
  const localLensCalls=lensCalls.filter(x=>x.body.cloud_consent===false);
  assert.ok(localLensCalls.length>=2,'Local Atlas Lens conversations were not captured');
  assert.ok(lensCalls.every(x=>typeof x.key==='string'&&x.key.length>=16),'Atlas Lens inference calls must be retry-safe');
  assert.equal(lensCalls.filter(x=>x.body.cloud_consent===true).length,1,'Exactly one approved cloud request must be sent');
  assert.deepEqual(pageErrors,[],'Browser JS errors');
  await page.close();
  console.log('Unified workspace passed: endpoint setup, activation, agent routing, application-scoped Atlas Lens inference, run trace, workflow editor, legacy route and mobile layout');
 }finally{
  if(browser)await browser.close();
  child.kill('SIGTERM');
  await new Promise(resolve=>setTimeout(resolve,220));
  await fs.rm(folder,{recursive:true,force:true});
  await new Promise(resolve=>model.close(resolve));
 }
}
main().catch(error=>{console.error(error);process.exitCode=1});
