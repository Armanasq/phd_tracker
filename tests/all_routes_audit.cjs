'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const http=require('node:http');
const net=require('node:net');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const TRACKER=['dashboard','applications','calendar','pipeline','actions','contacts','updates','compare','review','archive','sources'];
const STUDIO=['overview','agents','workflows','providers','applications','referees','timeline','evidence','planning','activity','settings'];
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
async function check(browser,url,kind,views,results){
 for(const [device,width,height] of SIZES){
  const page=await browser.newPage({viewport:{width,height}}),errors=[],httpErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{
   const responseUrl=new URL(r.url());
   const expectedPrivateProbe=kind==='tracker'&&r.status()===404&&responseUrl.pathname==='/api/bootstrap';
   if(r.url().startsWith(url)&&r.status()>=400&&!expectedPrivateProbe)httpErrors.push(r.status()+' '+r.url());
  });
  try{
   await page.goto(url+'/'+(kind==='tracker'?'index.html':'ai-studio.html'),{waitUntil:'networkidle'});
   if(kind==='tracker')await page.locator('#body h1').waitFor({timeout:15000});
   else await page.locator('#connection.live').waitFor({timeout:15000});
   for(const view of views){
    const selector=kind==='tracker'?'#navigation [data-action="nav"][data-value="'+view+'"]':'#studioNav [data-view="'+view+'"]';
    const root=kind==='tracker'?'#body':'#workspace';
    if(kind==='studio'&&width<=850)await page.locator('#mobileStudioView').selectOption(view);
    else await page.locator(selector).click();
    await page.locator(root+' h1').first().waitFor();
    const title=(await page.locator(root+' h1').first().innerText()).trim();
    assert.ok(title,kind+' '+view+' missing heading');
    assert.equal(new URL(page.url()).hash.slice(1),view,kind+' '+view+' incorrect route');
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    assert.ok(overflow<=2,kind+' '+view+' '+device+' horizontal overflow '+overflow);
    await page.reload({waitUntil:'networkidle'});
    await page.locator(root+' h1').first().waitFor();
    assert.equal(new URL(page.url()).hash.slice(1),view,kind+' '+view+' lost deep link');
    results.push({kind,view,device,title,status:'pass'});
   }
   assert.deepEqual(errors,[],kind+' '+device+' JavaScript errors');
   assert.deepEqual(httpErrors,[],kind+' '+device+' HTTP errors');
  }finally{await page.close()}
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
  await check(browser,publicUrl,'tracker',TRACKER,results);
  await check(browser,privateUrl,'studio',STUDIO,results);
  const page=await browser.newPage();
  try{
   await page.goto(publicUrl+'/index.html',{waitUntil:'networkidle'});
   assert.ok(await page.locator('a[href="./ai-studio.html"]').count(),'Tracker missing AI Studio link');
   await page.locator('a[href="./ai-studio.html"]').click();
   assert.ok(page.url().endsWith('/ai-studio.html'));
   await page.locator('a[href="./index.html"]').first().click();
   assert.ok(page.url().endsWith('/index.html'));
   await page.goto(publicUrl+'/ai-studio.html',{waitUntil:'networkidle'});
   assert.match(await page.locator('#workspace').innerText(),/private local service/i);
  }finally{await page.close()}
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
