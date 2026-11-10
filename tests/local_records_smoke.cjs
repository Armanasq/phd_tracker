'use strict';
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {chromium}=require('playwright');

const starter={
 schema_version:1,as_of:null,generated_at:"2026-11-09T00:00:00Z",timezone:"UTC",
 policy:"Independent starter",privacy:"No personal data on public Pages",
 instance:{repository:"TestAccount/atlas",type:"independent",data_mode:"starter",site_url:"https://testaccount.github.io/atlas/"},
 meta:{tracked:0,candidates:0,unpromoted_leads:0,notification_delivery:{}},
 records:[],leads:[],archive:[],tasks:[],task_ledger:[],duplicates:[],providers:[],watches:[],
 coverage:{workbook_audit_as_of:null,worksheets:[],files:[],totals:{tracked:0,research_candidates:0},discovery_errors:{}},
 documents:{academic_cv:"Academic CV"},global_document_states:{},
 source_links:{
  repository:"https://github.com/TestAccount/atlas",control_issue:"https://github.com/TestAccount/atlas/issues/new?template=00-owner-action-center.md",
  opportunities:"https://github.com/TestAccount/atlas/blob/main/data/opportunities.json",
  workbook:"https://github.com/TestAccount/atlas/blob/main/PhD_Action_List.xlsx",
  source_monitor:"https://github.com/TestAccount/atlas/actions/workflows/phd-intelligence.yml",
 }
};

async function main(){
 const root=path.resolve('site');
 const server=http.createServer(async(req,res)=>{
  try{
   const url=new URL(req.url,"http://127.0.0.1"),relative=decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname);
   const target=path.resolve(root,'.'+relative);
   if(!target.startsWith(root+path.sep)){res.writeHead(403);res.end();return}
   const content=await fs.readFile(target);
   const ext=path.extname(target);
   res.writeHead(200,{"Content-Type":({'.js':'application/javascript','.mjs':'application/javascript','.css':'text/css','.json':'application/json','.html':'text/html'}[ext]||'application/octet-stream')});
   res.end(content);
  }catch{res.writeHead(404);res.end("Not found")}
 });
 await new Promise(ok=>server.listen(0,"127.0.0.1",ok));
 const base="http://127.0.0.1:"+server.address().port;
 const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
 const page=await browser.newPage({viewport:{width:390,height:844},acceptDownloads:true});
 const errors=[];
 page.on("pageerror",error=>errors.push(error.message));
 await page.route("**/data/workspace.json",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(starter)}));
 const output=await fs.mkdtemp(path.join(os.tmpdir(),"atlas-local-"));
 try{
  await page.goto(base+"/",{waitUntil:"networkidle"});
  assert.match(await page.locator("#body h1").innerText(),/Set up your PhD workspace/);
  assert.ok((await page.locator("#body").innerText()).includes("without inherited applications"));
  await page.locator('[data-action="new-local"]').click();
  await page.locator("#localName").fill("Robotics and perception PhD");
  await page.locator("#localDeadline").fill("2027-01-31");
  await page.locator("#localCutoffTime").fill("16:00");
  await page.locator("#localCountry").fill("DE");
  await page.locator("#localSource").fill("https://example.edu/phd");
  await page.locator("#localNext").fill("Verify admission portal");
  await page.locator('[data-action="create-local"]').click();
  assert.match(await page.locator("#localError").innerText(),/cutoff time and institution timezone/);
  await page.locator("#localCutoffZone").fill("Europe/Berlin");
  await page.locator('[data-action="create-local"]').click();
  assert.ok((await page.locator(".modal").innerText()).includes("device-only"));
  assert.equal(await page.locator('.modal [data-action="save-command"]').count(),0);
  await page.locator("#editNotes").fill("PRIVATE draft note; not for GitHub");
  await page.locator("#editCutoffTime").fill("23:59");
  await page.locator("#editCutoffZone").fill("Europe/London");
  await page.locator("#editStatus").selectOption("preparing");
  await page.locator('[data-action="save-record"]').click();
  assert.equal(await page.locator(".modal").count(),0);
  await page.reload({waitUntil:"networkidle"});
  await page.locator("#workspaceSection").selectOption("applications");
  assert.ok((await page.locator("#body").innerText()).includes("Robotics and perception PhD"));
  assert.ok((await page.locator("#body").innerText()).includes("Preparing"));
  const localId=await page.locator('[data-action="record"][data-value^="LOCAL-"]').first().getAttribute("data-value");
  assert.match(localId,/^LOCAL-[0-9a-f-]+$/i);
  await page.locator("#exportMenu").click();
  const [sourceDownload]=await Promise.all([page.waitForEvent("download"),page.locator('[data-action="export"][data-value="github-source"]').click()]);
  await sourceDownload.saveAs(path.join(output,"user_opportunities.json"));
  const exported=JSON.parse(await fs.readFile(path.join(output,"user_opportunities.json"),"utf8"));
  assert.equal(exported.schema_version,1);
  assert.equal(exported.records.length,1);
  assert.equal(exported.records[0].name,"Robotics and perception PhD");
  assert.equal(exported.records[0].source_url,"https://example.edu/phd");
  assert.equal(exported.records[0].deadline_time,"23:59");
  assert.equal(exported.records[0].deadline_timezone,"Europe/London");
  assert.notEqual(exported.records[0].deadline_cutoff_verified,true);
  assert.equal("deadline_cutoff_utc" in exported.records[0],false);
  assert.ok(!JSON.stringify(exported).includes("PRIVATE draft note"));
  assert.ok(!JSON.stringify(exported).includes("preparing"));
  const [backupDownload]=await Promise.all([page.waitForEvent("download"),page.locator('.modal [data-action="export"][data-value="local"]').click()]);
  const backup=path.join(output,"local-backup.json");
  await backupDownload.saveAs(backup);
  assert.ok((await fs.readFile(backup,"utf8")).includes("PRIVATE draft note"));
  assert.ok((await fs.readFile(backup,"utf8")).includes("Europe/London"));
  await page.locator('.modal [data-action="close"]').click();
  await page.locator(".modal").waitFor({state:"detached"});
  await page.locator('#workspaceSection').selectOption("applications");
  await page.locator('.app-card:visible .rowbutton[data-action="record"][data-value="'+localId+'"]').click();
  page.once('dialog',d=>d.accept());
  await page.locator('[data-action="delete-local"]').click();
  assert.ok(!(await page.locator("#body").innerText()).includes("Robotics and perception PhD"));
  await page.locator("#localImportFile").setInputFiles(backup);
  await page.locator("#workspaceSection").selectOption("applications");
  await page.waitForFunction(()=>document.querySelector("#body")?.textContent?.includes("Robotics and perception PhD"),{timeout:10000});
  assert.ok((await page.locator("#body").innerText()).includes("Robotics and perception PhD"));
  await page.reload({waitUntil:"networkidle"});
  await page.locator("#workspaceSection").selectOption("applications");
  assert.ok((await page.locator("#body").innerText()).includes("Robotics and perception PhD"));
  assert.equal(await page.locator('.sidebar .side-link').getAttribute("href"),"https://github.com/TestAccount/atlas");
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:"pass",checks:["starter isolation","create","cutoff pair validation","local cutoff edit","reload","public export scrub","backup","delete","import","repo identity","mobile"]}));
 }finally{
  await page.close();await browser.close();await new Promise(ok=>server.close(ok));
  await fs.rm(output,{recursive:true,force:true});
 }
}
main().catch(error=>{console.error(error);process.exitCode=1});
