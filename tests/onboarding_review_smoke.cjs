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
with store.db:
    store.db.execute("INSERT INTO source_observations(application_id,source_url,status,content_sha256,observed_at,http_status,content_length,drift) VALUES(?,?,?,?,?,?,?,?)",("EXAMPLE-1","https://university.example/program","fetched",digest,"2026-11-10T08:00:00+00:00",200,21,"source_bytes_changed_needs_review"))
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
    assert.deepEqual(errors,[],'Private source review JavaScript errors');
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
    console.log('Private source review and browser-local fork setup smoke passed');
  } finally {
    if(browser)await browser.close();
    child.kill('SIGTERM');
    if(staticSite)await new Promise(resolve=>staticSite.server.close(resolve));
    await fs.rm(folder,{recursive:true,force:true});
  }
}

main().catch(error=>{console.error(error);process.exitCode=1;});
