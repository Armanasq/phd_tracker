'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const http=require('node:http');
const {chromium,firefox,webkit}=require('playwright');

async function serveSite(root){
  const server=http.createServer(async(request,response)=>{
    try{
      const url=new URL(request.url,'http://localhost');
      const local=path.resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
      if(!local.startsWith(root+path.sep)){response.writeHead(403);response.end();return}
      const body=await fs.readFile(local);
      const ext=path.extname(local);
      response.writeHead(200,{'Content-Type':({'.mjs':'text/javascript','.js':'text/javascript','.html':'text/html','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'}[ext]||'application/octet-stream')});
      response.end(body);
    }catch{response.writeHead(404);response.end('Not found')}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,origin:'http://127.0.0.1:'+server.address().port};
}

async function serveModel(origin,requests){
  const server=http.createServer(async(req,res)=>{
    const cors={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type','Access-Control-Allow-Private-Network':'true'};
    if(req.method==='OPTIONS'){res.writeHead(204,cors);res.end();return}
    const chunks=[];for await(const chunk of req)chunks.push(chunk);
    const body=Buffer.concat(chunks).toString('utf8');
    requests.push({path:req.url,method:req.method,body,authorization:req.headers.authorization});
    if(req.url==='/v1/models'){res.writeHead(200,{...cors,'Content-Type':'application/json'});res.end(JSON.stringify({data:[{id:'synthetic-chat'}]}));return}
    if(req.url==='/v1/chat/completions'){
      const input=JSON.parse(body);
      if(input.model!=='synthetic-chat'){res.writeHead(422,cors);res.end();return}
      if(input.stream){
        res.writeHead(200,{...cors,'Content-Type':'text/event-stream'});
        res.end('data: {"choices":[{"delta":{"content":"Verified local "}}]}\n\n'+'data: {"choices":[{"delta":{"content":"assistant reply"}}]}\n\n'+'data: [DONE]\n\n');
      }else{
        res.writeHead(200,{...cors,'Content-Type':'application/json'});
        res.end(JSON.stringify({choices:[{message:{content:'ready'}}]}));
      }
      return;
    }
    res.writeHead(404,cors);res.end();
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,endpoint:'http://127.0.0.1:'+server.address().port+'/v1'};
}

async function main(){
  const root=path.resolve('site'),requests=[];
  const site=await serveSite(root);
  const model=await serveModel(site.origin,requests);
  let browser;
  try{
    const selected=process.env.PHDAI_BROWSER_ENGINE||'chromium';
    const browsers={chromium,firefox,webkit};
    if(!Object.hasOwn(browsers,selected))throw new Error('Unknown browser engine');
    browser=await browsers[selected].launch(selected==='chromium'
      ?{headless:true,args:['--no-sandbox']}:{headless:true});
    const page=await browser.newPage({viewport:{width:1280,height:850}});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(site.origin+'/index.html#settings',{waitUntil:'networkidle'});
    const config=page.locator('form[data-os-form="bm-config"]');
    await config.locator('input[name="baseUrl"]').fill(model.endpoint);
    await config.locator('input[name="model"]').fill('synthetic-chat');
    await config.locator('button[type="submit"]').click();
    await page.locator('[data-os-action="bm-test"]').click();
    await page.waitForFunction(()=>document.querySelector('#currentModel')?.textContent?.includes('synthetic-chat'),{timeout:20000});
    await page.locator('.topbar [data-action="lens-open"]').click();
    await page.waitForFunction(()=>document.querySelector('.lens-identity-copy small')?.textContent?.includes('Verified'),{timeout:15000});
    await page.locator('#lensInput').fill('Assess my recorded evidence');
    await page.locator('#lensForm .lens-send').click();
    await page.locator('.lens-turn.assistant').last().getByText('Verified local assistant reply').waitFor({timeout:20000});
    const sent=requests.filter(x=>x.path==='/v1/chat/completions');
    assert.equal(sent.length,2,'Probe and assistant must each invoke the model');
    assert.ok(sent.every(x=>!x.authorization),'Browser-local requests must not forward credentials');
    assert.match(sent[1].body,/Assess my recorded evidence/);
    await page.locator('#atlasLensPanel [data-lens="close"]').click();
    await page.locator('#navigation [data-value="deployment"]').click();
    assert.match(await page.locator('#body').innerText(),/Browser-local model/);
    assert.match(await page.locator('#body').innerText(),/Authenticated cloud full stack/);
    await page.locator('#navigation [data-value="discovery"]').click();
    assert.match(await page.locator('#body h1').innerText(),/Discovery/);
    assert.deepEqual(errors,[]);
    console.log((process.env.PHDAI_BROWSER_ENGINE||'chromium')+' browser-local model and floating assistant integration passed');
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>site.server.close(resolve));
    await new Promise(resolve=>model.server.close(resolve));
  }
}

main().catch(error=>{console.error(error);process.exitCode=1});
