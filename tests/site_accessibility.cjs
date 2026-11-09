'use strict';
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;

async function main(){
 const site=path.resolve('site'),dest=path.resolve('artifacts/ui-qa');
 await fs.mkdir(dest,{recursive:true});
 const server=http.createServer(async(req,res)=>{
  try{
   const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   const filename=path.resolve(site,'.'+(pathname==='/'?'/index.html':pathname));
   if(!filename.startsWith(site+path.sep)){res.writeHead(403);res.end();return}
   const body=await fs.readFile(filename);
   res.writeHead(200,{'Content-Type':filename.endsWith('.js')||filename.endsWith('.mjs')?'application/javascript':filename.endsWith('.json')?'application/json':filename.endsWith('.css')?'text/css':'text/html'});
   res.end(body);
  }catch{res.writeHead(404);res.end('Not found')}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const issues=[];
 try{
  for(const [width,height,view] of [[1512,980,'dashboard'],[1512,980,'applications'],[1512,980,'calendar'],[1512,980,'pipeline'],[1512,980,'review'],[390,844,'applications']]){
   const context=await browser.newContext({viewport:{width,height}});
   const page=await context.newPage();
   await page.goto('http://127.0.0.1:'+server.address().port+'/',{waitUntil:'networkidle'});
   await page.locator('#body h1').waitFor();
   if(view!=='dashboard')await page.locator('#navigation [data-value="'+view+'"]').click();
   const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
   issues.push({viewport:width,view,violations:results.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.slice(0,8).map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))})),incomplete:results.incomplete.length});
   if(view==='applications'&&width>1000){
    await page.locator('#body tbody .rowbutton').first().click();
    const dialog=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
    issues.push({viewport:width,view:'application-dialog',violations:dialog.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.slice(0,8).map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))})),incomplete:dialog.incomplete.length});
   }
   await page.close();
   await context.close();
  }
  await fs.writeFile(path.join(dest,'phd-atlas-accessibility.json'),JSON.stringify({generated:new Date().toISOString(),results:issues},null,2));
  const blocking=issues.flatMap(x=>x.violations.filter(v=>['critical','serious'].includes(v.impact)).map(v=>({view:x.view,viewport:x.viewport,rule:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})));
  console.log(JSON.stringify({checked:issues.map(x=>x.view+'/'+x.viewport),violations:issues.map(x=>({view:x.view,types:x.violations.length,blocking:x.violations.filter(v=>['critical','serious'].includes(v.impact)).length})),blocking},null,2));
  assert.deepEqual(blocking,[],'Serious/critical WCAG automated accessibility violations');
 } finally{
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
 }
}
main().catch(err=>{console.error(err);process.exitCode=1});
