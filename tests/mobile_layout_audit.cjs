'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');

const routes=['dashboard','applications','operations','actions','ledger','calendar','pipeline','contacts','updates','compare','review','archive','sources','ai','agents','automations','activity','settings'];
const widths=[320,360,375,390,430,768];

async function main(){
 const root=path.resolve('site');
 const output=path.resolve('artifacts/ui-qa');
 await fs.mkdir(output,{recursive:true});
 const server=http.createServer(async(req,res)=>{
  try{
   const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   const full=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
   if(!full.startsWith(root+path.sep)){res.writeHead(403);res.end();return}
   const content=await fs.readFile(full);
   const type=full.endsWith('.mjs')||full.endsWith('.js')?'application/javascript':full.endsWith('.css')?'text/css':full.endsWith('.json')?'application/json':'text/html';
   res.writeHead(200,{'Content-Type':type});res.end(content);
  }catch{res.writeHead(404);res.end('Not found')}
 });
 await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 let browser;
 const results=[];
 try{
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const base='http://127.0.0.1:'+server.address().port;
  for(const width of widths){
   const page=await browser.newPage({viewport:{width,height:844},deviceScaleFactor:1});
   const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   try{
    await page.goto(base+'/',{waitUntil:'networkidle'});
    await page.locator('#body h1').first().waitFor();
    for(const view of routes){
     await page.locator('#workspaceSection').selectOption(view);
     await page.locator('#body h1').first().waitFor();
     const report=await page.evaluate(()=>{
      const round=x=>Math.round(x*10)/10;
      const rect=el=>{const b=el.getBoundingClientRect();return {left:round(b.left),right:round(b.right),top:round(b.top),bottom:round(b.bottom),width:round(b.width),height:round(b.height)}};
      const brand=rect(document.querySelector('.brand'));
      const navigation=rect(document.querySelector('.mobile-workspace-navigation'));
      const sidebar=rect(document.querySelector('.sidebar'));
      const content=document.querySelector('.page');
      const pagebox=rect(content);
      const style=getComputedStyle(content);
      const inner={left:pagebox.left+parseFloat(style.paddingLeft),right:pagebox.right-parseFloat(style.paddingRight)};
      const kpiEls=[...document.querySelectorAll('#body .kpi')];
      const kpiLastColumn=kpiEls.length?getComputedStyle(kpiEls.at(-1)).gridColumn:null;
      const kpis=kpiEls.map(el=>{
       const r=rect(el),s=getComputedStyle(el),l=el.querySelector('.label'),label=l?rect(l):null;
       return {left:r.left,right:r.right,padLeft:parseFloat(s.paddingLeft),padRight:parseFloat(s.paddingRight),label};
      });
      const topButtons=[...document.querySelectorAll('.topbar button')].filter(el=>getComputedStyle(el).display!=='none').map(rect);
      const documentOverflow=document.documentElement.scrollWidth-document.documentElement.clientWidth;
      const decision=document.querySelector('.decision-brief');
      const countdown=decision?.querySelector('.decision-brief-days strong');
      const programme=decision?.querySelector('.decision-brief-link');
      const intersect=countdown&&programme?(()=>{
       const a=rect(countdown),b=rect(programme);
       return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
      })():false;
      const clipped=programme?programme.scrollHeight>programme.clientHeight+2:false;
      const panels=[...document.querySelectorAll('#body>.panel,#body>.assurance-layout,#body>.registry-summary,#body>.operational-hero,#body>.kpis')].map(el=>({name:el.className,...rect(el)}));
      const issues=[...document.querySelectorAll('#body .registry-summary>div')].map(el=>parseFloat(getComputedStyle(el).paddingLeft));
      return {sidebar,brand,navigation,documentOverflow,pagebox,inner,kpis,kpiLastColumn,topButtons,intersect,clipped,panels,issues};
     });
     assert.ok(report.documentOverflow<=2,width+'px '+view+' document horizontal overflow: '+report.documentOverflow);
     assert.ok(report.sidebar.height<=82,width+'px '+view+' mobile header wrapped to '+report.sidebar.height+'px');
     assert.ok(Math.abs((report.brand.top+report.brand.bottom)/2-(report.navigation.top+report.navigation.bottom)/2)<=9,width+'px '+view+' mobile header selector is not aligned with brand');
     assert.ok(report.topButtons.every(b=>b.left>=-1&&b.right<=width+1),width+'px '+view+' toolbar overflows viewport');
     assert.ok(report.panels.every(b=>b.left>=report.inner.left-3&&b.right<=report.inner.right+3),width+'px '+view+' top-level content extends beyond page gutter: '+JSON.stringify(report.panels));
     assert.ok(report.kpis.every(k=>k.padLeft>=13&&k.padRight>=13&&k.label&&k.label.left>=k.left+12),width+'px '+view+' KPI margin defect: '+JSON.stringify(report.kpis));
     if(width>350&&width<=760&&report.kpis.length>1&&report.kpis.length%2===0)
      assert.equal(report.kpiLastColumn,"auto",width+'px '+view+' even KPI count must not leave an empty grid cell');
     assert.ok(report.issues.every(pad=>pad>=12),width+'px '+view+' registry card padding regression');
     assert.equal(report.intersect,false,width+'px '+view+' countdown overlaps programme');
     assert.equal(report.clipped,false,width+'px '+view+' programme name clipped');
     if(view==='dashboard' && width===320){
      const cols=await page.locator('.kpis').evaluate(el=>getComputedStyle(el).gridTemplateColumns.trim().split(/\s+/).length);
      assert.equal(cols,1,'320px KPI grid must use a single column');
     }
     if((width===320||width===390||width===430)&&['dashboard','applications','review','sources','ledger','settings'].includes(view)){
      await page.screenshot({path:path.join(output,'layout-'+width+'-'+view+'.png'),fullPage:false});
     }
     results.push({width,view,passed:true});
    }
    assert.deepEqual(errors,[],width+'px browser errors');
    if(width===390){
     await page.locator('#workspaceSection').selectOption('applications');
     await page.locator('.app-card .rowbutton').first().click();
     const modal=await page.locator('.modal').evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right}});
     assert.ok(modal.left>=-1&&modal.right<=391,'mobile application dialog must stay within viewport');
     await page.keyboard.press('Escape');
    }
   }finally{await page.close()}
  }
  await fs.writeFile(path.join(output,'mobile-layout-audit.json'),JSON.stringify({checks:results.length,results},null,2));
  console.log('Mobile layout audit passed: '+results.length+' route/viewport combinations');
 }finally{
  if(browser)await browser.close();
  await new Promise(ok=>server.close(ok));
 }
}
main().catch(err=>{console.error(err);process.exitCode=1});
