'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');

async function openPort() {
  const server=net.createServer();
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port;
  await new Promise(resolve=>server.close(resolve));
  return port;
}
async function main(){
  const port=await openPort(),root=path.resolve('.'),folder=await fs.mkdtemp(path.join(os.tmpdir(),'phd-ai-qa-'));
  const child=spawn('python',['-m','phd_agents','serve','--port',String(port)],{cwd:root,env:{...process.env,PHDAI_PRIVATE_DIR:folder},stdio:['ignore','pipe','pipe']});
  let stderr='';child.stderr.on('data',chunk=>{stderr+=chunk.toString()});
  const url='http://127.0.0.1:'+port;
  let ready=false;
  for(let i=0;i<70;i++){
    if(child.exitCode!==null)break;
    try{const r=await fetch(url+'/api/health');if(r.ok){ready=true;break}}catch{}
    await new Promise(resolve=>setTimeout(resolve,180));
  }
  assert.ok(ready,'Private server failed to start: '+stderr.slice(0,900));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto(url+'/ai-studio.html',{waitUntil:'networkidle'});
    await page.locator('#connection.live').waitFor({timeout:12000});
    await page.locator('[data-view="providers"]').click();
    await page.locator('.connection-card').first().waitFor();
    assert.ok(await page.locator('.connection-card').count()>=15);
    await page.locator('#providerFilter').selectOption('local');
    assert.ok((await page.locator('.connection-card').count())>=2);
    await page.locator('[data-view="settings"]').click();
    await page.locator('#settingsForm').waitFor();
    await page.locator('#prefZone').fill('Europe/Amsterdam');
    await page.locator('#prefLimit').fill('2');
    await page.locator('#prefCloudLimit').fill('0');
    await page.locator('#settingsForm button[type="submit"]').click();
    await page.waitForFunction(()=>document.querySelector('#prefZone')?.value==='Europe/Amsterdam');
    await page.locator('[data-view="activity"]').click();
    await page.getByText('INPUT TOKENS').waitFor();
    await page.locator('[data-view="providers"]').click();
    await page.locator('#providerFilter').selectOption('all');
    await page.route('**/api/providers/models',route=>route.fulfill({status:200,contentType:'application/json',
      body:JSON.stringify({provider_id:'ollama',status:'reachable',latency_ms:20,models:[{id:'smoke-local-model',name:'Smoke Local Model'}]})}));
    await page.locator('[data-action="provider-models"][data-id="ollama"]').click();
    await page.getByRole('dialog').getByText('Smoke Local Model').waitFor();
    await page.getByRole('dialog').getByText('Select model').click();
    await page.locator('.connection-card').filter({hasText:'smoke-local-model'}).first().waitFor();
    await page.locator('[data-action="edit-provider"][data-id="ollama"]').click();
    await page.getByRole('dialog').waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').count(),0);
    const out=path.resolve('artifacts','ui-qa');
    await fs.mkdir(out,{recursive:true});
    await page.screenshot({path:path.join(out,'ai-studio-providers-desktop.png'),fullPage:true});
    await page.goto(url+'/index.html',{waitUntil:'networkidle'});
    await page.locator('#aiProvider option').first().waitFor({timeout:12000});
    await page.route('**/api/agents/run',route=>route.fulfill({status:200,contentType:'application/json',
      body:JSON.stringify({id:'synthetic-test-run',text:'Verified evidence required for the closing time.',status:'proposed'})}));
    await page.locator('#body [data-action="ai-run"]').click();
    await page.locator('#aiInlineResult').getByText('Verified evidence required for the closing time.').waitFor();
    assert.equal((await page.locator('#aiInlineResult').innerText()).trim(),'Verified evidence required for the closing time.');
    await page.goto(url+'/ai-studio.html',{waitUntil:'networkidle'});
    await page.locator('#connection.live').waitFor();
    await page.setViewportSize({width:390,height:844});
    await page.locator('#mobileStudioView').selectOption('settings');
    await page.locator('#settingsForm').waitFor();
    await page.screenshot({path:path.join(out,'ai-studio-settings-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('AI Studio smoke passed: provider routing, settings, models, responsive view and dialog focus');
  }finally{
    await browser.close();
    child.kill('SIGTERM');
    await new Promise(resolve=>setTimeout(resolve,200));
    await fs.rm(folder,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1});
