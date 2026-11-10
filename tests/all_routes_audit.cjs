'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const http=require('node:http');
const net=require('node:net');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const TRACKER=['dashboard','applications','discovery','readiness','documents','operations','actions','ledger','calendar','pipeline','contacts','updates','compare','review','archive','sources','ai','agents','automations','activity','source-observations','source-claims','onboarding','deployment','settings'];

const SIZES=[['desktop',1440,900],['tablet',820,1080],['mobile',390,844],['narrow',320,700]];
async function freePort(){const s=net.createServer();await new Promise(ok=>s.listen(0,'127.0.0.1',ok));const port=s.address().port;await new Promise(ok=>s.close(ok));return port}
async function staticServer(root){
 const s=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://localhost'),rel=decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname),full=path.resolve(root,'.'+rel);
 if(!full.startsWith(root+path.sep)){res.writeHead(403);res.end();return}
 const data=await fs.readFile(full),ext=path.extname(full);
 res.writeHead(200,{'Content-Type':({'.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.html':'text/html'}[ext]||'application/octet-stream')});res.end(data)
 }catch{res.writeHead(404);res.end('Not found')}});
 await new Promise(ok=>s.listen(0,'127.0.0.1',ok));
 return {server:s,url:'http://127.0.0.1:'+s.address().port}
}
async function check(browser,url,views,results,mode){
 for(let batch=0;batch<SIZES.length;batch+=2){
 await Promise.all(SIZES.slice(batch,batch+2).map(async([device,width,height])=>{
  const page=await browser.newPage({viewport:{width,height}}),errors=[],httpErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{
   const responseUrl=new URL(r.url());
   const expectedPrivateProbe=mode==='public'&&r.status()===404&&['/api/bootstrap','/api/assistant/bootstrap'].includes(responseUrl.pathname);
   if(r.url().startsWith(url)&&r.status()>=400&&!expectedPrivateProbe)httpErrors.push(r.status()+' '+r.url());
  });
  try{
   await page.goto(url+'/index.html',{waitUntil:'networkidle'});
   await page.locator('#body h1').waitFor({timeout:15000});
   const lens=page.locator('#atlasLens');
   assert.equal(await lens.count(),1,'Atlas Lens must initialize on every workspace mode');
   if(width<=680)await page.locator('.topbar [data-action="lens-open"]').click();
   else await lens.locator('[data-lens="toggle"]').click();
   await page.locator('#atlasLensPanel').waitFor({timeout:12000});
   assert.ok(await page.locator('#lensScope').isVisible(),'Application context selector must render');
   await page.locator('#atlasLensPanel [data-lens="close"]').click();
   for(const view of views){
    const selector='#navigation [data-action="nav"][data-value="'+view+'"]';
    const root='#body';
    if(width<=980)await page.locator('#workspaceSection').selectOption(view);
    else await page.locator(selector).click();
    await page.locator(root+' h1').first().waitFor();
    const title=(await page.locator(root+' h1').first().innerText()).trim();
    assert.ok(title,mode+' '+view+' missing heading');
    assert.equal(new URL(page.url()).hash.slice(1),view,mode+' '+view+' incorrect route');
    if(view==='readiness'){
     assert.ok(await page.locator('[data-action="export-readiness"]').count(),mode+' readiness export unavailable');
     assert.ok((await page.locator('[data-action="readiness-filter"]').count())>=4,mode+' readiness filters missing');
     await page.locator('[data-action="readiness-filter"][data-value="proof"]').click();
     assert.ok(await page.locator('#body h1').first().isVisible(),mode+' readiness proof filter failed');
    }
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    assert.ok(overflow<=2,mode+' '+view+' '+device+' horizontal overflow '+overflow);
    await page.reload({waitUntil:'networkidle'});
    await page.locator(root+' h1').first().waitFor();
    assert.equal(new URL(page.url()).hash.slice(1),view,mode+' '+view+' lost deep link');
    results.push({mode,view,device,title,status:'pass'});
   }
   assert.deepEqual(errors,[],mode+' '+device+' JavaScript errors');
   assert.deepEqual(httpErrors,[],mode+' '+device+' HTTP errors');
  }finally{await page.close()}
 }));
 }
}
async function main(){
 const root=path.resolve('.'),out=path.join(root,'artifacts','ui-qa');
 await fs.mkdir(out,{recursive:true});
 const {server,url:publicUrl}=await staticServer(path.join(root,'site'));
 const folder=await fs.mkdtemp(path.join(os.tmpdir(),'phd-routes-'));
 const port=await freePort(),privateUrl='http://127.0.0.1:'+port;
 const child=spawn('python',['-m','phd_agents','serve','--port',String(port)],{cwd:root,env:{...process.env,PHDAI_PRIVATE_DIR:folder},stdio:'ignore'});
 let browser;const results=[];
 try{
  let ready=false;
  for(let i=0;i<75;i++){try{const r=await fetch(privateUrl+'/api/health');if(r.ok){ready=true;break}}catch{}await new Promise(ok=>setTimeout(ok,180))}
  assert.ok(ready,'Private runtime failed to start');
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  await check(browser,publicUrl,TRACKER,results,'public');
  await check(browser,privateUrl,TRACKER,results,'private');
  const page=await browser.newPage();
  try{
   await page.goto(publicUrl+'/index.html',{waitUntil:'networkidle'});
   assert.equal(await page.locator('iframe').count(),0,'No embedded AI Studio is permitted');
   await page.goto(publicUrl+'/ai-studio.html#providers',{waitUntil:'domcontentloaded'});
   await page.waitForURL('**/index.html#settings');
   await page.locator('#body h1').first().waitFor({timeout:12000});
   assert.match(await page.locator('#body').innerText(),/local model connection/i);

  }finally{await page.close()}
  const modeOrder={public:0,private:1},deviceOrder=Object.fromEntries(SIZES.map(([id],index)=>[id,index]));
  const routeOrder=Object.fromEntries(TRACKER.map((id,index)=>[id,index]));
  results.sort((a,b)=>modeOrder[a.mode]-modeOrder[b.mode]||deviceOrder[a.device]-deviceOrder[b.device]||routeOrder[a.view]-routeOrder[b.view]);
  await fs.writeFile(path.join(out,'all-routes-audit.json'),JSON.stringify({status:'pass',checks:results.length,results},null,2));
  console.log('All '+results.length+' route/viewport checks passed');
 }finally{
  if(browser)await browser.close();
  child.kill('SIGTERM');
  await new Promise(ok=>setTimeout(ok,200));
  await fs.rm(folder,{recursive:true,force:true});
  await new Promise(ok=>server.close(ok));
 }
}
main().catch(e=>{console.error(e);process.exitCode=1});
