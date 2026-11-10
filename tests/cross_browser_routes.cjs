'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const http=require('node:http');
const net=require('node:net');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {firefox,webkit}=require('playwright');

async function freePort(){
 const server=net.createServer();
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 await new Promise(resolve=>server.close(resolve));
 return port;
}

async function serveStatic(root){
 const server=http.createServer(async(request,response)=>{
  try{
   const url=new URL(request.url,'http://localhost');
   const relative=decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname);
   const target=path.resolve(root,'.'+relative);
   if(!target.startsWith(root+path.sep)){response.writeHead(403);response.end();return;}
   const body=await fs.readFile(target);
   const mime={'.html':'text/html','.css':'text/css','.js':'application/javascript','.mjs':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
   response.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream'});
   response.end(body);
  }catch{response.writeHead(404);response.end('Not found');}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 return {server,url:'http://127.0.0.1:'+server.address().port};
}

async function checkEngine(name,type,urls,routes,results){
 const browser=await type.launch({headless:true});
 try{
  for(const [mode,url] of urls){
   for(const [device,width,height] of [['desktop',1440,900],['mobile',390,844]]){
    const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
    const page=await context.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    try{
     await page.goto(url+'/index.html#dashboard',{waitUntil:'domcontentloaded'});
     await page.locator('#body h1').first().waitFor({timeout:20000});
     for(const view of routes){
      if(width<=980)await page.locator('#workspaceSection').selectOption(view);
      else await page.locator('#navigation [data-action="nav"][data-value="'+view+'"]').click();
      await page.waitForFunction(expected=>location.hash==='#'+expected,view);
      const heading=await page.locator('#body h1').first().textContent();
      assert.ok(heading?.trim(),name+' '+mode+' '+device+' '+view+' missing heading');
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
      assert.ok(overflow<=2,name+' '+mode+' '+device+' '+view+' horizontal overflow '+overflow);
      results.push({engine:name,mode,device,route:view});
     }
     const final=routes.at(-1),previous=routes.at(-2);
     await page.goBack();
     await page.waitForFunction(expected=>location.hash==='#'+expected,previous);
     await page.goForward();
     await page.waitForFunction(expected=>location.hash==='#'+expected,final);
     await page.reload({waitUntil:'domcontentloaded'});
     await page.locator('#body h1').first().waitFor({timeout:15000});
     assert.equal(new URL(page.url()).hash,'#'+final,name+' '+mode+' '+device+' lost deep link');
     if(mode==='private'){
      if(width<=980)await page.locator('#workspaceSection').selectOption('operations');
      else await page.locator('#navigation [data-action="nav"][data-value="operations"]').click();
      await page.locator('.ops-kpi-strip').waitFor({timeout:15000});
      assert.doesNotMatch(await page.locator('#body').innerText(),/Connect the private workspace/);
     }
     assert.deepEqual(errors,[],name+' '+mode+' '+device+' JavaScript failures');
    }finally{await context.close();}
   }
  }
 }finally{await browser.close();}
}

async function main(){
 const {VIEWS}=await import('../site/modules/routes.mjs');
 const routes=VIEWS.map(([id])=>id);
 assert.equal(new Set(routes).size,routes.length,'Canonical routes must have unique identifiers');
 const root=path.resolve('.'),staticServer=await serveStatic(path.join(root,'site'));
 const folder=await fs.mkdtemp(path.join(os.tmpdir(),'phd-cross-browser-'));
 const port=await freePort(),privateUrl='http://127.0.0.1:'+port;
 const child=spawn('python',['-m','phd_agents','serve','--port',String(port)],{
  cwd:root,env:{...process.env,PHDAI_PRIVATE_DIR:folder},stdio:['ignore','ignore','pipe'],
 });
 let serverErrors='';
 child.stderr.on('data',data=>{serverErrors+=String(data).slice(-800);});
 try{
  let ready=false;
  for(let attempt=0;attempt<80;attempt++){
   try{const response=await fetch(privateUrl+'/api/health');if(response.ok){ready=true;break;}}catch{}
   await new Promise(resolve=>setTimeout(resolve,180));
  }
  assert.ok(ready,'Private runtime failed: '+serverErrors.slice(-800));
  const results=[];
  for(const [name,type] of [['firefox',firefox],['webkit',webkit]]){
   await checkEngine(name,type,[['public',staticServer.url],['private',privateUrl]],routes,results);
  }
  const expected=2*2*2*routes.length;
  assert.equal(results.length,expected);
  const dest=path.resolve('artifacts/ui-qa');
  await fs.mkdir(dest,{recursive:true});
  await fs.writeFile(path.join(dest,'cross-browser-compatibility.json'),JSON.stringify({
   status:'passed',engines:['firefox','webkit'],modes:['public','private'],
   route_count:routes.length,checks:results.length,synthetic_browser_environment:true,results,
  },null,2));
  console.log('Firefox/WebKit compatibility: '+results.length+' public/private route, device and engine checks passed');
 }finally{
  child.kill('SIGTERM');
  await new Promise(resolve=>setTimeout(resolve,400));
  await fs.rm(folder,{recursive:true,force:true});
  await new Promise(resolve=>staticServer.server.close(resolve));
 }
}
main().catch(error=>{console.error(error);process.exitCode=1});
